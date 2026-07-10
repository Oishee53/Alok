"""
Configuration for model paths
File: backend/detection/config.py
"""

import os
from pathlib import Path

def get_model_path(model_name='best.pt'):
    """
    Get the correct model path regardless of where the script is run from
    
    Args:
        model_name: Name of the model file
        
    Returns:
        Absolute path to the model file
    """
    # Get the directory where this config file is located (detection/)
    current_dir = Path(__file__).parent.absolute()
    
    # Check if model is in detection/ directory
    model_path = current_dir / model_name
    if model_path.exists():
        return str(model_path)
    
    # Check if we're running from backend/ directory
    backend_dir = current_dir.parent
    model_path = backend_dir / 'detection' / model_name
    if model_path.exists():
        return str(model_path)
    
    # Check current working directory
    model_path = Path.cwd() / model_name
    if model_path.exists():
        return str(model_path)
    
    # Check detection subdirectory from cwd
    model_path = Path.cwd() / 'detection' / model_name
    if model_path.exists():
        return str(model_path)
    
    # Return default path (will fail gracefully with clear error)
    print(f"Warning: Model file '{model_name}' not found in expected locations.")
    print(f"Searched in:")
    print(f"  - {current_dir}")
    print(f"  - {backend_dir / 'detection'}")
    print(f"  - {Path.cwd()}")
    print(f"  - {Path.cwd() / 'detection'}")
    
    return str(current_dir / model_name)

# Model configuration
MODEL_PATHS = {
    'custom': get_model_path('best.pt'),
    'nano': get_model_path('yolo11n.pt'),
    'small': 'yolo11s.pt',
    'medium': 'yolo11m.pt',
    'large': 'yolo11l.pt',
    'xlarge': 'yolo11x.pt'
}

# Default model
DEFAULT_MODEL = 'custom'

if __name__ == "__main__":
    # Test the configuration
    print("Model Path Configuration:")
    print(f"Custom model (best.pt): {MODEL_PATHS['custom']}")
    print(f"File exists: {os.path.exists(MODEL_PATHS['custom'])}")