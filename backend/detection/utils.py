"""
Utility functions for object detection
File: backend/detection/utils.py
"""

import cv2
import numpy as np

def calculate_box_area(box):
    """Calculate area of bounding box"""
    x1, y1, x2, y2 = box
    return (x2 - x1) * (y2 - y1)

def calculate_box_center(box):
    """Calculate center point of bounding box"""
    x1, y1, x2, y2 = box
    center_x = (x1 + x2) / 2
    center_y = (y1 + y2) / 2
    return (center_x, center_y)

def calculate_distance_from_center(box, frame_shape):
    """Calculate distance of bounding box from frame center"""
    frame_height, frame_width = frame_shape[:2]
    frame_center = (frame_width / 2, frame_height / 2)
    box_center = calculate_box_center(box)
    
    distance = np.sqrt(
        (box_center[0] - frame_center[0])**2 + 
        (box_center[1] - frame_center[1])**2
    )
    return distance

def draw_proximity_zone(frame, min_area):
    """Draw a visual indicator of the proximity zone"""
    height, width = frame.shape[:2]
    
    # Calculate approximate radius based on min_area
    # Assuming square box: side = sqrt(area)
    side = int(np.sqrt(min_area))
    
    # Draw center circle to indicate proximity zone
    center = (width // 2, height // 2)
    radius = side // 2
    
    cv2.circle(frame, center, radius, (0, 255, 255), 2)
    cv2.putText(frame, "Proximity Zone", 
                (center[0] - 70, center[1] - radius - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    
    return frame

def format_detection_info(detected_objects, confidences=None):
    """Format detection information for display"""
    if not detected_objects:
        return "No objects detected"
    
    if confidences:
        info = []
        for obj, conf in zip(detected_objects, confidences):
            info.append(f"{obj} ({conf:.2f})")
        return ", ".join(info)
    else:
        return ", ".join(detected_objects)

def apply_nms(boxes, confidences, iou_threshold=0.4):
    """Apply Non-Maximum Suppression to remove overlapping boxes"""
    if len(boxes) == 0:
        return []
    
    boxes_np = np.array(boxes)
    confidences_np = np.array(confidences)
    
    # Convert to format expected by cv2.dnn.NMSBoxes
    x1 = boxes_np[:, 0]
    y1 = boxes_np[:, 1]
    x2 = boxes_np[:, 2]
    y2 = boxes_np[:, 3]
    
    widths = x2 - x1
    heights = y2 - y1
    
    boxes_xywh = np.column_stack([x1, y1, widths, heights])
    
    indices = cv2.dnn.NMSBoxes(
        boxes_xywh.tolist(),
        confidences_np.tolist(),
        score_threshold=0.5,
        nms_threshold=iou_threshold
    )
    
    if len(indices) > 0:
        return indices.flatten().tolist()
    return []

def resize_frame(frame, max_width=None, max_height=None):
    """Resize frame while maintaining aspect ratio"""
    height, width = frame.shape[:2]
    
    if max_width and width > max_width:
        ratio = max_width / width
        new_width = max_width
        new_height = int(height * ratio)
        frame = cv2.resize(frame, (new_width, new_height))
    
    if max_height and frame.shape[0] > max_height:
        height, width = frame.shape[:2]
        ratio = max_height / height
        new_height = max_height
        new_width = int(width * ratio)
        frame = cv2.resize(frame, (new_width, new_height))
    
    return frame

def save_detection_snapshot(frame, detected_objects, output_dir='snapshots'):
    """Save a snapshot of current detection"""
    import os
    from datetime import datetime
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    objects_str = '_'.join(detected_objects) if detected_objects else 'none'
    filename = f"{timestamp}_{objects_str}.jpg"
    filepath = os.path.join(output_dir, filename)
    
    cv2.imwrite(filepath, frame)
    return filepath