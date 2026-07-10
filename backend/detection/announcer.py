"""
Bangla announcement generation and non-blocking voice output.

Shared between the live desktop loop (live_detect.py) and the FastAPI
routes, so a remote client gets the exact same announcement text that
the local voice pipeline would speak.

File: backend/detection/announcer.py
"""

import hashlib
import os
import queue
import re
import sys
import tempfile
import threading
from collections import deque
from pathlib import Path

# Confidence below this is announced with "সম্ভবত" (possibly) — for a
# currency reader, false certainty is worse than admitted uncertainty.
HEDGE_CONFIDENCE = 0.65

# Box-area / frame-area ratios for proximity buckets
VERY_CLOSE_AREA_RATIO = 0.30
CLOSE_AREA_RATIO = 0.10

BANGLA_TRANSLATIONS = {
    # Custom model classes (taka denominations in best.pt)
    '1 Taka': 'এক টাকার নোট',
    '2 Taka': 'দুই টাকার নোট',
    '5 Taka': 'পাঁচ টাকার নোট',
    '10 Taka': 'দশ টাকার নোট',
    '20 Taka': 'বিশ টাকার নোট',
    '50 Taka': 'পঞ্চাশ টাকার নোট',
    '100 Taka': 'একশো টাকার নোট',
    '200 Taka': 'দুইশো টাকার নোট',
    '500 Taka': 'পাঁচশো টাকার নোট',
    '1000 Taka': 'এক হাজার টাকার নোট',
    # Generic label used while denomination voting hasn't settled yet
    'Taka Note': 'টাকার নোট',

    # Common objects from pretrained model
    'person': 'মানুষ',
    'bicycle': 'সাইকেল',
    'car': 'গাড়ি',
    'motorcycle': 'মোটরসাইকেল',
    'airplane': 'বিমান',
    'bus': 'বাস',
    'train': 'ট্রেন',
    'truck': 'ট্রাক',
    'boat': 'নৌকা',
    'traffic light': 'ট্রাফিক লাইট',
    'fire hydrant': 'ফায়ার হাইড্রান্ট',
    'stop sign': 'স্টপ সাইন',
    'parking meter': 'পার্কিং মিটার',
    'bench': 'বেঞ্চ',
    'bird': 'পাখি',
    'cat': 'বিড়াল',
    'dog': 'কুকুর',
    'horse': 'ঘোড়া',
    'sheep': 'ভেড়া',
    'cow': 'গরু',
    'elephant': 'হাতি',
    'bear': 'ভালুক',
    'zebra': 'জেব্রা',
    'giraffe': 'জিরাফ',
    'backpack': 'ব্যাকপ্যাক',
    'umbrella': 'ছাতা',
    'handbag': 'হ্যান্ডব্যাগ',
    'tie': 'টাই',
    'suitcase': 'স্যুটকেস',
    'frisbee': 'ফ্রিসবি',
    'skis': 'স্কি',
    'snowboard': 'স্নোবোর্ড',
    'sports ball': 'খেলার বল',
    'kite': 'ঘুড়ি',
    'baseball bat': 'বেসবল ব্যাট',
    'baseball glove': 'বেসবল গ্লাভস',
    'skateboard': 'স্কেটবোর্ড',
    'surfboard': 'সার্ফবোর্ড',
    'tennis racket': 'টেনিস র‍্যাকেট',
    'bottle': 'বোতল',
    'wine glass': 'ওয়াইন গ্লাস',
    'cup': 'কাপ',
    'fork': 'কাঁটা চামচ',
    'knife': 'ছুরি',
    'spoon': 'চামচ',
    'bowl': 'বাটি',
    'banana': 'কলা',
    'apple': 'আপেল',
    'sandwich': 'স্যান্ডউইচ',
    'orange': 'কমলা',
    'broccoli': 'ব্রকলি',
    'carrot': 'গাজর',
    'hot dog': 'হট ডগ',
    'pizza': 'পিজা',
    'donut': 'ডোনাট',
    'cake': 'কেক',
    'chair': 'চেয়ার',
    'couch': 'সোফা',
    'potted plant': 'গাছের টব',
    'bed': 'বিছানা',
    'dining table': 'খাবার টেবিল',
    'toilet': 'টয়লেট',
    'tv': 'টিভি',
    'laptop': 'ল্যাপটপ',
    'mouse': 'মাউস',
    'remote': 'রিমোট',
    'keyboard': 'কিবোর্ড',
    'cell phone': 'মোবাইল ফোন',
    'microwave': 'মাইক্রোওয়েভ',
    'oven': 'ওভেন',
    'toaster': 'টোস্টার',
    'sink': 'সিঙ্ক',
    'refrigerator': 'ফ্রিজ',
    'book': 'বই',
    'clock': 'ঘড়ি',
    'vase': 'ফুলদানি',
    'scissors': 'কাঁচি',
    'teddy bear': 'টেডি বিয়ার',
    'hair drier': 'হেয়ার ড্রায়ার',
    'toothbrush': 'টুথব্রাশ',
}

DIRECTION_BN = {
    'left': 'বাম দিকে',
    'center': 'সামনে',
    'right': 'ডান দিকে',
}

PROXIMITY_BN = {
    'very_close': 'খুব কাছে',
    'close': 'কাছে',
    'far': 'দূরে',
}


_TAKA_CLASS_RE = re.compile(r'^\d+ Taka$')
GENERIC_NOTE_CLASS = 'Taka Note'


class DenominationStabilizer:
    """
    Majority voting for banknote denominations across video frames.

    A single frame is unreliable: a tilted or blurred note flips between
    denominations frame to frame, and announcing each guess reads wrong
    values aloud. Instead, per-frame results vote over a sliding window;
    until one denomination wins at least `min_votes` of the last `window`
    frames, the note is announced generically as "টাকার নোট". Once a
    winner emerges, disagreeing single frames are relabeled to it.

    One instance per client connection (state is per camera session).
    Only applied when a single note is in frame — with several distinct
    notes visible, voting across them would be meaningless.
    """

    def __init__(self, window=5, min_votes=3):
        self.history = deque(maxlen=window)
        self.min_votes = min_votes

    @staticmethod
    def is_taka(class_name):
        return bool(_TAKA_CLASS_RE.match(class_name or ''))

    def stabilize(self, detections):
        """Takes and returns a merged detection list (dicts with
        class_name/confidence). Non-taka detections pass through."""
        taka = [d for d in detections if self.is_taka(d['class_name'])]
        others = [d for d in detections if not self.is_taka(d['class_name'])]

        # Record this frame's votes: best confidence per denomination
        frame_votes = {}
        for d in taka:
            c = d['class_name']
            frame_votes[c] = max(frame_votes.get(c, 0.0), d['confidence'])
        self.history.append(frame_votes)

        if len(taka) != 1:
            # No note, or several distinct notes — nothing to stabilize
            return detections

        # Tally the window: appearances first, accumulated confidence as tiebreak
        counts, conf_sum = {}, {}
        for votes in self.history:
            for c, conf in votes.items():
                counts[c] = counts.get(c, 0) + 1
                conf_sum[c] = conf_sum.get(c, 0.0) + conf

        winner = max(counts, key=lambda c: (counts[c], conf_sum[c]))
        det = taka[0]

        if counts[winner] >= self.min_votes:
            if det['class_name'] != winner:
                det = {**det, 'class_name': winner}
        else:
            # Not enough agreement yet — say it's a note, don't guess the value
            det = {**det, 'class_name': GENERIC_NOTE_CLASS}

        return [det] + others


def get_direction(box, frame_width):
    """Classify a box as left / center / right by its horizontal center."""
    x1, _, x2, _ = box[:4]
    center_x = (x1 + x2) / 2
    if center_x < frame_width / 3:
        return 'left'
    if center_x > frame_width * 2 / 3:
        return 'right'
    return 'center'


def get_proximity(box, frame_width, frame_height):
    """Classify a box as very_close / close / far by its area relative to the frame."""
    x1, y1, x2, y2 = box[:4]
    frame_area = frame_width * frame_height
    if frame_area <= 0:
        return 'far'
    ratio = ((x2 - x1) * (y2 - y1)) / frame_area
    if ratio >= VERY_CLOSE_AREA_RATIO:
        return 'very_close'
    if ratio >= CLOSE_AREA_RATIO:
        return 'close'
    return 'far'


def describe_detection(class_name, confidence, box, frame_width, frame_height):
    """
    Build a spatially-aware Bangla phrase for one detection,
    e.g. "ডান দিকে একটি গাড়ি, খুব কাছে" or "সম্ভবত একশো টাকার নোট".

    Returns dict with direction, proximity, hedged flag, and the phrase.
    """
    direction = get_direction(box, frame_width)
    proximity = get_proximity(box, frame_width, frame_height)
    hedged = confidence < HEDGE_CONFIDENCE

    bangla_name = BANGLA_TRANSLATIONS.get(class_name, class_name)
    phrase = f"{DIRECTION_BN[direction]} একটি {bangla_name}"
    if hedged:
        phrase = f"সম্ভবত {phrase}"
    if proximity == 'very_close':
        phrase += f", {PROXIMITY_BN['very_close']}"

    return {
        'direction': direction,
        'proximity': proximity,
        'hedged': hedged,
        'phrase': phrase,
    }


def generate_announcement(descriptions):
    """
    Combine per-detection phrases (from describe_detection) into one
    Bangla announcement sentence.
    """
    phrases = [d['phrase'] for d in descriptions]
    if not phrases:
        return "কিছু পাওয়া যায়নি"
    if len(phrases) == 1:
        return phrases[0]
    return " এবং ".join([", ".join(phrases[:-1]), phrases[-1]])


class VoiceAnnouncer:
    """
    Non-blocking Bangla text-to-speech.

    - speak() only enqueues; a daemon worker thread synthesizes and plays,
      so the detection loop never stalls while audio is playing.
    - The queue holds one pending announcement: a newer one replaces a
      stale unplayed one (old scene info is worse than no info).
    - gTTS output is cached on disk keyed by text, so the fixed vocabulary
      (denominations, common objects) works offline after first use.
    - If gTTS fails (no network, cache miss), falls back to offline
      pyttsx3; if that also fails, plays an error tone so the user knows
      the announcement was lost instead of failing silently.
    """

    def __init__(self, cache_dir=None):
        if cache_dir is None:
            cache_dir = Path(__file__).parent / 'tts_cache'
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self._queue = queue.Queue(maxsize=1)
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def speak(self, text):
        """Queue an announcement without blocking; newest wins."""
        try:
            self._queue.put_nowait(text)
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(text)
            except queue.Full:
                pass

    def _run(self):
        while True:
            text = self._queue.get()
            try:
                self._speak_blocking(text)
            except Exception as e:
                print(f"Speech error: {e}")
                self._error_tone()

    def _cache_path(self, text):
        digest = hashlib.md5(text.encode('utf-8')).hexdigest()
        return self.cache_dir / f"{digest}.mp3"

    def _speak_blocking(self, text):
        audio_file = self._cache_path(text)

        if not audio_file.exists():
            try:
                from gtts import gTTS
                tts = gTTS(text=text, lang='bn', slow=False)
                # Write to a temp file first so a failed download never
                # leaves a truncated mp3 in the cache.
                with tempfile.NamedTemporaryFile(
                        delete=False, suffix='.mp3', dir=self.cache_dir) as fp:
                    tmp_name = fp.name
                tts.save(tmp_name)
                os.replace(tmp_name, audio_file)
            except Exception as e:
                print(f"gTTS unavailable ({e}), trying offline TTS")
                self._speak_offline(text)
                return

        from playsound import playsound
        playsound(str(audio_file))

    def _speak_offline(self, text):
        """Offline fallback via pyttsx3 (voice quality depends on installed OS voices)."""
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            print(f"Offline TTS failed: {e}")
            self._error_tone()

    @staticmethod
    def _error_tone():
        """Audible signal that an announcement could not be spoken."""
        try:
            if sys.platform == 'win32':
                import winsound
                winsound.Beep(440, 300)
            else:
                sys.stdout.write('\a')
                sys.stdout.flush()
        except Exception:
            pass
