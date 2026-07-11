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
    """
    Adiciona um timestamp como texto sobreposto no frame.
    (Atualmente comentado para não interferir com a visualização)

    Args:
        frame: Imagem de entrada
        timestamp_ns: Timestamp em nanossegundos

    Returns:
        np.ndarray: Cópia do frame (com ou sem timestamp)
    """
    try:
        frame_copy = frame.copy()
        timestamp_ms = timestamp_ns // 1_000_000  # Converte para milissegundos
        # O código abaixo está comentado para não adicionar texto ao frame
        # cv2.putText(frame_copy, f"TS:{timestamp_ms}", (10, 30),
        #            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        return frame_copy
    except Exception as e:
        print(f"Erro ao adicionar o carimbo de data/hora: {e}")
        return frame


async def ws_handler(websocket, current_frame, frame_lock, latency_metrics, 
                     clients_set, capture_t1_shared=None, fps_transmission_shared=None):
    """
    Handler WebSocket que processa pedidos de frames e mede os tempos do servidor.
    
    Este handler é chamado para cada cliente que se conecta ao servidor WebSocket.
    Mantém uma ligação persistente e responde a pedidos de frames individuais.
    
    Args:
        websocket: Objeto WebSocket do cliente
        current_frame: Frame atual da câmara (partilhado entre threads)
        frame_lock: Lock para acesso thread-safe ao frame
        latency_metrics: Dicionário para armazenar métricas de latência
        clients_set: Conjunto de clientes conectados
        capture_t1_shared: Valor partilhado do tempo T1 (captura)
        fps_transmission_shared: Valor partilhado do FPS de transmissão
    """
    client_addr = None
    try:
        # ============================================================
        # CONEXÃO DO CLIENTE
        # ============================================================
        client_addr = websocket.remote_address
        print(f"Cliente conectado de {client_addr}")
        
        clients_set.add(websocket)  # Adiciona o cliente ao conjunto
        print(f"Total de clientes: {len(clients_set)}")
        
        # Envia mensagem de boas-vindas
        try:
            await websocket.send(json.dumps({"type": "welcome", "message": "Ligado ao servidor de transmissão de vídeo"}))
            print("Mensagem de boas-vindas enviada")
        except Exception as e:
            print(f"Falha ao enviar a mensagem de boas-vindas: {e}")
        
        # ============================================================
        # MÉTRICAS DO CLIENTE
        # ============================================================
        client_metrics = {
            'frame_count': 0,           # Contador de frames enviados
            'fps_frame_count': 0,       # Contador para cálculo de FPS
            'last_fps_update': time.time(),  # Última atualização de FPS
            'fps': 0.0                  # FPS atual do cliente
        }
        
        # Histórico de FPS para estatísticas
        fps_values = []
        
        # ============================================================
        # ARMAZENAMENTO DE TEMPOS DO SERVIDOR
        # ============================================================
        server_timings = {
            't1_capture': deque(maxlen=100),      # Tempo de captura (câmara → memória)
            't2_resize': deque(maxlen=100),       # Tempo de redimensionamento
            't3_encode': deque(maxlen=100),       # Tempo de compressão JPEG
            't4_total_server': deque(maxlen=100), # Tempo total do servidor (T1+T2+T3)
            't5_network_send': deque(maxlen=100)  # Tempo de envio WebSocket
        }
        
        # ============================================================
        # LOOP PRINCIPAL DE MENSAGENS
        # ============================================================
        async for message in websocket:
            try:
                data = json.loads(message)  # Descodifica a mensagem JSON
                
                # ============================================================
                # PEDIDO DE FRAME
                # ============================================================
                if data.get("type") == "request_frame":
                    print(f"Pedido de frame #{client_metrics['frame_count']}")
                    
                    # ============================================================
                    # ACESSO AO FRAME COM PROTEÇÃO POR LOCK
                    # ============================================================
                    with frame_lock:
                        if isinstance(current_frame, list):
                            frame_available = current_frame[0] is not None
                            current_frame_data = current_frame[0] if frame_available else None
                        else:
                            frame_available = current_frame is not None
                            current_frame_data = current_frame if frame_available else None
                    
                    # Verifica se há frame disponível
                    if not frame_available or current_frame_data is None:
                        print("Sem frame disponível, enviando resposta de espera.")
                        await websocket.send(json.dumps({
                            "type": "waiting",
                            "message": "Camera not ready",
                            "frame_index": client_metrics['frame_count']
                        }))
                        client_metrics['frame_count'] += 1
                        continue
                    
                    try:
                        # ============================================================
                        # T1: OBTÉM O TEMPO DE CAPTURA DA THREAD DE CAPTURA
                        # ============================================================
                        t1_capture_ms = 0
                        if capture_t1_shared and isinstance(capture_t1_shared, list):
                            t1_capture_ms = capture_t1_shared[0]
                        server_timings['t1_capture'].append(t1_capture_ms)
                        
                        # ============================================================
                        # T2: MEDIÇÃO DO TEMPO DE REDIMENSIONAMENTO
                        # ============================================================
                        t2_start = time.perf_counter_ns()
                        
                        # Timestamp do servidor
                        server_timestamp_ms = int(time.time() * 1000)
                        
                        # Redimensiona o frame se necessário (máx 1280 pixels)
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
                        
                        # Adiciona timestamp ao frame (opcional)
                        frame_with_ts = add_timestamp_to_frame(frame_resized, server_timestamp_ms * 1_000_000)
                        
                        # ============================================================
                        # T3: MEDIÇÃO DO TEMPO DE COMPRESSÃO JPEG
                        # ============================================================
                        t3_start = time.perf_counter_ns()
                        
                        # Codifica o frame para JPEG com qualidade 70
                        success, buffer = cv2.imencode('.jpg', frame_with_ts, 
                                                     [cv2.IMWRITE_JPEG_QUALITY, 70])
                        
                        t3_encode_time = (time.perf_counter_ns() - t3_start) / 1_000_000
                        server_timings['t3_encode'].append(t3_encode_time)
                        
                        if not success:
                            print("Falha ao codificar o quadro")
                            continue
                        
                        # ============================================================
                        # T4: CÁLCULO DO TEMPO TOTAL DO SERVIDOR
                        # ============================================================
                        t4_total_server = t1_capture_ms + t2_resize_time + t3_encode_time
                        server_timings['t4_total_server'].append(t4_total_server)
                        
                        # ============================================================
                        # T5: MEDIÇÃO DO TEMPO DE ENVIO WEBSOCKET
                        # ============================================================
                        t5_start = time.perf_counter_ns()
                        
                        # Prepara a resposta com os metadados e a imagem
                        response = {
                            'metadata': {
                                'server_timestamp_ms': server_timestamp_ms,
                                't1_capture_ms': t1_capture_ms,
                                't2_resize_ms': t2_resize_time,
                                't3_encode_ms': t3_encode_time,
                                't4_total_server_ms': t4_total_server,
                                'frame_index': client_metrics['frame_count']
                            },
                            'image_data': buffer.tobytes().hex()  # Imagem codificada em hexadecimal
                        }
                        
                        # Envia a resposta via WebSocket
                        await websocket.send(json.dumps(response))
                        
                        t5_network_time = (time.perf_counter_ns() - t5_start) / 1_000_000
                        server_timings['t5_network_send'].append(t5_network_time)
                        
                        # ============================================================
                        # ATUALIZAÇÃO DE MÉTRICAS
                        # ============================================================
                        # Atualiza o dicionário de métricas
                        latency_metrics['t1_capture'].append(t1_capture_ms)
                        latency_metrics['t2_processing'].append(t4_total_server)
                        
                        # Atualiza contadores do cliente
                        client_metrics['frame_count'] += 1
                        client_metrics['fps_frame_count'] += 1
                        
                        # ============================================================
                        # CÁLCULO DO FPS DO CLIENTE (A CADA SEGUNDO)
                        # ============================================================
                        current_time = time.time()
                        if current_time - client_metrics['last_fps_update'] >= 1.0:
                            client_metrics['fps'] = client_metrics['fps_frame_count'] / (current_time - client_metrics['last_fps_update'])
                            
                            # Armazena o FPS para estatísticas
                            fps_values.append(client_metrics['fps'])
                            if len(fps_values) > 1000:
                                fps_values.pop(0)
                            
                            # Armazena no dicionário de métricas
                            if 'fps_transmission' not in latency_metrics:
                                latency_metrics['fps_transmission'] = []
                            latency_metrics['fps_transmission'].append(client_metrics['fps'])
                            
                            # Partilha com a thread principal
                            if fps_transmission_shared is not None and isinstance(fps_transmission_shared, list):
                                fps_transmission_shared[0] = client_metrics['fps']
                            
                            # Reinicia contadores
                            client_metrics['fps_frame_count'] = 0
                            client_metrics['last_fps_update'] = current_time
                            
                            # Imprime estatísticas de FPS de transmissão
                            if fps_values:
                                avg_fps = sum(fps_values) / len(fps_values)
                                max_fps = max(fps_values)
                                min_fps = min(fps_values)
                                print(f"\nESTATÍSTICAS DE FPS DE TRANSMISSÃO (last {len(fps_values)} amostras):")
                                print(f"   Média: {avg_fps:.1f} | Máx: {max_fps:.1f} | Mín: {min_fps:.1f} FPS")
                            
                            print(f"FPS do cliente: {client_metrics['fps']:.1f}")
                        
                        # ============================================================
                        # IMPRESSÃO DETALHADA DOS TEMPOS (A CADA 30 FRAMES)
                        # ============================================================
                        if client_metrics['frame_count'] % 30 == 0:
                            print(f"\n{'='*70}")
                            print(f"TEMPORIZAÇÃO DO SERVIDOR (Frame #{client_metrics['frame_count']})")
                            print(f"{'='*70}")
                            print(f"T1 Capturar:    {t1_capture_ms:6.2f}ms  (câmara → memória)")
                            print(f"T2 Redimensionar:     {t2_resize_time:6.2f}ms  (operação de redimensionamento)")
                            print(f"🗜️ T3 Codificar:     {t3_encode_time:6.2f}ms  (Compressão JPEG)")
                            print(f"{'-'*70}")
                            print(f"T4 Servidor Total: {t4_total_server:6.2f}ms  (T1+T2+T3)")
                            print(f"T5 Envio em rede: {t5_network_time:6.2f}ms  (Envio via WebSocket)")
                            print(f"{'='*70}\n")
                        
                        # ============================================================
                        # STATUS SIMPLES (A CADA FRAME)
                        # ============================================================
                        print(f"Frame #{client_metrics['frame_count']} | "
                              f"T1:{t1_capture_ms:.1f}ms | "
                              f"T2:{t2_resize_time:.1f}ms | "
                              f"T3:{t3_encode_time:.1f}ms | "
                              f"T4:{t4_total_server:.1f}ms | "
                              f"T5:{t5_network_time:.1f}ms")
                        
                    except Exception as e:
                        print(f"Erro no processamento do frame: {e}")
                        traceback.print_exc()
                        await websocket.send(json.dumps({
                            "type": "error",
                            "message": f"Frame processing error: {str(e)}"
                        }))
                
                # ============================================================
                # RELATÓRIO DE LATÊNCIA DO CLIENTE
                # ============================================================
                elif data.get("type") == "latency_report":
                    report = data.get("data", {})
                    print(f"Relatório de Latência do Cliente:")
                    print(f"   T6 Rede Rx: {report.get('t3_network', 0):.1f}ms")
                    print(f"   T7 Decodificar:     {report.get('t4_decoding', 0):.1f}ms")
                    print(f"   T8 YOLO:       {report.get('t5_yolo', 0):.1f}ms")
                    print(f"   T9 Desenhar:       {report.get('t6_draw', 0):.1f}ms")
                    print(f"   T10 Ecrã:   {report.get('t7_rendering', 0):.1f}ms")
                    
                    # Armazena as métricas do cliente
                    for metric in ['t3_network', 't4_decoding', 't5_yolo', 't6_draw', 't7_rendering', 'total']:
                        if metric in report:
                            latency_metrics[metric].append(report[metric])
                
            except json.JSONDecodeError as e:
                print(f"JSON inválido: {e}")
            except Exception as e:
                print(f"Erro no ciclo de mensagens: {e}")
                traceback.print_exc()
                
    except websockets.exceptions.ConnectionClosed as e:
        print(f"🔌 Cliente {client_addr} desconectou: {e}")
    except Exception as e:
        print(f"Erro fatal no ws_handler: {e}")
        traceback.print_exc()
    finally:
        # Remove o cliente do conjunto quando a ligação termina
        if websocket in clients_set:
            clients_set.remove(websocket)
            print(f"Cliente removido. Total de clientes: {len(clients_set)}")


async def start_websocket_server(ws_port, current_frame, frame_lock, latency_metrics, 
                                 connected_clients, capture_t1_shared=None, 
                                 fps_transmission_shared=None):
    """
    Inicia o servidor WebSocket.

    Args:
        ws_port: Porta para o servidor WebSocket
        current_frame: Frame atual da câmara
        frame_lock: Lock para acesso thread-safe ao frame
        latency_metrics: Dicionário de métricas de latência
        connected_clients: Conjunto de clientes conectados
        capture_t1_shared: Valor partilhado do tempo T1
        fps_transmission_shared: Valor partilhado do FPS de transmissão
    """
    print(f"\nIniciar o servidor WebSocket na porta {ws_port}...")
    
    try:
        # ============================================================
        # CONFIGURAÇÃO SSL (OPCIONAL)
        # ============================================================
        ssl_context = None
        cert_path = "certs/certTwo.pem"
        key_path = "certs/keyTwo.pem"
        
        if os.path.exists(cert_path) and os.path.exists(key_path):
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_context.load_cert_chain(certfile=cert_path, keyfile=key_path)
            print("SSL ativado")
        else:
            print("SSL desativado - utilizando ws://")
        
        # ============================================================
        # DEFINIÇÃO DO HANDLER
        # ============================================================
        async def handler(websocket):
            await ws_handler(websocket, current_frame, frame_lock, latency_metrics, 
                           connected_clients, capture_t1_shared, fps_transmission_shared)
        
        # ============================================================
        # INICIALIZAÇÃO DO SERVIDOR
        # ============================================================
        async with websockets.serve(
            handler, 
            '0.0.0.0',  # Escuta em todas as interfaces
            ws_port,
            ssl=ssl_context,
            ping_interval=20,   # Intervalo entre pings (keep-alive)
            ping_timeout=40,    # Timeout para respostas de ping
            max_size=10 * 1024 * 1024  # Tamanho máximo da mensagem (10 MB)
        ):
            from src.utils.network import get_ip_address
            server_ip = get_ip_address()
            protocol = "wss" if ssl_context else "ws"
            print(f"Servidor WebSocket em execução em {protocol}://{server_ip}:{ws_port}")
            print(f"Aguardando ligações...")
            
            # Mantém o servidor em execução indefinidamente
            await asyncio.Future()
                    
    except OSError as e:
        # Erro relacionado com a porta (ex: já em uso)
        if "98" in str(e) or "address already in use" in str(e).lower():
            print(f"Porta {ws_port} já está em uso!")
            print("   Tente: sudo lsof -i :3001")
        else:
            print(f"Erro do servidor: {e}")
            traceback.print_exc()
    except Exception as e:
        print(f"Erro do servidor: {e}")
        traceback.print_exc()


def run_websocket_server(ws_port, current_frame, frame_lock, connected_clients, 
                        latency_metrics, capture_t1_shared=None, 
                        fps_transmission_shared=None):
    """
    Executa o servidor WebSocket no seu próprio loop de eventos.
    Esta função é chamada numa thread separada.

    Args:
        ws_port: Porta para o servidor WebSocket
        current_frame: Frame atual da câmara
        frame_lock: Lock para acesso thread-safe ao frame
        connected_clients: Conjunto de clientes conectados
        latency_metrics: Dicionário de métricas de latência
        capture_t1_shared: Valor partilhado do tempo T1
        fps_transmission_shared: Valor partilhado do FPS de transmissão
    """
    print("Iniciando thread WebSocket...")
    
    # Cria um novo loop de eventos para a thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Executa o servidor WebSocket no loop
        loop.run_until_complete(start_websocket_server(ws_port, current_frame, frame_lock, 
                                                       latency_metrics, connected_clients, 
                                                       capture_t1_shared, fps_transmission_shared))
    except KeyboardInterrupt:
        print("\nWebSocket interrompido")
    except Exception as e:
        print(f"WebSocket fatal: {e}")
        traceback.print_exc()
    finally:
        loop.close()  # Fecha o loop quando termina
        print("A thread WebSocket foi interrompida.")