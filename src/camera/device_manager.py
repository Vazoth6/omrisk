# src/camera/device_manager.py
import cv2
import os

def list_cameras():
    """List available cameras on Linux using V4L2"""
    cameras = []
    
    print("Scanning for cameras using V4L2...")
    
    # Check common V4L2 device paths
    v4l2_devices = [
        '/dev/video0', '/dev/video1', '/dev/video2', '/dev/video3',
        '/dev/video4', '/dev/video5', '/dev/video6', '/dev/video7'
    ]
    
    for device_path in v4l2_devices:
        if os.path.exists(device_path):
            try:
                # Try to open with V4L2 backend
                cap = cv2.VideoCapture(device_path, cv2.CAP_V4L2)
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        # Get camera properties
                        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        fps = cap.get(cv2.CAP_PROP_FPS)
                        
                        camera_name = f"{device_path} ({width}x{height}, {fps:.1f} FPS)"
                        cameras.append((device_path, camera_name))
                        print(f"Found: {camera_name}")
                    
                    cap.release()
                    cv2.destroyAllWindows()
            except Exception as e:
                print(f"Error testing {device_path}: {e}")
                continue
    
    # Fallback: try numeric indices with V4L2
    if not cameras:
        print("Trying numeric indices with V4L2...")
        for index in range(0, 10):
            try:
                cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        fps = cap.get(cv2.CAP_PROP_FPS)
                        
                        camera_name = f"Camera {index} ({width}x{height}, {fps:.1f} FPS)"
                        cameras.append((index, camera_name))
                        print(f"Found: {camera_name}")
                    
                    cap.release()
                    cv2.destroyAllWindows()
            except Exception as e:
                print(f"Error testing camera {index}: {e}")
                continue
    
    return cameras

def select_camera():
    """Let user select which camera to use"""
    cameras = list_cameras()
    
    if not cameras:
        print("\n❌ No cameras found!")
        print("\nTroubleshooting steps:")
        print("1. Make sure your webcam is connected")
        print("2. Check if V4L2 is installed: sudo apt install v4l-utils")
        print("3. List devices: v4l2-ctl --list-devices")
        print("4. Check permissions: ls -la /dev/video*")
        return None
    
    print(f"\n✅ Found {len(cameras)} camera(s):")
    for idx, (cam_index, cam_name) in enumerate(cameras):
        print(f"{idx + 1}. {cam_name}")
    
    if len(cameras) == 1:
        print(f"\nUsing the only available camera: {cameras[0][1]}")
        return cameras[0][0]
    
    while True:
        try:
            choice = input(f"\nSelect a camera (1-{len(cameras)}) or 'q' to quit: ")
            if choice.lower() == 'q':
                return None
            choice = int(choice)
            if 1 <= choice <= len(cameras):
                selected_index = cameras[choice - 1][0]
                print(f"Selected: {cameras[choice - 1][1]}")
                return selected_index
            print("Invalid choice. Please try again.")
        except ValueError:
            print("Please enter a number.")