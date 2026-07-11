# src/server/handlers.py
import json
import time
import cv2
from http.server import BaseHTTPRequestHandler
from src.web import get_static_file, get_mime_type

# Global variables for handler context
_handler_context = {}

def set_handler_context(current_frame, frame_lock, connected_clients, latency_metrics, 
                        html_content, system_monitor=None, fps_capture_shared=None,
                        fps_transmission_shared=None):
    """Set the global context for the handler"""
    global _handler_context
    _handler_context = {
        'current_frame': current_frame,
        'frame_lock': frame_lock,
        'connected_clients': connected_clients,
        'latency_metrics': latency_metrics,
        'html_content': html_content,
        'system_monitor': system_monitor,
        'fps_capture_shared': fps_capture_shared,
        'fps_transmission_shared': fps_transmission_shared  # NEW
    }

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    """Custom HTTP request handler for streaming dashboard"""
    
    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            html_content = _handler_context.get('html_content')
            if html_content:
                self.wfile.write(html_content.encode("utf-8"))
            else:
                self.wfile.write(b"<h1>HTML content not loaded</h1><p>Debug: html_content is None</p>")
            return

        elif self.path.startswith('/static/'):
            filepath = self.path[8:]
            content = get_static_file(filepath)
            if content:
                self.send_response(200)
                self.send_header("Content-type", get_mime_type(filepath))
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_error(404, "Static file not found")
            return

        elif self.path == "/debug":
            self.send_response(200)
            current_frame_container = _handler_context.get('current_frame')
            frame_lock = _handler_context.get('frame_lock')
            
            if current_frame_container is not None and frame_lock:
                with frame_lock:
                    if isinstance(current_frame_container, list):
                        frame = current_frame_container[0]
                    else:
                        frame = current_frame_container
                    
                    if frame is not None:
                        _, buffer = cv2.imencode('.jpg', frame)
                        self.send_header("Content-type", "image/jpeg")
                        self.end_headers()
                        self.wfile.write(buffer.tobytes())
                    else:
                        self.send_header("Content-type", "text/html")
                        self.end_headers()
                        self.wfile.write(b"<h1>No frame available (frame is None)</h1>")
            else:
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h1>No frame available</h1>")
            return
                
        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            
            current_frame_container = _handler_context.get('current_frame')
            frame_exists = False
            if current_frame_container is not None:
                if isinstance(current_frame_container, list):
                    frame_exists = current_frame_container[0] is not None
                else:
                    frame_exists = current_frame_container is not None
            
            health_data = {
                "status": "running",
                "camera": frame_exists,
                "clients": len(_handler_context.get('connected_clients', set())),
                "timestamp": time.time(),
                "latency_samples": {k: len(v) for k, v in _handler_context.get('latency_metrics', {}).items()}
            }
            self.wfile.write(json.dumps(health_data).encode())
            return
            
        elif self.path == "/metrics":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            
            # ==========================================
            # LATENCY METRICS
            # ==========================================
            metrics_stats = {}
            latency_metrics = _handler_context.get('latency_metrics', {})
            for metric, values in latency_metrics.items():
                if values:
                    metrics_stats[metric] = {
                        "samples": len(values),
                        "avg": round(sum(values) / len(values), 2),
                        "min": round(min(values), 2),
                        "max": round(max(values), 2),
                        "last_10_avg": round(sum(values[-10:]) / min(10, len(values)), 2) if values else 0
                    }
            
            current_frame_container = _handler_context.get('current_frame')
            frame_exists = False
            if current_frame_container is not None:
                if isinstance(current_frame_container, list):
                    frame_exists = current_frame_container[0] is not None
                else:
                    frame_exists = current_frame_container is not None
            
            # ==========================================
            # SYSTEM METRICS
            # ==========================================
            system_stats = {}
            system_monitor = _handler_context.get('system_monitor')
            if system_monitor:
                system_stats = system_monitor.get_stats()
            
            # ==========================================
            # FPS METRICS (UPDATED)
            # ==========================================
            fps_capture = 0
            fps_capture_shared = _handler_context.get('fps_capture_shared')
            if fps_capture_shared and isinstance(fps_capture_shared, list):
                fps_capture = round(fps_capture_shared[0], 1)
            
            fps_transmission = 0
            fps_transmission_shared = _handler_context.get('fps_transmission_shared')
            if fps_transmission_shared and isinstance(fps_transmission_shared, list):
                fps_transmission = round(fps_transmission_shared[0], 1)
            
            # ==========================================
            # BUILD RESPONSE
            # ==========================================
            metrics_data = {
                "timestamp": time.time(),
                "metrics": metrics_stats,
                "system": system_stats,
                "fps": {
                    "capture": fps_capture,
                    "transmission": fps_transmission  # NEW
                },
                "connected_clients": len(_handler_context.get('connected_clients', set())),
                "current_frame": frame_exists
            }
            self.wfile.write(json.dumps(metrics_data, indent=2).encode())
            return
        else:
            self.send_error(404, "Not Found")
    
    def log_message(self, format, *args):
        pass

def create_handler_with_context(current_frame, frame_lock, connected_clients, latency_metrics, 
                                html_content, system_monitor=None, fps_capture_shared=None,
                                fps_transmission_shared=None):
    """Create a handler with the required context"""
    set_handler_context(current_frame, frame_lock, connected_clients, latency_metrics, 
                        html_content, system_monitor, fps_capture_shared, 
                        fps_transmission_shared)
    return SimpleHTTPRequestHandler