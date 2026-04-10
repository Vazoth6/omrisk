# src/camera/__init__.py
"""
Camera module for video capture and processing
"""

from .device_manager import list_cameras, select_camera
from .capture import capture_frames
from .frame_processor import process_frame, add_timestamp_to_frame

__all__ = [
    'list_cameras',
    'select_camera', 
    'capture_frames',
    'process_frame',
    'add_timestamp_to_frame',
    'get_frame_info'
]