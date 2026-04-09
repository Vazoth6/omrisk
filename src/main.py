import sys
import threading
import time
from pathlib import Path

# Add src to path if needed
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import config
from src.camera.device_manager import CameraDeviceManager
from src.camera.capture import CameraCapture
from src.metrics.latency_tracker import LatencyTracker
from src.server.http_server import HTTPServer
from src.server.websocket_server import WebSocketServer
from src.utils.logger import setup_logger
from src.utils.ssl_helper import setup_ssl

logger = setup_logger(__name__)

class VideoStreamingSystem:
    def __init__(self):
        self.latency_tracker = LatencyTracker()
        self.camera = None
        self.http_server = None
        self.ws_server = None
        
    def initialize_camera(self):
        """Select and initialize camera"""
        camera_id = CameraDeviceManager.select_camera()
        if camera_id is None:
            logger.error("No camera selected")
            return False
        
        self.camera = CameraCapture(camera_id, self.latency_tracker)
        return True
    
    def start(self):
        """Start all components"""
        print(f"\n{'='*60}")
        print(f"Video Streaming System v1.0")
        print(f"{'='*60}")
        print(f"Server IP: {config.SERVER_IP}")
        print(f"HTTP Port: {config.HTTP_PORT}")
        print(f"WebSocket Port: {config.WS_PORT}")
        print(f"{'='*60}\n")
        
        # Start camera
        if not self.initialize_camera():
            return
        
        self.camera.start()
        logger.info("✅ Camera started")
        
        # Setup SSL
        ssl_context = setup_ssl()
        
        # Start HTTP server
        self.http_server = HTTPServer(config, ssl_context)
        http_thread = threading.Thread(target=self.http_server.start, daemon=True)
        http_thread.start()
        logger.info(f"✅ HTTP server started on https://{config.SERVER_IP}:{config.HTTP_PORT}")
        
        # Start WebSocket server
        self.ws_server = WebSocketServer(config, self.camera, self.latency_tracker, ssl_context)
        ws_thread = threading.Thread(target=self.ws_server.start, daemon=True)
        ws_thread.start()
        logger.info(f"✅ WebSocket server started on port {config.WS_PORT}")
        
        print(f"\n📺 Open browser: https://{config.SERVER_IP}:{config.HTTP_PORT}")
        print("Press Ctrl+C to stop\n")
        
        # Keep alive and print metrics
        try:
            last_summary = time.time()
            while True:
                time.sleep(1)
                if time.time() - last_summary >= config.SUMMARY_INTERVAL:
                    self.latency_tracker.print_summary()
                    last_summary = time.time()
        except KeyboardInterrupt:
            print("\n🛑 Shutting down...")
            self.stop()
    
    def stop(self):
        """Stop all components"""
        if self.camera:
            self.camera.stop()
        if self.http_server:
            self.http_server.stop()
        if self.ws_server:
            self.ws_server.stop()
        logger.info("System stopped")

def main():
    system = VideoStreamingSystem()
    system.start()

if __name__ == "__main__":
    main()