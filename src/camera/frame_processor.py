# src/camera/frame_processor.py
import cv2
import numpy as np
from typing import Optional

def add_timestamp_to_frame(frame: np.ndarray, timestamp_ns: int) -> np.ndarray:
    """Add timestamp as text overlay to frame"""
    frame_copy = frame.copy()
    timestamp_ms = timestamp_ns // 1_000_000
    cv2.putText(frame_copy, f"TS:{timestamp_ms}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    return frame_copy

def process_frame(frame: np.ndarray, max_dimension: int = 1280, 
                  quality: int = 70, add_timestamp: bool = True, 
                  timestamp_ns: Optional[int] = None) -> tuple:
    """
    Process a frame: resize, add timestamp, and encode to JPEG
    
    Args:
        frame: Input frame as numpy array
        max_dimension: Maximum dimension for resizing
        quality: JPEG quality (0-100)
        add_timestamp: Whether to add timestamp overlay
        timestamp_ns: Timestamp in nanoseconds (if None, uses current time)
    
    Returns:
        tuple: (encoded_buffer, processing_time_ms, frame_with_ts)
    """
    import time
    
    # Resize frame for better performance
    height, width = frame.shape[:2]
    if width > max_dimension:
        scale = max_dimension / width
        new_width = max_dimension
        new_height = int(height * scale)
        frame_resized = cv2.resize(frame, (new_width, new_height))
    else:
        frame_resized = frame
    
    # Add timestamp if requested
    if add_timestamp:
        if timestamp_ns is None:
            timestamp_ns = int(time.time() * 1_000_000_000)
        frame_with_ts = add_timestamp_to_frame(frame_resized, timestamp_ns)
    else:
        frame_with_ts = frame_resized
    
    # Encode to JPEG
    encode_start = time.perf_counter_ns()
    _, buffer = cv2.imencode('.jpg', frame_with_ts, 
                             [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    encode_end = time.perf_counter_ns()
    
    processing_time = (encode_end - encode_start) / 1_000_000  # Convert to ms
    
    return buffer, processing_time, frame_with_ts

def get_frame_info(frame: np.ndarray) -> dict:
    """Get information about a frame"""
    if frame is None:
        return {'valid': False}
    
    return {
        'valid': True,
        'shape': frame.shape,
        'width': frame.shape[1],
        'height': frame.shape[0],
        'channels': frame.shape[2] if len(frame.shape) > 2 else 1,
        'dtype': str(frame.dtype),
        'size_bytes': frame.nbytes
    }