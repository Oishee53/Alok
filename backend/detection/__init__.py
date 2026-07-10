"""
Detection module initialization
File: backend/detection/__init__.py
"""

from .model import YOLOModel, create_model
from .live_detect import DualModelDetector, VoiceAnnouncer, start_live_detection, CONFIG
from .utils import (
    calculate_box_area,
    calculate_box_center,
    calculate_distance_from_center,
    draw_proximity_zone,
    format_detection_info,
    apply_nms,
    resize_frame,
    save_detection_snapshot
)

# Backward compatibility
ObjectDetector = DualModelDetector

__all__ = [
    'YOLOModel',
    'create_model',
    'DualModelDetector',
    'ObjectDetector',
    'VoiceAnnouncer',
    'start_live_detection',
    'CONFIG',
    'calculate_box_area',
    'calculate_box_center',
    'calculate_distance_from_center',
    'draw_proximity_zone',
    'format_detection_info',
    'apply_nms',
    'resize_frame',
    'save_detection_snapshot'
]