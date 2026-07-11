# src/server/handlers.py

import json
import time
import cv2
from http.server import BaseHTTPRequestHandler
from src.web import get_static_file, get_mime_type

# ============================================================
# CONTEXTO GLOBAL PARTILHADO COM O HANDLER
# ============================================================
# Este dicionário contém todas as variáveis partilhadas entre o servidor HTTP e os handlers
_handler_context = {}

def set_handler_context(current_frame, frame_lock, connected_clients, latency_metrics, 
                        html_content, system_monitor=None, fps_capture_shared=None,
                        fps_transmission_shared=None):
    """
    Define o contexto global para o handler HTTP.
    Esta função é chamada pelo servidor HTTP para passar as variáveis partilhadas.
    
    Args:
        current_frame: Frame atual da câmara
        frame_lock: Lock para acesso thread-safe ao frame
        connected_clients: Conjunto de clientes conectados ao WebSocket
        latency_metrics: Dicionário de métricas de latência
        html_content: Conteúdo HTML da página principal
        system_monitor: Monitor do sistema (CPU/RAM)
        fps_capture_shared: Valor partilhado do FPS de captura
        fps_transmission_shared: Valor partilhado do FPS de transmissão
    """
    global _handler_context
    _handler_context = {
        'current_frame': current_frame,
        'frame_lock': frame_lock,
        'connected_clients': connected_clients,
        'latency_metrics': latency_metrics,
        'html_content': html_content,
        'system_monitor': system_monitor,
        'fps_capture_shared': fps_capture_shared,
        'fps_transmission_shared': fps_transmission_shared
    }


class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    """
    Handler HTTP personalizado para o dashboard de streaming.
    Processa pedidos GET para a página principal, ficheiros estáticos, debug, health e metrics.
    """
    
    def do_GET(self):
        """
        Processa pedidos GET HTTP.
        Mapeia diferentes caminhos para diferentes respostas.
        """
        
        # ============================================================
        # ROTA PRINCIPAL: PÁGINA INICIAL
        # ============================================================
        if self.path == "/":
            self.send_response(200)  # OK
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            
            html_content = _handler_context.get('html_content')
            if html_content:
                self.wfile.write(html_content.encode("utf-8"))  # Envia o HTML
            else:
                self.wfile.write(b"<h1>HTML content not loaded</h1><p>Debug: html_content is None</p>")
            return

        # ============================================================
        # ROTA: FICHEIROS ESTÁTICOS (CSS, JS, imagens)
        # ============================================================
        elif self.path.startswith('/static/'):
            filepath = self.path[8:]  # Remove '/static/' do caminho
            content = get_static_file(filepath)  # Obtém o conteúdo do ficheiro
            
            if content:
                self.send_response(200)
                self.send_header("Content-type", get_mime_type(filepath))  # Define o tipo MIME
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_error(404, "Static file not found")  # Ficheiro não encontrado
            return

        # ============================================================
        # ROTA: DEBUG - DEVOLVE O FRAME ATUAL
        # ============================================================
        elif self.path == "/debug":
            self.send_response(200)
            current_frame_container = _handler_context.get('current_frame')
            frame_lock = _handler_context.get('frame_lock')
            
            # Verifica se o frame existe e é acessível
            if current_frame_container is not None and frame_lock:
                with frame_lock:  # Proteção para acesso thread-safe
                    # Verifica se é uma lista (para permitir mutabilidade)
                    if isinstance(current_frame_container, list):
                        frame = current_frame_container[0]
                    else:
                        frame = current_frame_container
                    
                    if frame is not None:
                        # Codifica o frame para JPEG e envia como imagem
                        _, buffer = cv2.imencode('.jpg', frame)
                        self.send_header("Content-type", "image/jpeg")
                        self.end_headers()
                        self.wfile.write(buffer.tobytes())
                    else:
                        # Frame não disponível
                        self.send_header("Content-type", "text/html")
                        self.end_headers()
                        self.wfile.write(b"<h1>No frame available (frame is None)</h1>")
            else:
                # Falta frame ou lock
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h1>No frame available</h1>")
            return
                
        # ============================================================
        # ROTA: HEALTH - ESTADO DO SISTEMA
        # ============================================================
        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            
            # Verifica se a câmara está a fornecer frames
            current_frame_container = _handler_context.get('current_frame')
            frame_exists = False
            if current_frame_container is not None:
                if isinstance(current_frame_container, list):
                    frame_exists = current_frame_container[0] is not None
                else:
                    frame_exists = current_frame_container is not None
            
            # Constrói os dados de saúde do sistema
            health_data = {
                "status": "running",
                "camera": frame_exists,  # True se a câmara estiver ativa
                "clients": len(_handler_context.get('connected_clients', set())),  # Número de clientes
                "timestamp": time.time(),
                "latency_samples": {k: len(v) for k, v in _handler_context.get('latency_metrics', {}).items()}
            }
            self.wfile.write(json.dumps(health_data).encode())
            return
            
        # ============================================================
        # ROTA: METRICS - ESTATÍSTICAS DETALHADAS EM JSON
        # ============================================================
        elif self.path == "/metrics":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            
            # ============================================================
            # COLETA DE MÉTRICAS DE LATÊNCIA
            # ============================================================
            metrics_stats = {}
            latency_metrics = _handler_context.get('latency_metrics', {})
            
            # Itera sobre cada métrica e calcula estatísticas
            for metric, values in latency_metrics.items():
                if values:  # Se existirem valores
                    metrics_stats[metric] = {
                        "samples": len(values),
                        "avg": round(sum(values) / len(values), 2),  # Média
                        "min": round(min(values), 2),                 # Mínimo
                        "max": round(max(values), 2),                 # Máximo
                        "last_10_avg": round(sum(values[-10:]) / min(10, len(values)), 2) if values else 0  # Média dos últimos 10
                    }
            
            # ============================================================
            # VERIFICAÇÃO DO ESTADO DA CÂMARA
            # ============================================================
            current_frame_container = _handler_context.get('current_frame')
            frame_exists = False
            if current_frame_container is not None:
                if isinstance(current_frame_container, list):
                    frame_exists = current_frame_container[0] is not None
                else:
                    frame_exists = current_frame_container is not None
            
            # ============================================================
            # COLETA DE MÉTRICAS DO SISTEMA (CPU/RAM)
            # ============================================================
            system_stats = {}
            system_monitor = _handler_context.get('system_monitor')
            if system_monitor:
                system_stats = system_monitor.get_stats()  # Obtém estatísticas atuais
            
            # ============================================================
            # COLETA DE MÉTRICAS DE FPS
            # ============================================================
            fps_capture = 0
            fps_capture_shared = _handler_context.get('fps_capture_shared')
            if fps_capture_shared and isinstance(fps_capture_shared, list):
                fps_capture = round(fps_capture_shared[0], 1)  # FPS de captura
            
            fps_transmission = 0
            fps_transmission_shared = _handler_context.get('fps_transmission_shared')
            if fps_transmission_shared and isinstance(fps_transmission_shared, list):
                fps_transmission = round(fps_transmission_shared[0], 1)  # FPS de transmissão
            
            # ============================================================
            # CONSTRUÇÃO DA RESPOSTA
            # ============================================================
            metrics_data = {
                "timestamp": time.time(),
                "metrics": metrics_stats,           # Estatísticas de latência
                "system": system_stats,             # Estatísticas de CPU/RAM
                "fps": {
                    "capture": fps_capture,         # FPS de captura
                    "transmission": fps_transmission  # FPS de transmissão
                },
                "connected_clients": len(_handler_context.get('connected_clients', set())),
                "current_frame": frame_exists
            }
            
            # Envia a resposta JSON com indentação para legibilidade
            self.wfile.write(json.dumps(metrics_data, indent=2).encode())
            return
        
        # ============================================================
        # ROTA NÃO ENCONTRADA (404)
        # ============================================================
        else:
            self.send_error(404, "Not Found")
    
    def log_message(self, format, *args):
        """
        Suprime os logs padrão do servidor HTTP para evitar poluir o terminal.
        """
        pass  # Não imprime mensagens de log


def create_handler_with_context(current_frame, frame_lock, connected_clients, latency_metrics, 
                                html_content, system_monitor=None, fps_capture_shared=None,
                                fps_transmission_shared=None):
    """
    Cria um handler HTTP com o contexto necessário.
    
    Args:
        current_frame: Frame atual da câmara
        frame_lock: Lock para acesso thread-safe ao frame
        connected_clients: Conjunto de clientes conectados ao WebSocket
        latency_metrics: Dicionário de métricas de latência
        html_content: Conteúdo HTML da página principal
        system_monitor: Monitor do sistema (CPU/RAM)
        fps_capture_shared: Valor partilhado do FPS de captura
        fps_transmission_shared: Valor partilhado do FPS de transmissão
    
    Returns:
        SimpleHTTPRequestHandler: Classe do handler configurada com o contexto
    """
    # Define o contexto global com os parâmetros fornecidos
    set_handler_context(current_frame, frame_lock, connected_clients, latency_metrics, 
                        html_content, system_monitor, fps_capture_shared, 
                        fps_transmission_shared)
    
    # Retorna a classe do handler (já com o contexto definido)
    return SimpleHTTPRequestHandler