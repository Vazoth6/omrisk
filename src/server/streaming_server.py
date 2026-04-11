# src/server/streaming_server.py
import asyncio
import json
import time
import ssl
import os
import websockets
import cv2
import numpy as np
from typing import Set, Optional
from src.camera.frame_processor import add_timestamp_to_frame

# Global metrics storage will be passed from main
connected_clients = set()

async def ws_handler(websocket, current_frame, frame_lock, latency_metrics, connected_clients):
    """WebSocket handler with latency measurement"""
    print(f"New client connected from {websocket.remote_address}!")
    connected_clients.add(websocket)
    client_metrics = {
        'frame_count': 0,
        'last_print_time': time.time()
    }
    
    try:
        async for message in websocket:
            data = json.loads(message)
            
            if data.get("type") == "request_frame":
                with frame_lock:
                    if current_frame is not None:
                        # Start timing for T2 (server processing)
                        t2_start = time.perf_counter_ns()
                        
                        # Get current timestamp in milliseconds
                        server_timestamp_ms = int(time.time() * 1000)
                        
                        # Resize frame for better performance
                        height, width = current_frame.shape[:2]
                        max_dimension = 1280
                        if width > max_dimension:
                            scale = max_dimension / width
                            new_width = max_dimension
                            new_height = int(height * scale)
                            frame_resized = cv2.resize(current_frame, (new_width, new_height))
                        else:
                            frame_resized = current_frame
                        
                        # Add timestamp to frame
                        frame_with_ts = add_timestamp_to_frame(frame_resized, server_timestamp_ms * 1_000_000)
                        
                        # Encode to JPEG
                        encode_start = time.perf_counter_ns()
                        _, buffer = cv2.imencode('.jpg', frame_with_ts, 
                                                 [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                        encode_end = time.perf_counter_ns()
                        
                        # Calculate T2 processing time
                        t2_processing = (encode_end - t2_start) / 1_000_000  # ms
                        
                        # Add metadata with timestamps
                        metadata = {
                            'server_timestamp_ms': server_timestamp_ms,
                            't1_capture': data.get('t1_capture', 0),
                            't2_processing': t2_processing,
                            'frame_index': client_metrics['frame_count']
                        }
                        
                        # Create combined message with metadata
                        combined_data = {
                            'metadata': metadata,
                            'image_data': buffer.tobytes().hex()  # Send as hex string
                        }
                        
                        # Send to client
                        await websocket.send(json.dumps(combined_data))
                        
                        # Update metrics
                        latency_metrics['t2_processing'].append(t2_processing)
                        
                        # Print periodic summary
                        client_metrics['frame_count'] += 1
                        current_time = time.time()
                        if current_time - client_metrics['last_print_time'] >= 5:
                            from src.metrics.latency_tracker import print_latency_summary
                            print_latency_summary()
                            client_metrics['last_print_time'] = current_time
                            
                    else:
                        print("WARNING: current_frame is None!")
                        
            elif data.get("type") == "latency_report":
                # Client sends back latency measurements
                report = data.get("data", {})
                
                # Store all metrics
                for metric in ['t1_capture', 't3_network', 't4_decoding', 't5_rendering', 'total']:
                    if metric in report:
                        latency_metrics[metric].append(report[metric])
                
                # Print individual frame latency
                print(f"\n📊 Frame {report.get('frame_index', 0)} Latency:")
                print(f"  T1 Capture:     {report.get('t1_capture', 0):6.2f}ms")
                print(f"  T2 Processing:  {report.get('t2_processing', 0):6.2f}ms")
                print(f"  T3 Network:     {report.get('t3_network', 0):6.2f}ms")
                print(f"  T4 Decoding:    {report.get('t4_decoding', 0):6.2f}ms")
                print(f"  T5 Rendering:   {report.get('t5_rendering', 0):6.2f}ms")
                print(f"  TOTAL:          {report.get('total', 0):6.2f}ms")
                
    except websockets.exceptions.ConnectionClosed as e:
        print(f"Client disconnected: {e}")
    except Exception as e:
        print(f"Error in ws_handler: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if websocket in connected_clients:
            connected_clients.remove(websocket)

async def start_websocket_server(ws_port, current_frame, frame_lock, latency_metrics, connected_clients):
    """Start WebSocket server"""
    print(f"\nStarting WebSocket server on port {ws_port}...")
    
    try:
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)

        cert_path = "certs/certTwo.pem"
        key_path = "certs/keyTwo.pem"
        
        if os.path.exists(cert_path) and os.path.exists(key_path):
            ssl_context.load_cert_chain(certfile=cert_path, keyfile=key_path)
            print("✅ Encryption: SSL certificate loaded successfully")
            use_ssl = ssl_context
        else:
            print(f"⚠️  Warning: Certificates not found at {cert_path} and {key_path}")
            print("⚠️  Warning: Running WebSocket without SSL (ws://)")
            print("   Browser may block mixed content (https + ws)")
            use_ssl = None
        
        # Try to start on the default port, if busy try alternative ports
        port_to_use = ws_port
        max_retries = 5
        
        for attempt in range(max_retries):
            try:
                # Create handler with context
                async def handler(websocket, path):
                    await ws_handler(websocket, current_frame, frame_lock, latency_metrics, connected_clients)
                
                async with websockets.serve(
                    handler, 
                    '0.0.0.0',  # Listen on all interfaces
                    port_to_use, 
                    ssl=use_ssl,
                    ping_interval=20,
                    ping_timeout=40,
                    max_size=10 * 1024 * 1024  # 10MB max message size
                ):
                    from src.utils.network import get_ip_address
                    server_ip = get_ip_address()
                    protocol = "wss" if use_ssl else "ws"
                    print(f"✅ WebSocket server: Started on {protocol}://{server_ip}:{port_to_use}")
                    print(f"   Also available at: {protocol}://localhost:{port_to_use}")
                    
                    await asyncio.Future()  # Run forever
                break
            except OSError as e:
                if "98" in str(e) or "address already in use" in str(e).lower():
                    if attempt < max_retries - 1:
                        print(f"Port {port_to_use} is busy. Trying port {port_to_use + 1}...")
                        port_to_use += 1
                    else:
                        print(f"❌ Failed to find an available port after {max_retries} attempts")
                        return
                else:
                    raise e
                    
    except Exception as e:
        print(f"❌ Failed to start WebSocket server: {e}")
        import traceback
        traceback.print_exc()

def run_websocket_server(ws_port, current_frame, frame_lock, latency_metrics, connected_clients):
    """Run WebSocket server in its own event loop"""
    # Set up proper event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(start_websocket_server(ws_port, current_frame, frame_lock, latency_metrics, connected_clients))
    except KeyboardInterrupt:
        print("\nWebSocket server stopped by user")
    except Exception as e:
        print(f"WebSocket server error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        loop.close()