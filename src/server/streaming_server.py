# src/server/streaming_server.py
import asyncio
import json
import time
import ssl
import os
import sys
import websockets
import cv2
import numpy as np
import traceback

# Simple timestamp function without error handling issues
def add_timestamp_to_frame(frame, timestamp_ns):
    """Add timestamp as text overlay to frame"""
    try:
        frame_copy = frame.copy()
        timestamp_ms = timestamp_ns // 1_000_000
        cv2.putText(frame_copy, f"TS:{timestamp_ms}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        return frame_copy
    except Exception as e:
        print(f"Error adding timestamp: {e}")
        return frame

async def ws_handler(websocket, current_frame, frame_lock, latency_metrics, clients_set):
    """WebSocket handler with latency measurement"""
    client_addr = None
    try:
        client_addr = websocket.remote_address
        print(f"✅ Client connected from {client_addr}")
        
        # Add client to set
        clients_set.add(websocket)
        print(f"👥 Total clients: {len(clients_set)}")
        
        # Send a welcome message
        try:
            await websocket.send(json.dumps({"type": "welcome", "message": "Connected to video stream server"}))
            print("📤 Sent welcome message")
        except Exception as e:
            print(f"❌ Failed to send welcome: {e}")
        
        client_metrics = {
            'frame_count': 0,
            'last_print_time': time.time()
        }
        
        # Main message loop
        async for message in websocket:
            try:
                print(f"📨 Received: {message[:100]}...")
                data = json.loads(message)
                
                if data.get("type") == "request_frame":
                    print(f"🎬 Frame request #{client_metrics['frame_count']}")
                    
                    # Check if frame exists
                    with frame_lock:
                        if isinstance(current_frame, list):
                            frame_available = current_frame[0] is not None
                            current_frame_data = current_frame[0] if frame_available else None
                        else:
                            frame_available = current_frame is not None
                            current_frame_data = current_frame if frame_available else None
                    
                    if not frame_available or current_frame_data is None:
                        print("⚠️ No frame available, sending waiting response")
                        await websocket.send(json.dumps({
                            "type": "waiting",
                            "message": "Camera not ready",
                            "frame_index": client_metrics['frame_count']
                        }))
                        client_metrics['frame_count'] += 1
                        continue
                    
                    try:
                        # Start timing
                        t2_start = time.perf_counter_ns()
                        
                        # Get timestamp
                        server_timestamp_ms = int(time.time() * 1000)
                        
                        # Resize frame
                        height, width = current_frame_data.shape[:2]
                        max_dimension = 1280
                        if width > max_dimension:
                            scale = max_dimension / width
                            new_width = max_dimension
                            new_height = int(height * scale)
                            frame_resized = cv2.resize(current_frame_data, (new_width, new_height))
                        else:
                            frame_resized = current_frame_data
                        
                        # Add timestamp
                        frame_with_ts = add_timestamp_to_frame(frame_resized, server_timestamp_ms * 1_000_000)
                        
                        # Encode to JPEG
                        success, buffer = cv2.imencode('.jpg', frame_with_ts, 
                                                     [cv2.IMWRITE_JPEG_QUALITY, 70])
                        
                        if not success:
                            print("❌ Failed to encode frame")
                            continue
                        
                        # Calculate processing time
                        t2_processing = (time.perf_counter_ns() - t2_start) / 1_000_000
                        
                        # Prepare response
                        response = {
                            'metadata': {
                                'server_timestamp_ms': server_timestamp_ms,
                                't1_capture': data.get('t1_capture', 0),
                                't2_processing': t2_processing,
                                'frame_index': client_metrics['frame_count']
                            },
                            'image_data': buffer.tobytes().hex()
                        }
                        
                        # Send frame
                        await websocket.send(json.dumps(response))
                        print(f"📤 Frame #{client_metrics['frame_count']} sent, size: {len(buffer.tobytes())} bytes, T2: {t2_processing:.2f}ms")
                        
                        # Update metrics
                        latency_metrics['t2_processing'].append(t2_processing)
                        client_metrics['frame_count'] += 1
                        
                    except Exception as e:
                        print(f"❌ Error processing frame: {e}")
                        traceback.print_exc()
                        await websocket.send(json.dumps({
                            "type": "error",
                            "message": f"Frame processing error: {str(e)}"
                        }))
                
                elif data.get("type") == "latency_report":
                    report = data.get("data", {})
                    for metric in ['t1_capture', 't3_network', 't4_decoding', 't5_rendering', 'total']:
                        if metric in report:
                            latency_metrics[metric].append(report[metric])
                    print(f"📊 Latency - T1:{report.get('t1_capture',0):.1f}ms T3:{report.get('t3_network',0):.1f}ms Total:{report.get('total',0):.1f}ms")
                
            except json.JSONDecodeError as e:
                print(f"❌ Invalid JSON: {e}")
            except Exception as e:
                print(f"❌ Error in message loop: {e}")
                traceback.print_exc()
                
    except websockets.exceptions.ConnectionClosed as e:
        print(f"🔌 Client {client_addr} disconnected: {e}")
    except Exception as e:
        print(f"💥 Fatal error in ws_handler: {e}")
        traceback.print_exc()
    finally:
        if websocket in clients_set:
            clients_set.remove(websocket)
            print(f"👋 Client removed. Total clients: {len(clients_set)}")

async def start_websocket_server(ws_port, current_frame, frame_lock, latency_metrics, connected_clients):
    """Start WebSocket server"""
    print(f"\n🚀 Starting WebSocket server on port {ws_port}...")
    
    try:
        # SSL setup (optional)
        ssl_context = None
        cert_path = "certs/certTwo.pem"
        key_path = "certs/keyTwo.pem"
        
        if os.path.exists(cert_path) and os.path.exists(key_path):
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_context.load_cert_chain(certfile=cert_path, keyfile=key_path)
            print("✅ SSL enabled")
        else:
            print("⚠️ SSL disabled - using ws:// (browser may show warnings)")
        
        # Create handler
        async def handler(websocket):
            await ws_handler(websocket, current_frame, frame_lock, latency_metrics, connected_clients)
        
        # Start server
        async with websockets.serve(
            handler, 
            '0.0.0.0',
            ws_port, 
            ssl=ssl_context,
            ping_interval=20,
            ping_timeout=40,
            max_size=10 * 1024 * 1024
        ):
            from src.utils.network import get_ip_address
            server_ip = get_ip_address()
            protocol = "wss" if ssl_context else "ws"
            print(f"✅ WebSocket server running on {protocol}://{server_ip}:{ws_port}")
            print(f"🔄 Waiting for connections...")
            
            # Keep running forever
            await asyncio.Future()
                    
    except OSError as e:
        if "98" in str(e) or "address already in use" in str(e).lower():
            print(f"❌ Port {ws_port} is already in use!")
            print("   Try: sudo lsof -i :3001")
        else:
            print(f"❌ Server error: {e}")
            traceback.print_exc()
    except Exception as e:
        print(f"❌ Server error: {e}")
        traceback.print_exc()

def run_websocket_server(ws_port, current_frame, frame_lock, connected_clients, latency_metrics):
    """Run WebSocket server in its own event loop"""
    print("🔵 Starting WebSocket thread...")
    
    # Create new event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(start_websocket_server(ws_port, current_frame, frame_lock, latency_metrics, connected_clients))
    except KeyboardInterrupt:
        print("\n⚠️ WebSocket interrupted")
    except Exception as e:
        print(f"❌ WebSocket fatal: {e}")
        traceback.print_exc()
    finally:
        loop.close()
        print("🔵 WebSocket thread stopped")