# src/server/http_server.py
import ssl
import os
from http.server import HTTPServer
from .handlers import create_handler_with_context
from src.utils.ssl_helper import generate_self_signed_cert

def run_http_server(http_port, current_frame, frame_lock, connected_clients, latency_metrics, html_content):
    """Run HTTP server with SSL"""
    server_address = ('0.0.0.0', http_port)  # Listen on all interfaces
    
    # Create handler with context
    handler_class = create_handler_with_context(
        current_frame, frame_lock, connected_clients, latency_metrics, html_content
    )
    
    httpd = HTTPServer(server_address, handler_class)
    
    # SSL wrapping
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    
    # Try to load certificates
    cert_file = "certs/certTwo.pem"
    key_file = "certs/keyTwo.pem"
    
    if not os.path.exists(cert_file):
        print(f"\n❌ Certificate file '{cert_file}' not found!")
        print("Generating self-signed certificate...")
        generate_self_signed_cert()
    
    try:
        context.load_cert_chain(certfile=cert_file, keyfile=key_file)
        httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
        
        # Get server IP for display
        from src.utils.network import get_ip_address
        server_ip = get_ip_address()
        
        print(f"\n✅ HTTPS server: Running at https://{server_ip}:{http_port}")
        print(f"   Also available at: https://localhost:{http_port}")
        print(f"   Metrics endpoint: https://{server_ip}:{http_port}/metrics")
        httpd.serve_forever()
    except Exception as e:
        print(f"❌ Failed to start HTTPS server: {e}")
        raise