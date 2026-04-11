# src/server/handlers.py
import json
import time
import cv2
from http.server import BaseHTTPRequestHandler
from src.web import get_static_file, get_mime_type

# Global variables for handler context (simpler approach)
_handler_context = {}

def set_handler_context(current_frame, frame_lock, connected_clients, latency_metrics, html_content):
    """Set the global context for the handler"""
    global _handler_context
    _handler_context = {
        'current_frame': current_frame,
        'frame_lock': frame_lock,
        'connected_clients': connected_clients,
        'latency_metrics': latency_metrics,
        'html_content': html_content
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
            current_frame = _handler_context.get('current_frame')
            frame_lock = _handler_context.get('frame_lock')
            
            if current_frame is not None and frame_lock:
                with frame_lock:
                    _, buffer = cv2.imencode('.jpg', current_frame)
                    self.send_header("Content-type", "image/jpeg")
                    self.end_headers()
                    self.wfile.write(buffer.tobytes())
            else:
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h1>No frame available</h1>")
            return
                
        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            health_data = {
                "status": "running",
                "camera": _handler_context.get('current_frame') is not None,
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
            
            metrics_stats = {}
            latency_metrics = _handler_context.get('latency_metrics', {})
            for metric, values in latency_metrics.items():
                if values:
                    metrics_stats[metric] = {
                        "samples": len(values),
                        "avg": sum(values) / len(values),
                        "min": min(values),
                        "max": max(values),
                        "last_10_avg": sum(values[-10:]) / min(10, len(values)) if values else 0
                    }
            
            metrics_data = {
                "timestamp": time.time(),
                "metrics": metrics_stats,
                "connected_clients": len(_handler_context.get('connected_clients', set())),
                "current_frame": _handler_context.get('current_frame') is not None
            }
            self.wfile.write(json.dumps(metrics_data, indent=2).encode())
            return
        else:
            self.send_error(404, "Not Found")
    
    def log_message(self, format, *args):
        pass

def create_handler_with_context(current_frame, frame_lock, connected_clients, latency_metrics, html_content):
    """Create a handler with the required context"""
    set_handler_context(current_frame, frame_lock, connected_clients, latency_metrics, html_content)
    return SimpleHTTPRequestHandler