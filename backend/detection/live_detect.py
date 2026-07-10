"""
Live object detection with proximity filtering and voice announcements
AUTOMATIC DUAL MODEL DETECTION - Detects with BOTH models simultaneously!

Announcements are spatial ("ডান দিকে একটি গাড়ি, খুব কাছে") and spoken from a
background thread, so detection never stalls while audio plays. Runs
headless by default — no window and no keyboard needed; stop with Ctrl+C
or by passing max_duration.

File: backend/detection/live_detect.py
"""

import cv2
from ultralytics import YOLO
import time
from pathlib import Path

# Try package-relative imports (when imported by FastAPI routes), fall
# back to plain imports (when run directly from the detection/ folder).
try:
    from .config import get_model_path
    from .announcer import VoiceAnnouncer, describe_detection, generate_announcement
except ImportError:
    try:
        from config import get_model_path
    except ImportError:
        def get_model_path(model_name='best.pt'):
            model_file = Path(__file__).parent.absolute() / model_name
            return str(model_file) if model_file.exists() else model_name
    from announcer import VoiceAnnouncer, describe_detection, generate_announcement

MODEL_PATH = get_model_path('best.pt')

# Configuration
CONFIG = {
    'custom_model_path': MODEL_PATH,
    'pretrained_model_path': str(Path(__file__).parent / 'yolo11n.pt'),
    'min_confidence': 0.5,
    'min_box_area': 5000,
    'min_announcement_interval': 2,
    'camera_width': 640,
    'camera_height': 480,
    'camera_fps': 30,
    'detection_interval': 3,
    'use_dual_models': True,
    'language': 'bn',  # Bangla
}


class DualModelDetector:
    """Handles YOLO object detection with BOTH custom and pretrained models"""

    def __init__(self, config):
        self.config = config
        self.models = {}
        self.last_announced_scene = set()
        self.last_announcement_time = 0

        # Load custom model
        try:
            print(f"Loading CUSTOM model from {config['custom_model_path']}...")
            self.models['custom'] = YOLO(config['custom_model_path'])
            custom_classes = len(self.models['custom'].names)
            print(f"✓ Custom model loaded ({custom_classes} classes)")
        except Exception as e:
            print(f"✗ Could not load custom model: {e}")

        # Load pretrained model
        try:
            print(f"Loading PRETRAINED model from {config['pretrained_model_path']}...")
            self.models['pretrained'] = YOLO(config['pretrained_model_path'])
            pretrained_classes = len(self.models['pretrained'].names)
            print(f"✓ Pretrained model loaded ({pretrained_classes} classes)")
        except Exception as e:
            print(f"✗ Could not load pretrained model: {e}")

        if not self.models:
            raise RuntimeError("No models could be loaded!")

        print(f"→ Loaded {len(self.models)} model(s) for detection")

    def filter_by_proximity(self, boxes, confidences, class_ids):
        """Filter detections by bounding box size (proximity indicator)"""
        filtered_boxes = []
        filtered_confidences = []
        filtered_classes = []

        min_area = self.config['min_box_area']

        for box, conf, cls in zip(boxes, confidences, class_ids):
            x1, y1, x2, y2 = box
            area = (x2 - x1) * (y2 - y1)

            if area >= min_area:
                filtered_boxes.append(box)
                filtered_confidences.append(conf)
                filtered_classes.append(cls)

        return filtered_boxes, filtered_confidences, filtered_classes

    def _run_model(self, model_key, frame):
        """Run one model on a frame and return proximity-filtered detections."""
        results = self.models[model_key](
            frame,
            conf=self.config['min_confidence'],
            verbose=False
        )

        boxes, confidences, class_ids = [], [], []
        if results[0].boxes is not None and len(results[0].boxes) > 0:
            for box in results[0].boxes:
                boxes.append(box.xyxy[0].cpu().numpy())
                confidences.append(float(box.conf[0]))
                class_ids.append(int(box.cls[0]))

        return self.filter_by_proximity(boxes, confidences, class_ids)

    def process_frame_dual(self, frame, annotate=True):
        """
        Process frame with BOTH models and merge results.

        Returns (annotated_frame, detections) where each detection dict has
        class_name, confidence, box, source_model, direction, proximity,
        hedged, and a Bangla phrase.
        """
        frame_height, frame_width = frame.shape[:2]
        detections = []
        annotated_frame = frame.copy() if annotate else frame

        # Custom model first (its detections have priority)
        if 'custom' in self.models:
            boxes, confs, classes = self._run_model('custom', frame)
            for box, conf, cls in zip(boxes, confs, classes):
                class_name = self.models['custom'].names[cls]
                det = {
                    'class_name': class_name,
                    'confidence': conf,
                    'box': box,
                    'source_model': 'custom',
                }
                det.update(describe_detection(
                    class_name, conf, box, frame_width, frame_height))
                detections.append(det)

                if annotate:
                    x1, y1, x2, y2 = map(int, box)
                    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (255, 0, 0), 3)
                    label = f"{class_name} ({conf:.2f}) [CUSTOM]"
                    cv2.putText(annotated_frame, label, (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

        # Pretrained model, skipping boxes that duplicate custom detections
        if 'pretrained' in self.models:
            boxes, confs, classes = self._run_model('pretrained', frame)
            for box, conf, cls in zip(boxes, confs, classes):
                is_duplicate = any(
                    d['source_model'] == 'custom'
                    and self.calculate_iou(box, d['box']) > 0.5
                    for d in detections
                )
                if is_duplicate:
                    continue

                class_name = self.models['pretrained'].names[cls]
                det = {
                    'class_name': class_name,
                    'confidence': conf,
                    'box': box,
                    'source_model': 'pretrained',
                }
                det.update(describe_detection(
                    class_name, conf, box, frame_width, frame_height))
                detections.append(det)

                if annotate:
                    x1, y1, x2, y2 = map(int, box)
                    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
                    label = f"{class_name} ({conf:.2f}) [PRETRAINED]"
                    cv2.putText(annotated_frame, label, (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        if annotate:
            custom_count = sum(1 for d in detections if d['source_model'] == 'custom')
            pretrained_count = len(detections) - custom_count
            cv2.putText(annotated_frame,
                        f"Custom: {custom_count} | Pretrained: {pretrained_count}",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(annotated_frame, f"Total close objects: {len(detections)}",
                        (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(annotated_frame, "BLUE=Custom | GREEN=Pretrained",
                        (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

        return annotated_frame, detections

    def calculate_iou(self, box1, box2):
        """Calculate Intersection over Union of two boxes"""
        x1_1, y1_1, x2_1, y2_1 = box1
        x1_2, y1_2, x2_2, y2_2 = box2

        x1_i = max(x1_1, x1_2)
        y1_i = max(y1_1, y1_2)
        x2_i = min(x2_1, x2_2)
        y2_i = min(y2_1, y2_2)

        if x2_i < x1_i or y2_i < y1_i:
            return 0.0

        intersection = (x2_i - x1_i) * (y2_i - y1_i)
        area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
        area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
        union = area1 + area2 - intersection

        return intersection / union if union > 0 else 0.0

    def should_announce(self, detections, current_time):
        """
        Announce when the scene changed — same object moving to a new
        direction counts as a change, since position is what the user
        acts on — and the minimum interval has passed.
        """
        scene = {(d['class_name'], d['direction']) for d in detections}
        objects_changed = scene != self.last_announced_scene
        time_elapsed = (current_time - self.last_announcement_time
                        >= self.config['min_announcement_interval'])

        return objects_changed and time_elapsed

    def mark_announced(self, detections, current_time):
        """Record what was just announced, for change detection."""
        self.last_announced_scene = {
            (d['class_name'], d['direction']) for d in detections
        }
        self.last_announcement_time = current_time


def start_live_detection(show_window=False, max_duration=None):
    """
    Main function to start live detection with BOTH models.

    Args:
        show_window: Show the annotated OpenCV window (needs a display and
            keyboard — for sighted developers debugging). Default False:
            audio-only, stop with Ctrl+C.
        max_duration: Optional run time limit in seconds.
    """

    print("\n" + "=" * 60)
    print("  স্বয়ংক্রিয় ডুয়াল মডেল লাইভ ডিটেকশন")
    print("=" * 60)
    if show_window:
        print("  নীল বক্স   = কাস্টম মডেল (আপনার অবজেক্ট)")
        print("  সবুজ বক্স  = প্রি-ট্রেইন্ড মডেল (সাধারণ অবজেক্ট)")
        print("=" * 60 + "\n")

    detector = DualModelDetector(CONFIG)
    announcer = VoiceAnnouncer()

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Camera not found!")
        announcer.speak("ক্যামেরা পাওয়া যায়নি")
        time.sleep(3)  # give the async announcement a moment to play
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CONFIG['camera_width'])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CONFIG['camera_height'])
    cap.set(cv2.CAP_PROP_FPS, CONFIG['camera_fps'])

    stop_hint = "'q' চাপুন বন্ধ করতে।" if show_window else "Ctrl+C চাপুন বন্ধ করতে।"
    print(f"লাইভ ডিটেকশন শুরু হচ্ছে... {stop_hint}")
    print(f"Settings: Min confidence={CONFIG['min_confidence']}, Min box area={CONFIG['min_box_area']}")
    print(f"Models active: {len(detector.models)}")
    print()

    frame_count = 0
    annotated_frame = None
    start_time = time.time()

    try:
        while True:
            if max_duration and time.time() - start_time >= max_duration:
                print(f"\nসময়সীমা ({max_duration}s) শেষ।")
                break

            ret, frame = cap.read()
            if not ret:
                print("Failed to read frame")
                break

            frame_count += 1

            if frame_count % CONFIG['detection_interval'] == 0:
                annotated_frame, detections = detector.process_frame_dual(
                    frame, annotate=show_window)

                current_time = time.time()

                if detector.should_announce(detections, current_time):
                    if detections:
                        announcement = generate_announcement(detections)

                        custom_objects = {d['class_name'] for d in detections
                                          if d['source_model'] == 'custom'}
                        pretrained_objects = {d['class_name'] for d in detections
                                              if d['source_model'] == 'pretrained'}

                        print(f"\n>>> সনাক্ত করা হয়েছে:")
                        if custom_objects:
                            print(f"    কাস্টম মডেল: {', '.join(custom_objects)}")
                        if pretrained_objects:
                            print(f"    প্রি-ট্রেইন্ড মডেল: {', '.join(pretrained_objects)}")
                        print(f"    ঘোষণা: {announcement}\n")

                        # Non-blocking: detection keeps running while this plays
                        announcer.speak(announcement)
                    else:
                        print("কোন কাছাকাছি অবজেক্ট সনাক্ত করা যায়নি")

                    detector.mark_announced(detections, current_time)

            if show_window:
                display = annotated_frame if annotated_frame is not None else frame
                cv2.imshow("Dual Model Live Detection (Press 'q' to quit)", display)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

    except KeyboardInterrupt:
        print("\nবন্ধ করা হচ্ছে...")
    finally:
        cap.release()
        if show_window:
            cv2.destroyAllWindows()

    print("\nলাইভ ডিটেকশন শেষ হয়েছে।")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Live dual-model detection with Bangla voice")
    parser.add_argument('--window', action='store_true',
                        help="Show annotated video window (debugging; needs display + keyboard)")
    parser.add_argument('--duration', type=float, default=None,
                        help="Stop automatically after this many seconds")
    args = parser.parse_args()

    start_live_detection(show_window=args.window, max_duration=args.duration)
