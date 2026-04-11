import sys
import os

# Add src directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import from the refactored modules
from src.camera.device_manager import select_camera, list_cameras
from src.camera.capture import capture_frames
from src.metrics.latency_tracker import latency_metrics, print_latency_summary
from src.metrics.metrics_collector import MetricsCollector
from src.metrics.reporters import MetricsReporter
from src.server.http_server import run_http_server
from src.server.streaming_server import run_websocket_server
from src.utils.network import get_ip_address, check_port_available, get_system_info
from src.utils.ssl_helper import generate_self_signed_cert, check_certificates
from src.utils.logger import setup_logger
from src.web import get_html_content

import threading
import time
import socket
import platform
import cv2
import numpy as np
from typing import Optional

# Global frame storage (shared between threads) - USING LIST FOR MUTABILITY
current_frame = [None]  # List wrapper for thread-safe updates
frame_lock = threading.Lock()

# Configuration
SERVER_IP = get_ip_address()
HTTP_PORT = 8000
WS_PORT = 3001

# Setup logger
logger = setup_logger(__name__)

html_content = get_html_content()

# Initialize metrics components
metrics_collector = MetricsCollector(max_history=1000)
metrics_reporter = MetricsReporter(auto_print=True, print_interval=10)

def main():
    global current_frame

    print("\n" + "="*60)
    print("OMRISK VIDEO STREAMING SERVER WITH LATENCY MEASUREMENT")
    print("="*60)
    print(f"Version: 1.0.0")
    sys_info = get_system_info()
    print(f"Server IP: {sys_info['ip_address']}")
    print(f"Hostname: {sys_info['hostname']}")
    print(f"Platform: {sys_info['platform']}")
    print(f"Python: {sys_info['python_version']}")
    
    # Check Python version
    if sys.version_info < (3, 7):
        print("❌ Python 3.7 or higher is required")
        return

    print("\n🔍 Checking for port conflicts...")
    if not check_port_available(3001, '127.0.0.1'):
        print("⚠️  Port 3001 is already in use!")
        print("   The server will try alternative ports (3002, 3003, etc.)")
    
    # Select camera
    print("\n📷 Camera Selection")
    print("-" * 40)
    camera_index = select_camera()
    if camera_index is None:
        print("No camera selected. Exiting.")
        return
    
    # Check for required certificates
    print("\n🔐 SSL Certificate Check")
    print("-" * 40)
    if not check_certificates():
        generate_self_signed_cert()
    
    # Start camera capture in a separate thread
    print("\n🎥 Starting Camera Capture")
    print("-" * 40)
    
    def capture_wrapper():
        capture_frames(camera_index, current_frame, frame_lock, latency_metrics)
    
    camera_thread = threading.Thread(
        target=capture_wrapper,
        daemon=True,
        name="Camera-Capture"
    )
    camera_thread.start()
    
    # Give camera time to initialize
    print("Waiting for camera to initialize...")
    time.sleep(2)
    
    # CRITICAL: Wait for first frame
    print("Waiting for first frame...")
    frame_timeout = 10
    start_wait = time.time()
    frame_received = False
    
    while (time.time() - start_wait) < frame_timeout:
        with frame_lock:
            if current_frame[0] is not None:
                frame_received = True
                print(f"\n✅ First frame received! Shape: {current_frame[0].shape}")
                break
        print(".", end="", flush=True)
        time.sleep(0.5)
    
    if not frame_received:
        print("\n❌ No frames received from camera after 10 seconds!")
        print("Check camera connection and permissions")
        return
    
    # Start HTTP server in thread
    print("\n🌐 Starting HTTP Server")
    print("-" * 40)
    http_thread = threading.Thread(
        target=run_http_server,
        args=(HTTP_PORT, current_frame, frame_lock, connected_clients, latency_metrics, html_content),
        daemon=True,
        name="HTTP-Server"
    )
    http_thread.start()
    time.sleep(1)
    
    # Start WebSocket server in separate thread
    print("\n🔄 Starting WebSocket Server")
    print("-" * 40)
    ws_thread = threading.Thread(
        target=run_websocket_server,
        args=(WS_PORT, current_frame, frame_lock, connected_clients, latency_metrics),
        daemon=True,
        name="WebSocket-Server"
    )
    ws_thread.start()
    
    # Wait for servers to start
    time.sleep(2)
    
    # Display server status
    print("\n" + "="*60)
    print("✅ SERVERS ARE RUNNING")
    print("="*60)
    print(f"\n📺 Open your browser and visit:")
    print(f"   https://{SERVER_IP}:{HTTP_PORT}")
    print(f"   or")
    print(f"   https://localhost:{HTTP_PORT}")
    
    print("\n📊 Available endpoints:")
    print(f"   • /         - Streaming dashboard")
    print(f"   • /debug    - Camera debug view")
    print(f"   • /health   - System health status")
    print(f"   • /metrics  - Latency metrics (JSON)")
    
    print("\n📈 Latency metrics will be displayed:")
    print("   • T1 - Capture time (camera to memory)")
    print("   • T2 - Processing time (resize + encode)")
    print("   • T3 - Network time (server → client)")
    print("   • T4 - Decoding time (JPEG → bitmap)")
    print("   • T5 - Rendering time (canvas draw)")
    print("   • TOTAL - Sum of all components")
    
    print("\n🛑 Press Ctrl+C to stop all servers")
    print("="*60)
    
    # Print initial metrics
    time.sleep(1)
    print_latency_summary()
    
    # Keep main thread alive and print periodic summaries
    try:
        last_summary_time = time.time()
        while True:
            time.sleep(1)
            
            # Print summary every 10 seconds
            current_time = time.time()
            if current_time - last_summary_time >= 10:
                print_latency_summary()
                last_summary_time = current_time
                
            # Display status
            with frame_lock:
                frame_status = "Active" if current_frame[0] is not None else "No frame"
            
            print(f"\r📊 Status: Camera: {frame_status} | Clients: {len(connected_clients)} | "
                  f"Frames: {len(latency_metrics['t1_capture'])} | Press Ctrl+C to stop", end="")
                  
    except KeyboardInterrupt:
        print("\n\n" + "="*60)
        print("🛑 Shutting down servers...")
        print("="*60)
        
        # Print final summary
        print("\n📊 FINAL LATENCY SUMMARY:")
        print_latency_summary()
        
        # Calculate and print averages
        print("\n📈 OVERALL AVERAGES:")
        for metric, values in latency_metrics.items():
            if values:
                avg = sum(values) / len(values)
                print(f"{metric.upper():15s}: {avg:6.2f}ms ({len(values)} samples)")
        
        # Cleanup
        with frame_lock:
            current_frame[0] = None
        
        print("\n✅ All servers stopped. Goodbye!")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Unexpected error in main loop: {e}")
        import traceback
        traceback.print_exc()

# Global connected clients set (needed for the servers)
connected_clients = set()

if __name__ == "__main__":
    # Required packages installation reminder
    required_packages = [
        "websockets",
        "opencv-python",
        "numpy"
    ]
    
    print("Required Python packages:")
    for pkg in required_packages:
        print(f"  • {pkg}")
    
    print("\nInstall with: pip install websockets opencv-python numpy")
    print("="*60)
    
    # Check for V4L2 utilities
    print("\n🔍 Checking for V4L2 utilities...")
    if os.system("which v4l2-ctl > /dev/null 2>&1") != 0:
        print("⚠️  v4l2-ctl not found. Install with: sudo apt install v4l-utils")
    else:
        print("✅ v4l2-ctl is available")
    
    # Check for port conflicts
    print("\n🔍 Checking for port conflicts...")
    try:
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.settimeout(1)
        result = test_socket.connect_ex(('127.0.0.1', 3001))
        if result == 0:
            print("⚠️  Port 3001 is already in use!")
            print("   The server will try alternative ports (3002, 3003, etc.)")
        test_socket.close()
    except:
        pass
    
    try:
        main()
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()