import sys
import os

# ============================================================
# ADIÇÃO DO DIRETÓRIO SRC AO PATH DO PYTHON
# ============================================================
# Isto permite importar os módulos do projeto corretamente
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ============================================================
# IMPORTAÇÃO DOS MÓDULOS DO PROJETO
# ============================================================
from src.camera.device_manager import select_camera
from src.camera.capture import capture_frames
from src.metrics.latency_tracker import latency_metrics, print_latency_summary
from src.metrics.metrics_collector import MetricsCollector
from src.metrics.reporters import MetricsReporter
from src.metrics.system_monitor import SystemMonitor
from src.server.http_server import run_http_server
from src.server.streaming_server import run_websocket_server
from src.utils.network import get_ip_address, check_port_available, get_system_info
from src.utils.ssl_helper import generate_self_signed_cert, check_certificates
from src.utils.logger import setup_logger
from src.web import get_html_content

# ============================================================
# IMPORTAÇÃO DE BIBLIOTECAS STANDARD
# ============================================================
import threading
import time
import socket
import platform
import cv2
import numpy as np
from typing import Optional

# ============================================================
# VARIÁVEIS GLOBAIS PARTILHADAS ENTRE THREADS
# ============================================================

# Armazenamento do frame global (partilhado entre threads)
# Usa uma lista para permitir mutabilidade (a lista é imutável, o conteúdo é mutável)
current_frame = [None]
frame_lock = threading.Lock()  # Lock para acesso thread-safe ao frame

# Tempo T1 partilhado entre a thread de captura e o servidor WebSocket
capture_t1_shared = [0.0]

# FPS de captura (partilhado com outros módulos)
fps_capture_shared = [0.0]

# FPS de transmissão (partilhado com outros módulos)
fps_transmission_shared = [0.0]

# ============================================================
# CONFIGURAÇÃO DO SERVIDOR
# ============================================================
SERVER_IP = get_ip_address()  # Obtém o IP local do servidor
HTTP_PORT = 8000  # Porta para o servidor HTTPS
WS_PORT = 3001    # Porta para o servidor WebSocket

# ============================================================
# INICIALIZAÇÃO DE COMPONENTES
# ============================================================

# Configuração do logger
logger = setup_logger(__name__)

# Carrega o conteúdo HTML para a interface web
html_content = get_html_content()

# Inicializa o coletor de métricas (histórico de até 1000 amostras)
metrics_collector = MetricsCollector(max_history=1000)

# Inicializa o gerador de relatórios (imprime automaticamente a cada 10 segundos)
metrics_reporter = MetricsReporter(auto_print=True, print_interval=10)

# Conjunto de clientes conectados ao WebSocket
connected_clients = set()


def main():
    """
    Função principal do servidor.
    Coordena a inicialização de todos os componentes e mantém o servidor em execução.
    """
    global current_frame

    # ============================================================
    # INFORMAÇÕES DO SERVIDOR
    # ============================================================
    print("\n" + "="*60)
    print("Servidor de streaming de vídeo OMRISK")
    print("="*60)
    print(f"Version: 1.0.0")
    sys_info = get_system_info()
    print(f"IP do servidor: {sys_info['ip_address']}")
    print(f"Nome do host: {sys_info['hostname']}")
    print(f"Plataforma: {sys_info['platform']}")
    print(f"Python: {sys_info['python_version']}")
    
    # ============================================================
    # VERIFICAÇÃO DA VERSÃO DO PYTHON
    # ============================================================
    if sys.version_info < (3, 7):
        print("Python 3.7 or higher is required")
        return

    # ============================================================
    # VERIFICAÇÃO DE CONFLITOS DE PORTAS
    # ============================================================
    print("\nVerificação de conflitos de portas...")
    if not check_port_available(3001, '127.0.0.1'):
        print("A porta 3001 já está em utilização!")
        print("   O servidor tentará portas alternativas. (3002, 3003, etc.)")
    
    # ============================================================
    # SELEÇÃO DA CÂMARA
    # ============================================================
    print("\nSeleção de câmara")
    print("-" * 40)
    camera_index = select_camera()  # Permite ao utilizador escolher a câmara
    if camera_index is None:
        print("Nenhuma câmara selecionada. Saindo.")
        return
    
    # ============================================================
    # VERIFICAÇÃO DE CERTIFICADOS SSL
    # ============================================================
    print("\nVerificação de certificado SSL")
    print("-" * 40)
    if not check_certificates():  # Verifica se os certificados existem
        generate_self_signed_cert()  # Gera certificados autoassinados se necessário
    
    # ============================================================
    # INICIALIZAÇÃO DO MONITOR DO SISTEMA (CPU/RAM)
    # ============================================================
    print("\nMonitor de arranque do sistema")
    print("-" * 40)
    system_monitor = SystemMonitor(interval=1.0, max_samples=120)
    system_monitor.start()  # Inicia a monitorização numa thread de fundo
    
    # ============================================================
    # INICIALIZAÇÃO DA CAPTURA DE IMAGEM
    # ============================================================
    print("\nIniciar a captura de vídeo")
    print("-" * 40)
    
    def capture_wrapper():
        """Wrapper para a função de captura (executada na thread)"""
        capture_frames(camera_index, current_frame, frame_lock, latency_metrics, 
                      capture_t1_shared, fps_capture_shared)
    
    # Cria e inicia a thread de captura
    camera_thread = threading.Thread(
        target=capture_wrapper,
        daemon=True,
        name="Camera-Capture"
    )
    camera_thread.start()
    
    # Aguarda a inicialização da câmara
    print("Aguarda-se a inicialização da câmara....")
    time.sleep(2)
    
    # ============================================================
    # VERIFICAÇÃO DO PRIMEIRO FRAME
    # ============================================================
    print("Aguarda-se o primeiro quadro...")
    frame_timeout = 10  # Tempo máximo de espera (segundos)
    start_wait = time.time()
    frame_received = False
    
    # Aguarda até receber o primeiro frame ou atingir o timeout
    while (time.time() - start_wait) < frame_timeout:
        with frame_lock:
            if current_frame[0] is not None:
                frame_received = True
                print(f"\nPrimeiro quadro recebido! Formato: {current_frame[0].shape}")
                break
        print(".", end="", flush=True)  # Indicador visual de progresso
        time.sleep(0.5)
    
    # Se não recebeu frame, termina o programa
    if not frame_received:
        print("\nNenhuma imagem recebida da câmara após 10 segundos!")
        print("Verifique a ligação e as permissões da câmara.")
        return
    
    # ============================================================
    # INICIALIZAÇÃO DO SERVIDOR HTTP
    # ============================================================
    print("\nIniciar o servidor HTTP")
    print("-" * 40)
    http_thread = threading.Thread(
        target=run_http_server,
        args=(HTTP_PORT, current_frame, frame_lock, connected_clients, 
              latency_metrics, html_content, system_monitor, 
              fps_capture_shared, fps_transmission_shared),
        daemon=True,
        name="HTTP-Server"
    )
    http_thread.start()
    time.sleep(1)  # Aguarda o servidor iniciar
    
    # ============================================================
    # INICIALIZAÇÃO DO SERVIDOR WEBSOCKET
    # ============================================================
    print("\nIniciar o servidor WebSocket")
    print("-" * 40)
    ws_thread = threading.Thread(
        target=run_websocket_server,
        args=(WS_PORT, current_frame, frame_lock, connected_clients, 
              latency_metrics, capture_t1_shared, fps_transmission_shared),
        daemon=True,
        name="WebSocket-Server"
    )
    ws_thread.start()
    
    # Aguarda os servidores iniciarem
    time.sleep(2)
    
    # ============================================================
    # EXIBIÇÃO DO ESTADO DO SERVIDOR
    # ============================================================
    print("\n" + "="*60)
    print("OS SERVIDORES ESTÃO A FUNCIONAR")
    print("="*60)
    print(f"\nAbra o seu navegador e visite:")
    print(f"   https://{SERVER_IP}:{HTTP_PORT}")
    print(f"   ou")
    print(f"   https://localhost:{HTTP_PORT}")
    
    print("\nEndpoints disponíveis:")
    print(f"   - /         - Painel de streaming")
    print(f"   - /debug    - Visualização de depuração da câmara")
    print(f"   - /health   - Estado de saúde do sistema")
    print(f"   - /metrics  - Métricas de latência (JSON)")
    
    print("\nAs métricas de latência serão apresentadas.:")
    print("   T1 - Tempo de captura (câmara para memória)")
    print("   T2 - Tempo de redimensionamento (escalonamento da imagem)")
    print("   T3 - Tempo de codificação (compressão JPEG)")
    print("   T4 - Processamento total do servidor (T1+T2+T3)")
    print("   T5 - Tempo de envio pela rede (transmissão WebSocket)")
    print("   T6 - Tempo de receção da rede (cliente)")
    print("   T7 - Tempo de descodificação (JPEG → bitmap)")
    print("   T8 - Tempo de inferência YOLO")
    print("   T9 - Tempo de desenho da sobreposição")
    print("   T10 - Tempo de renderização do vídeo")
    print("   TOTAL - Latência de ponta a ponta")
    
    print("\n📊 System metrics:")
    print("   💻 CPU: Average and peak usage")
    print("   🧠 RAM: Average and peak usage")
    print("   🎬 FPS: Capture and transmission rates")
    
    print("\n🛑 Press Ctrl+C to stop all servers")
    print("="*60)
    
    # ============================================================
    # IMPRESSÃO INICIAL DE MÉTRICAS
    # ============================================================
    time.sleep(1)
    print_latency_summary()
    
    # ============================================================
    # VARIÁVEIS PARA ESTATÍSTICAS DE FPS
    # ============================================================
    fps_capture_history = []  # Histórico de FPS de captura
    fps_transmission_history = []  # Histórico de FPS de transmissão
    fps_stats_interval = 10  # Intervalo para impressão de estatísticas (segundos)
    
    # ============================================================
    # LOOP PRINCIPAL (MANTÉM O SERVIDOR EM EXECUÇÃO)
    # ============================================================
    try:
        last_summary_time = time.time()
        last_fps_stats_time = time.time()
        
        while True:
            time.sleep(1)  # Aguarda 1 segundo entre iterações
            
            # ============================================================
            # IMPRESSÃO DO RESUMO DE LATÊNCIA (A CADA 10 SEGUNDOS)
            # ============================================================
            current_time = time.time()
            if current_time - last_summary_time >= 10:
                print_latency_summary()
                last_summary_time = current_time
            
            # ============================================================
            # RECOLHA DE ESTATÍSTICAS DE FPS
            # ============================================================
            if fps_capture_shared[0] > 0:
                fps_capture_history.append(fps_capture_shared[0])
            if fps_transmission_shared[0] > 0:
                fps_transmission_history.append(fps_transmission_shared[0])
            
            # ============================================================
            # IMPRESSÃO DAS ESTATÍSTICAS DE FPS (A CADA 10 SEGUNDOS)
            # ============================================================
            if current_time - last_fps_stats_time >= fps_stats_interval:
                if fps_capture_history:
                    avg_cap = sum(fps_capture_history) / len(fps_capture_history)
                    max_cap = max(fps_capture_history)
                    min_cap = min(fps_capture_history)
                    print(f"\nESTATÍSTICAS DE FPS (last {len(fps_capture_history)} amostras):")
                    print(f"Capturar - Média: {avg_cap:.1f} | Máx: {max_cap:.1f} | Mín: {min_cap:.1f} FPS")
                
                if fps_transmission_history:
                    avg_tx = sum(fps_transmission_history) / len(fps_transmission_history)
                    max_tx = max(fps_transmission_history)
                    min_tx = min(fps_transmission_history)
                    print(f"Transmissão - Média: {avg_tx:.1f} | Máx: {max_tx:.1f} | Mín: {min_tx:.1f} FPS")
                
                # Reinicia os históricos após a impressão
                fps_capture_history = []
                fps_transmission_history = []
                last_fps_stats_time = current_time
            
            # ============================================================
            # EXIBIÇÃO DO ESTADO EM TEMPO REAL (LINHA ÚNICA)
            # ============================================================
            with frame_lock:
                frame_status = "Active" if current_frame[0] is not None else "No frame"
            
            current_t1 = capture_t1_shared[0] if capture_t1_shared[0] > 0 else 0
            current_fps_cap = fps_capture_shared[0] if fps_capture_shared else 0
            current_fps_tx = fps_transmission_shared[0] if fps_transmission_shared else 0
            
            # Obtém estatísticas do sistema
            stats = system_monitor.get_stats()
            cpu = stats['cpu']['current']
            ram = stats['ram']['current']
            
            print(f"\r📊 Estado: Câmera: {frame_status} | "
                  f"T1: {current_t1:.1f}ms | "
                  f"FPS Cap: {current_fps_cap:.1f} | "
                  f"FPS Tx: {current_fps_tx:.1f} | "
                  f"CPU: {cpu:.1f}% | "
                  f"RAM: {ram:.0f}MB | "
                  f"Clientes: {len(connected_clients)} | "
                  f"Prima Ctrl+C para parar", end="")
                  
    except KeyboardInterrupt:
        # ============================================================
        # ENCERRAMENTO (CTRL+C)
        # ============================================================
        print("\n\n" + "="*60)
        print("Desligando os servidores...")
        print("="*60)
        
        # ============================================================
        # IMPRESSÃO DAS ESTATÍSTICAS FINAIS
        # ============================================================
        print("\nRESUMO FINAL DA LATÊNCIA:")
        print_latency_summary()
        
        print("\nMÉDIAS GERAIS:")
        metric_names = {
            't1_capture': 'T1 Capture',
            't2_resize': 'T2 Resize',
            't3_encode': 'T3 Encode',
            't4_total_server': 'T4 Server Total',
            't5_network_send': 'T5 Network Send',
            't2_processing': 'Processing (Legacy)'
        }
        
        for metric_key, metric_name in metric_names.items():
            if metric_key in latency_metrics and latency_metrics[metric_key]:
                values = latency_metrics[metric_key]
                avg = sum(values) / len(values)
                print(f"{metric_name:20s}: {avg:6.2f}ms ({len(values)} amostras)")
        
        # ============================================================
        # IMPRESSÃO DAS ESTATÍSTICAS DO SISTEMA
        # ============================================================
        stats = system_monitor.get_stats()
        print("\nESTATÍSTICAS DO SISTEMA:")
        print(f"  Média de CPU: {stats['cpu']['avg']:.1f}%")
        print(f"  Pico de CPU:    {stats['cpu']['max']:.1f}%")
        print(f"  RAM média: {stats['ram']['avg']:.1f} MB")
        print(f"  Pico RAM:    {stats['ram']['max']:.1f} MB")
        print(f"  RAM Total:   {stats['ram']['total_mb']:.1f} MB")
        print(f"  Amostras:     {stats['cpu']['samples']}")
        
        # ============================================================
        # IMPRESSÃO DAS ESTATÍSTICAS DE FPS
        # ============================================================
        print("\nESTATÍSTICAS DE FPS (Final):")
        
        # Estatísticas de FPS de captura
        capture_fps_values = latency_metrics.get('fps_capture', [])
        if capture_fps_values:
            print(f"Capture FPS:")
            print(f"    Média: {sum(capture_fps_values)/len(capture_fps_values):.1f} FPS")
            print(f"    Máximo: {max(capture_fps_values):.1f} FPS")
            print(f"    Mínimo: {min(capture_fps_values):.1f} FPS")
            print(f"    Amostras: {len(capture_fps_values)}")
        else:
            print(f"Captura de FPS: Nenhum dado recolhido")
        
        # Estatísticas de FPS de transmissão
        transmission_fps_values = latency_metrics.get('fps_transmission', [])
        if transmission_fps_values:
            print(f"FPS de transmissão:")
            print(f"    Média: {sum(transmission_fps_values)/len(transmission_fps_values):.1f} FPS")
            print(f"    Máximo: {max(transmission_fps_values):.1f} FPS")
            print(f"    Mínimo: {min(transmission_fps_values):.1f} FPS")
            print(f"    Amostras: {len(transmission_fps_values)}")
        else:
            print(f"FPS de transmissão: Nenhum dado recolhido (nenhum cliente ligado)")
        
        # ============================================================
        # LIMPEZA DE RECURSOS
        # ============================================================
        with frame_lock:
            current_frame[0] = None
        
        system_monitor.stop()  # Para a monitorização do sistema
        
        print("\nTodos os servidores foram interrompidos. Adeus!")
        print("="*60)
        
    except Exception as e:
        # ============================================================
        # TRATAMENTO DE ERROS INESPERADOS
        # ============================================================
        print(f"\nErro inesperado no loop principal: {e}")
        import traceback
        traceback.print_exc()


# ============================================================
# PONTO DE ENTRADA DO PROGRAMA
# ============================================================
if __name__ == "__main__":
    # ============================================================
    # LISTA DE PACOTES REQUERIDOS
    # ============================================================
    required_packages = [
        "websockets",
        "opencv-python",
        "numpy",
        "psutil"
    ]
    
    print("Pacotes Python necessários:")
    for pkg in required_packages:
        print(f"    -> {pkg}")
    
    print("\nInstalar com:")
    print("  sudo apt install python3-psutil  # Para psutil")
    print("  pip install websockets opencv-python numpy  # venv")
    print("="*60)
    
    # ============================================================
    # VERIFICAÇÃO DE UTILITÁRIOS V4L2
    # ============================================================
    print("\nA verificar os utilitários V4L2...")
    if os.system("which v4l2-ctl > /dev/null 2>&1") != 0:
        print("O pacote v4l2-ctl não foi encontrado. Instale com: sudo apt install v4l-utils")
    else:
        print("O pacote v4l2-ctl está disponível.")
    
    # ============================================================
    # VERIFICAÇÃO DE CONFLITOS DE PORTAS
    # ============================================================
    print("\nVerificação de conflitos de portas...")
    try:
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.settimeout(1)
        result = test_socket.connect_ex(('127.0.0.1', 3001))
        if result == 0:
            print("A porta 3001 já está em utilização!")
            print("   O servidor tentará portas alternativas (3002, 3003, etc.)")
        test_socket.close()
    except:
        pass
    
    # ============================================================
    # EXECUÇÃO DA FUNÇÃO PRINCIPAL
    # ============================================================
    try:
        main()
    except Exception as e:
        print(f"\nErro fatal: {e}")
        import traceback
        traceback.print_exc()