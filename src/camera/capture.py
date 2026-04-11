# src/camera/capture.py
import cv2
import time
import numpy as np
from typing import Optional

def capture_frames(camera_index, current_frame, frame_lock, latency_metrics):
    """
    Capture frames from the selected camera with latency measurement
    
    Args:
        camera_index: Camera index or device path
        current_frame: List containing the global frame (mutability fix)
        frame_lock: Lock for thread-safe frame access
        latency_metrics: Dictionary to store latency metrics
    """
    print(f"\nInitializing camera {camera_index}...")
    
    # Use V4L2 for Linux
    if isinstance(camera_index, str) and camera_index.startswith('/dev/video'):
        # It's a device path
        cap = cv2.VideoCapture(camera_index, cv2.CAP_V4L2)
    else:
        # It's a numeric index
        cap = cv2.VideoCapture(camera_index, cv2.CAP_V4L2)
    
    if not cap.isOpened():
        print(f"❌ Error: Could not open camera {camera_index}")
        print("Try selecting a different camera")
        return
    
    # Try to set optimal properties for V4L2
    try:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cap.set(cv2.CAP_PROP_FPS, 30)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    except Exception as e:
        print(f"Note: Using default camera settings ({e})")
    
    # Get actual camera properties
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    print(f"Camera settings: {width}x{height} at {fps:.1f} FPS")
    print("Press Ctrl+C in the terminal to stop capturing")
    
    frame_count = 0
    start_time = time.time()
    last_print_time = time.time()
    
    try:
        while True:
            # Measure T1: Capture latency
            t1_start = time.perf_counter_ns()
            ret, frame = cap.read()
            t1_end = time.perf_counter_ns()
            
            if not ret:
                print("Error: Could not read frame")
                time.sleep(0.1)
                continue
            
            # Calculate T1 in milliseconds
            t1_capture = (t1_end - t1_start) / 1_000_000
            
            # CRITICAL FIX: Store frame with lock using list index assignment
            with frame_lock:
                # Since current_frame is a list, assign to index 0
                current_frame[0] = frame.copy()
            
            # Store T1 metric
            latency_metrics['t1_capture'].append(t1_capture)
            
            frame_count += 1
            
            # Print periodic status
            current_time = time.time()
            if current_time - last_print_time >= 2:
                elapsed = current_time - start_time
                fps_calc = frame_count / elapsed
                
                print(f"\n📊 Capture Status:")
                print(f"  Frames: {frame_count} | FPS: {fps_calc:.1f}")
                print(f"  Frame size: {frame.shape[1]}x{frame.shape[0]}")
                print(f"  T1 Capture (last): {t1_capture:.2f}ms")
                
                # Verify frame was stored correctly
                with frame_lock:
                    if current_frame[0] is not None:
                        print(f"  Frame stored successfully in list container")
                    else:
                        print(f"  WARNING: Frame storage failed!")
                
                if latency_metrics['t1_capture']:
                    avg_t1 = sum(latency_metrics['t1_capture'][-10:]) / min(10, len(latency_metrics['t1_capture']))
                    print(f"  T1 Avg (last 10): {avg_t1:.2f}ms")
                
                last_print_time = current_time
            
            # Small delay to prevent CPU overuse
            time.sleep(max(0, (1.0/fps) - 0.005))  # Aim for target FPS
            
    except KeyboardInterrupt:
        print("\nCapture stopped by user")
    except Exception as e:
        print(f"Error in capture loop: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("Camera released")