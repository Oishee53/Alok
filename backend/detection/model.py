"""
YOLO Model Handler
File: backend/detection/model.py
"""

from ultralytics import YOLO
import torch
import cv2
import numpy as np
from pathlib import Path

try:
    from .config import MODEL_PATHS, DEFAULT_MODEL, get_model_path
except ImportError:
    # Fallback if config.py is not available
    def get_model_path(model_name='best.pt'):
        current_dir = Path(__file__).parent.absolute()
        model_path = current_dir / model_name
        if model_path.exists():
            return str(model_path)
        return model_name
    
    MODEL_PATHS = {
        'custom': get_model_path('best.pt'),
        'nano': get_model_path('yolo11n.pt'),
        'small': 'yolo11s.pt',
        'medium': 'yolo11m.pt',
        'large': 'yolo11l.pt',
        'xlarge': 'yolo11x.pt'
    }
    DEFAULT_MODEL = 'custom'

class YOLOModel:
    """Wrapper class for YOLO model operations"""
    
    def __init__(self, model_path=None, device=None):
        """
        Initialize YOLO model
        
        Args:
            model_path: Path to YOLO model weights (if None, uses default custom model)
            device: Device to run model on ('cpu', 'cuda', or None for auto)
        """
        if model_path is None:
            model_path = MODEL_PATHS.get(DEFAULT_MODEL, 'best.pt')
        self.model_path = model_path
        self.device = device if device else ('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = None
        self.class_names = None
        self._load_model()
    
    def _load_model(self):
        """Load YOLO model from weights file"""
        try:
            print(f"Loading YOLO model from {self.model_path}...")
            self.model = YOLO(self.model_path)
            self.class_names = self.model.names
            print(f"Model loaded successfully on {self.device}")
            print(f"Available classes: {len(self.class_names)}")
        except Exception as e:
            print(f"Error loading model: {e}")
            raise
    
    def predict(self, image, conf_threshold=0.5, iou_threshold=0.45, verbose=False):
        """
        Run prediction on an image
        
        Args:
            image: Input image (numpy array or path)
            conf_threshold: Confidence threshold for detections
            iou_threshold: IOU threshold for NMS
            verbose: Whether to print verbose output
            
        Returns:
            Results object from YOLO
        """
        if self.model is None:
            raise RuntimeError("Model not loaded")
        
        results = self.model(
            image,
            conf=conf_threshold,
            iou=iou_threshold,
            verbose=verbose,
            device=self.device
        )
        
        return results
    
    def predict_and_parse(self, image, conf_threshold=0.5):
        """
        Run prediction and return parsed results
        
        Args:
            image: Input image
            conf_threshold: Confidence threshold
            
        Returns:
            dict with boxes, confidences, class_ids, and class_names
        """
        results = self.predict(image, conf_threshold=conf_threshold)
        
        parsed_results = {
            'boxes': [],
            'confidences': [],
            'class_ids': [],
            'class_names': []
        }
        
        if results[0].boxes is not None and len(results[0].boxes) > 0:
            for box in results[0].boxes:
                # Bounding box coordinates
                xyxy = box.xyxy[0].cpu().numpy()
                parsed_results['boxes'].append(xyxy)
                
                # Confidence score
                conf = float(box.conf[0])
                parsed_results['confidences'].append(conf)
                
                # Class ID and name
                cls_id = int(box.cls[0])
                parsed_results['class_ids'].append(cls_id)
                parsed_results['class_names'].append(self.class_names[cls_id])
        
        return parsed_results
    
    def annotate_image(self, image, results):
        """
        Annotate image with detection results
        
        Args:
            image: Original image
            results: YOLO results object
            
        Returns:
            Annotated image
        """
        return results[0].plot()
    
    def get_class_name(self, class_id):
        """Get class name from class ID"""
        return self.class_names.get(class_id, 'Unknown')
    
    def get_all_classes(self):
        """Get all available class names"""
        return list(self.class_names.values())
    
    def detect_from_file(self, image_path, conf_threshold=0.5, save_path=None):
        """
        Detect objects in an image file
        
        Args:
            image_path: Path to image file
            conf_threshold: Confidence threshold
            save_path: Optional path to save annotated image
            
        Returns:
            Parsed detection results and annotated image
        """
        # Read image
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Could not read image from {image_path}")
        
        # Run detection
        results = self.predict(image, conf_threshold=conf_threshold)
        parsed = self.predict_and_parse(image, conf_threshold=conf_threshold)
        annotated = self.annotate_image(image, results)
        
        # Save if requested
        if save_path:
            cv2.imwrite(save_path, annotated)
            print(f"Saved annotated image to {save_path}")
        
        return parsed, annotated
    
    def detect_from_camera(self, camera_id=0, conf_threshold=0.5):
        """
        Run detection on camera feed (generator)
        
        Args:
            camera_id: Camera device ID
            conf_threshold: Confidence threshold
            
        Yields:
            Tuple of (annotated_frame, parsed_results)
        """
        cap = cv2.VideoCapture(camera_id)
        
        if not cap.isOpened():
            raise RuntimeError(f"Could not open camera {camera_id}")
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                results = self.predict(frame, conf_threshold=conf_threshold)
                parsed = self.predict_and_parse(frame, conf_threshold=conf_threshold)
                annotated = self.annotate_image(frame, results)
                
                yield annotated, parsed
        
        finally:
            cap.release()
    
    def batch_predict(self, images, conf_threshold=0.5):
        """
        Run prediction on multiple images
        
        Args:
            images: List of images or image paths
            conf_threshold: Confidence threshold
            
        Returns:
            List of parsed results
        """
        all_results = []
        
        for image in images:
            parsed = self.predict_and_parse(image, conf_threshold=conf_threshold)
            all_results.append(parsed)
        
        return all_results
    
    def export_model(self, format='onnx', output_path=None):
        """
        Export model to different format
        
        Args:
            format: Export format ('onnx', 'torchscript', 'tflite', etc.)
            output_path: Optional output path
        """
        if output_path:
            self.model.export(format=format, output=output_path)
        else:
            self.model.export(format=format)
        
        print(f"Model exported to {format} format")
    
    def __repr__(self):
        return f"YOLOModel(model_path='{self.model_path}', device='{self.device}', classes={len(self.class_names)})"


# Helper function to create model instance
def create_model(model_type='custom', device=None):
    """
    Create a YOLO model instance
    
    Args:
        model_type: Model size ('custom', 'nano', 'small', 'medium', 'large', 'xlarge')
        device: Device to run on
        
    Returns:
        YOLOModel instance
    """
    model_path = MODEL_PATHS.get(model_type.lower(), MODEL_PATHS['custom'])
    return YOLOModel(model_path=model_path, device=device)


if __name__ == "__main__":
    # Test the model
    model = create_model('nano')
    print(model)
    print(f"Available classes: {model.get_all_classes()[:10]}...")  # Print first 10 classes