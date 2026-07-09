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
from collections import deque

def add_timestamp_to_frame(frame, timestamp_ns):
    """Add timestamp as text overlay to frame"""
    try:
        frame_copy = frame.copy()
        timestamp_ms = timestamp_ns // 1_000_000
        # cv2.putText(frame_copy, f"TS:{timestamp_ms}", (10, 30),
        #            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        return frame_copy
    except Exception as e:
        print(f"Error adding timestamp: {e}")
        return frame

async def ws_handler(websocket, current_frame, frame_lock, latency_metrics, 
                     clients_set, capture_t1_shared=None):
    """WebSocket handler with complete server-side timing"""
    client_addr = None
    try:
        client_addr = websocket.remote_address
        print(f"✅ Client connected from {client_addr}")
        
        clients_set.add(websocket)
        print(f"👥 Total clients: {len(clients_set)}")
        
        try:
            await websocket.send(json.dumps({"type": "welcome", "message": "Connected to video stream server"}))
            print("📤 Sent welcome message")
        except Exception as e:
            print(f"❌ Failed to send welcome: {e}")
        
        client_metrics = {
            'frame_count': 0,
            'fps_frame_count': 0,
            'last_fps_update': time.time(),
            'fps': 0.0
        }
        
        # Server timing storage
        server_timings = {
            't1_capture': deque(maxlen=100),
            't2_resize': deque(maxlen=100),
            't3_encode': deque(maxlen=100),
            't4_total_server': deque(maxlen=100),
            't5_network_send': deque(maxlen=100)
        }
        
        async for message in websocket:
            try:
                data = json.loads(message)
                
                if data.get("type") == "request_frame":
                    print(f"🎬 Frame request #{client_metrics['frame_count']}")
                    
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
                        # ==========================================
                        # GET T1 CAPTURE TIME FROM CAPTURE THREAD
                        # ==========================================
                        t1_capture_ms = 0
                        if capture_t1_shared and isinstance(capture_t1_shared, list):
                            t1_capture_ms = capture_t1_shared[0]
                        server_timings['t1_capture'].append(t1_capture_ms)
                        
                        # ==========================================
                        # MEASURE T2: RESIZE TIME
                        # ==========================================
                        t2_start = time.perf_counter_ns()
                        
                        server_timestamp_ms = int(time.time() * 1000)
                        
                        height, width = current_frame_data.shape[:2]
                        max_dimension = 1280
                        if width > max_dimension:
                            scale = max_dimension / width
                            new_width = max_dimension
                            new_height = int(height * scale)
                            frame_resized = cv2.resize(current_frame_data, (new_width, new_height))
                        else:
                            frame_resized = current_frame_data
                        
                        t2_resize_time = (time.perf_counter_ns() - t2_start) / 1_000_000
                        server_timings['t2_resize'].append(t2_resize_time)
                        
                        frame_with_ts = add_timestamp_to_frame(frame_resized, server_timestamp_ms * 1_000_000)
                        
                        # ==========================================
                        # MEASURE T3: JPEG ENCODE TIME
                        # ==========================================
                        t3_start = time.perf_counter_ns()
                        
                        success, buffer = cv2.imencode('.jpg', frame_with_ts, 
                                                     [cv2.IMWRITE_JPEG_QUALITY, 70])
                        
                        t3_encode_time = (time.perf_counter_ns() - t3_start) / 1_000_000
                        server_timings['t3_encode'].append(t3_encode_time)
                        
                        if not success:
                            print("❌ Failed to encode frame")
                            continue
                        
                        # ==========================================
                        # CALCULATE TOTAL SERVER PROCESSING
                        # ==========================================
                        t4_total_server = t1_capture_ms + t2_resize_time + t3_encode_time
                        server_timings['t4_total_server'].append(t4_total_server)
                        
                        # ==========================================
                        # MEASURE T5: NETWORK SEND TIME
                        # ==========================================
                        t5_start = time.perf_counter_ns()
                        
                        response = {
                            'metadata': {
                                'server_timestamp_ms': server_timestamp_ms,
                                't1_capture_ms': t1_capture_ms,
                                't2_resize_ms': t2_resize_time,
                                't3_encode_ms': t3_encode_time,
                                't4_total_server_ms': t4_total_server,
                                'frame_index': client_metrics['frame_count']
                            },
                            'image_data': buffer.tobytes().hex()
                        }
                        
                        await websocket.send(json.dumps(response))
                        
                        t5_network_time = (time.perf_counter_ns() - t5_start) / 1_000_000
                        server_timings['t5_network_send'].append(t5_network_time)
                        
                        # Update metrics
                        latency_metrics['t1_capture'].append(t1_capture_ms)
                        latency_metrics['t2_processing'].append(t4_total_server)
                        
                        client_metrics['frame_count'] += 1
                        client_metrics['fps_frame_count'] += 1
                        
                        # Update client FPS
                        current_time = time.time()
                        if current_time - client_metrics['last_fps_update'] >= 1.0:
                            client_metrics['fps'] = client_metrics['fps_frame_count'] / (current_time - client_metrics['last_fps_update'])
                            client_metrics['fps_frame_count'] = 0
                            client_metrics['last_fps_update'] = current_time
                            print(f"📊 Client FPS: {client_metrics['fps']:.1f}")
                        
                        # Print detailed server timing every 30 frames
                        if client_metrics['frame_count'] % 30 == 0:
                            print(f"\n{'='*70}")
                            print(f"📊 SERVER TIMING (Frame #{client_metrics['frame_count']})")
                            print(f"{'='*70}")
                            print(f"📷 T1 Capture:    {t1_capture_ms:6.2f}ms  (camera → memory)")
                            print(f"📏 T2 Resize:     {t2_resize_time:6.2f}ms  (resize operation)")
                            print(f"🗜️ T3 Encode:     {t3_encode_time:6.2f}ms  (JPEG compression)")
                            print(f"{'-'*70}")
                            print(f"⚙️ T4 Total Server: {t4_total_server:6.2f}ms  (T1+T2+T3)")
                            print(f"📤 T5 Network Send: {t5_network_time:6.2f}ms  (WebSocket send)")
                            print(f"{'='*70}\n")
                        
                        # Simple status every frame
                        print(f"📤 Frame #{client_metrics['frame_count']} | "
                              f"T1:{t1_capture_ms:.1f}ms | "
                              f"T2:{t2_resize_time:.1f}ms | "
                              f"T3:{t3_encode_time:.1f}ms | "
                              f"T4:{t4_total_server:.1f}ms | "
                              f"T5:{t5_network_time:.1f}ms")
                        
                    except Exception as e:
                        print(f"❌ Error processing frame: {e}")
                        traceback.print_exc()
                        await websocket.send(json.dumps({
                            "type": "error",
                            "message": f"Frame processing error: {str(e)}"
                        }))
                
                elif data.get("type") == "latency_report":
                    report = data.get("data", {})
                    print(f"📊 Client Latency Report:")
                    print(f"   T6 Network Rx: {report.get('t3_network', 0):.1f}ms")
                    print(f"   T7 Decode:     {report.get('t4_decoding', 0):.1f}ms")
                    print(f"   T8 YOLO:       {report.get('t5_yolo', 0):.1f}ms")
                    print(f"   T9 Draw:       {report.get('t6_draw', 0):.1f}ms")
                    print(f"   T10 Display:   {report.get('t7_rendering', 0):.1f}ms")
                    
                    for metric in ['t3_network', 't4_decoding', 't5_yolo', 't6_draw', 't7_rendering', 'total']:
                        if metric in report:
                            latency_metrics[metric].append(report[metric])
                
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

async def start_websocket_server(ws_port, current_frame, frame_lock, latency_metrics, 
                                 connected_clients, capture_t1_shared=None):
    """Start WebSocket server"""
    print(f"\n🚀 Starting WebSocket server on port {ws_port}...")
    
    try:
        ssl_context = None
        cert_path = "certs/certTwo.pem"
        key_path = "certs/keyTwo.pem"
        
        if os.path.exists(cert_path) and os.path.exists(key_path):
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_context.load_cert_chain(certfile=cert_path, keyfile=key_path)
            print("✅ SSL enabled")
        else:
            print("⚠️ SSL disabled - using ws:// (browser may show warnings)")
        
        async def handler(websocket):
            await ws_handler(websocket, current_frame, frame_lock, latency_metrics, 
                           connected_clients, capture_t1_shared)
        
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

def run_websocket_server(ws_port, current_frame, frame_lock, connected_clients, 
                        latency_metrics, capture_t1_shared=None):
    """Run WebSocket server in its own event loop"""
    print("🔵 Starting WebSocket thread...")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(start_websocket_server(ws_port, current_frame, frame_lock, 
                                                       latency_metrics, connected_clients, 
                                                       capture_t1_shared))
    except KeyboardInterrupt:
        print("\n⚠️ WebSocket interrupted")
    except Exception as e:
        print(f"❌ WebSocket fatal: {e}")
        traceback.print_exc()
    finally:
        loop.close()
        print("🔵 WebSocket thread stopped")