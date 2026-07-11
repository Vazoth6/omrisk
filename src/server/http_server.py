# src/server/http_server.py

import ssl
import os
from http.server import HTTPServer
from .handlers import create_handler_with_context
from src.utils.ssl_helper import generate_self_signed_cert


def run_http_server(http_port, current_frame, frame_lock, connected_clients, 
                    latency_metrics, html_content, system_monitor=None, 
                    fps_capture_shared=None, fps_transmission_shared=None):
    """
    Executa o servidor HTTP com suporte SSL/TLS.
    
    Este servidor disponibiliza a interface web de monitorização, bem como
    os endpoints para obtenção de métricas e estado do sistema.
    
    Args:
        http_port: Porta onde o servidor HTTP vai escutar
        current_frame: Frame atual da câmara (partilhado entre threads)
        frame_lock: Lock para acesso thread-safe ao frame
        connected_clients: Conjunto de clientes conectados ao WebSocket
        latency_metrics: Dicionário com as métricas de latência
        html_content: Conteúdo HTML da página principal
        system_monitor: Monitor do sistema (CPU/RAM) - opcional
        fps_capture_shared: Valor partilhado do FPS de captura - opcional
        fps_transmission_shared: Valor partilhado do FPS de transmissão - opcional
    """
    # ============================================================
    # CONFIGURAÇÃO DO SERVIDOR
    # ============================================================
    # Escuta em todas as interfaces de rede (0.0.0.0) para permitir acesso externo
    server_address = ('0.0.0.0', http_port)
    
    # Cria a classe handler com o contexto completo
    handler_class = create_handler_with_context(
        current_frame, frame_lock, connected_clients, latency_metrics, 
        html_content, system_monitor, fps_capture_shared, fps_transmission_shared
    )
    
    # Cria a instância do servidor HTTP
    httpd = HTTPServer(server_address, handler_class)
    
    # ============================================================
    # CONFIGURAÇÃO SSL/TLS
    # ============================================================
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)  # Contexto TLS para o servidor
    
    # Caminhos para os ficheiros de certificado e chave
    cert_file = "certs/certTwo.pem"
    key_file = "certs/keyTwo.pem"
    
    # Verifica se os certificados existem; se não, gera autoassinados
    if not os.path.exists(cert_file):
        print(f"\nArquivo de certificado '{cert_file}' não encontrado!")
        print("Geração de certificado auto-assinado...")
        generate_self_signed_cert()  # Gera certificados autoassinados
    
    try:
        # Carrega o certificado e a chave privada
        context.load_cert_chain(certfile=cert_file, keyfile=key_file)
        
        # Envolve o socket do servidor com SSL/TLS
        httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
        
        # Obtém o IP do servidor para exibição
        from src.utils.network import get_ip_address
        server_ip = get_ip_address()
        
        # ============================================================
        # INFORMAÇÕES DO SERVIDOR
        # ============================================================
        print(f"\nServidor HTTPS: Em execução em https://{server_ip}:{http_port}")
        print(f"   Também disponível em: https://localhost:{http_port}")
        print(f"   Ponto final de métricas: https://{server_ip}:{http_port}/metrics")
        
        # ============================================================
        # LOOP PRINCIPAL DO SERVIDOR
        # ============================================================
        # Mantém o servidor em execução até ser interrompido
        httpd.serve_forever()
        
    except Exception as e:
        # Em caso de erro ao iniciar o servidor, exibe a mensagem e levanta a exceção
        print(f"Falha ao iniciar o servidor HTTPS: {e}")
        raise