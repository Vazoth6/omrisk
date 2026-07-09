# src/main.py
import sys
import os

# Add src directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.camera.device_manager import select_camera
from src.camera.capture import capture_frames
from src.metrics.latency_tracker import latency_metrics, print_latency_summary
from src.metrics.metrics_collector import MetricsCollector
from src.metrics.reporters import MetricsReporter
from src.metrics.system_monitor import SystemMonitor  # NOVO
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
current_frame = [None]
frame_lock = threading.Lock()

# Shared T1 capture time between capture thread and WebSocket server
capture_t1_shared = [0.0]

# Shared FPS capture value (NOVO)
fps_capture_shared = [0.0]

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

# Global connected clients set
connected_clients = set()

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
        print("Python 3.7 or higher is required")
        return

    print("\nChecking for port conflicts...")
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
    print("\nSSL Certificate Check")
    print("-" * 40)
    if not check_certificates():
        generate_self_signed_cert()
    
    # ==========================================
    # START SYSTEM MONITOR (NOVO)
    # ==========================================
    print("\n📊 Starting System Monitor")
    print("-" * 40)
    system_monitor = SystemMonitor(interval=1.0, max_samples=120)
    system_monitor.start()
    
    # ==========================================
    # START CAMERA CAPTURE
    # ==========================================
    print("\nStarting Camera Capture")
    print("-" * 40)
    
    def capture_wrapper():
        capture_frames(camera_index, current_frame, frame_lock, latency_metrics, 
                      capture_t1_shared, fps_capture_shared)
    
    camera_thread = threading.Thread(
        target=capture_wrapper,
        daemon=True,
        name="Camera-Capture"
    )
    camera_thread.start()
    
    # Give camera time to initialize
    print("Waiting for camera to initialize...")
    time.sleep(2)
    
    # Wait for first frame
    print("Waiting for first frame...")
    frame_timeout = 10
    start_wait = time.time()
    frame_received = False
    
    while (time.time() - start_wait) < frame_timeout:
        with frame_lock:
            if current_frame[0] is not None:
                frame_received = True
                print(f"\nFirst frame received! Shape: {current_frame[0].shape}")
                break
        print(".", end="", flush=True)
        time.sleep(0.5)
    
    if not frame_received:
        print("\nNo frames received from camera after 10 seconds!")
        print("Check camera connection and permissions")
        return
    
    # ==========================================
    # START HTTP SERVER
    # ==========================================
    print("\nStarting HTTP Server")
    print("-" * 40)
    http_thread = threading.Thread(
        target=run_http_server,
        args=(HTTP_PORT, current_frame, frame_lock, connected_clients, 
              latency_metrics, html_content, system_monitor, fps_capture_shared),
        daemon=True,
        name="HTTP-Server"
    )
    http_thread.start()
    time.sleep(1)
    
    # ==========================================
    # START WEBSOCKET SERVER
    # ==========================================
    print("\nStarting WebSocket Server")
    print("-" * 40)
    ws_thread = threading.Thread(
        target=run_websocket_server,
        args=(WS_PORT, current_frame, frame_lock, connected_clients, 
              latency_metrics, capture_t1_shared),
        daemon=True,
        name="WebSocket-Server"
    )
    ws_thread.start()
    
    # Wait for servers to start
    time.sleep(2)
    
    # ==========================================
    # DISPLAY SERVER STATUS
    # ==========================================
    print("\n" + "="*60)
    print("SERVERS ARE RUNNING")
    print("="*60)
    print(f"\n📺 Open your browser and visit:")
    print(f"   https://{SERVER_IP}:{HTTP_PORT}")
    print(f"   or")
    print(f"   https://localhost:{HTTP_PORT}")
    
    print("\n📊 Available endpoints:")
    print(f"   - /         - Streaming dashboard")
    print(f"   - /debug    - Camera debug view")
    print(f"   - /health   - System health status")
    print(f"   - /metrics  - Latency metrics (JSON) - INCLUDES CPU/RAM/FPS")
    
    print("\n📈 Latency metrics will be displayed:")
    print("   📷 T1 - Capture time (camera to memory)")
    print("   📏 T2 - Resize time (image scaling)")
    print("   🗜️ T3 - Encode time (JPEG compression)")
    print("   ⚙️ T4 - Total server processing (T1+T2+T3)")
    print("   📤 T5 - Network send time (WebSocket transmission)")
    print("   🌐 T6 - Network receive time (client)")
    print("   🔓 T7 - Decode time (JPEG → bitmap)")
    print("   🤖 T8 - YOLO inference time")
    print("   🎨 T9 - Overlay draw time")
    print("   🖥️ T10 - Display render time")
    print("   📊 TOTAL - End-to-end latency")
    
    print("\n📊 System metrics:")
    print("   💻 CPU: Average and peak usage")
    print("   🧠 RAM: Average and peak usage")
    print("   🎬 FPS: Capture and transmission rates")
    
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
                
            # Display status with T1 and FPS values
            with frame_lock:
                frame_status = "Active" if current_frame[0] is not None else "No frame"
            
            current_t1 = capture_t1_shared[0] if capture_t1_shared[0] > 0 else 0
            current_fps = fps_capture_shared[0] if fps_capture_shared else 0
            
            # Get system stats
            stats = system_monitor.get_stats()
            cpu = stats['cpu']['current']
            ram = stats['ram']['current']
            
            print(f"\r📊 Status: Camera: {frame_status} | "
                  f"T1: {current_t1:.1f}ms | "
                  f"FPS: {current_fps:.1f} | "
                  f"CPU: {cpu:.1f}% | "
                  f"RAM: {ram:.0f}MB | "
                  f"Clients: {len(connected_clients)} | "
                  f"Press Ctrl+C to stop", end="")
                  
    except KeyboardInterrupt:
        print("\n\n" + "="*60)
        print("🛑 Shutting down servers...")
        print("="*60)
        
        # ==========================================
        # PRINT FINAL STATISTICS
        # ==========================================
        print("\n📊 FINAL LATENCY SUMMARY:")
        print_latency_summary()
        
        print("\n📈 OVERALL AVERAGES:")
        metric_names = {
            't1_capture': 'T1 Capture',
            't2_resize': 'T2 Resize',
            't3_encode': 'T3 Encode',
            't4_total_server': 'T4 Server Total',
            't5_network_send': 'T5 Network Send',
            't2_processing': 'Processing (Legacy)'
        }
        
        for metric_key, metric_name in metric_names.items():
            if metric_key in latency_metrics and latency_metrics[metric_key]:
                values = latency_metrics[metric_key]
                avg = sum(values) / len(values)
                print(f"{metric_name:20s}: {avg:6.2f}ms ({len(values)} samples)")
        
        # ==========================================
        # PRINT SYSTEM STATISTICS (NOVO)
        # ==========================================
        stats = system_monitor.get_stats()
        print("\n📊 SYSTEM STATISTICS:")
        print(f"  CPU Average: {stats['cpu']['avg']:.1f}%")
        print(f"  CPU Peak:    {stats['cpu']['max']:.1f}%")
        print(f"  RAM Average: {stats['ram']['avg']:.1f} MB")
        print(f"  RAM Peak:    {stats['ram']['max']:.1f} MB")
        print(f"  RAM Total:   {stats['ram']['total_mb']:.1f} MB")
        print(f"  Samples:     {stats['cpu']['samples']}")
        
        print(f"\n  FPS Capture:    {fps_capture_shared[0]:.1f}")
        
        # Cleanup
        with frame_lock:
            current_frame[0] = None
        
        system_monitor.stop()
        
        print("\n✅ All servers stopped. Goodbye!")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Unexpected error in main loop: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    required_packages = [
        "websockets",
        "opencv-python",
        "numpy",
        "psutil"  # NOVO
    ]
    
    print("Required Python packages:")
    for pkg in required_packages:
        print(f"  • {pkg}")
    
    print("\nInstall with:")
    print("  sudo apt install python3-psutil  # For psutil")
    print("  pip install websockets opencv-python numpy  # In virtual environment")
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
        print(f"\nErro fatal: {e}")
        import traceback
        traceback.print_exc()