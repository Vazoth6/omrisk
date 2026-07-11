import cv2
import time
import numpy as np
from typing import Optional, List


def capture_frames(camera_index, current_frame, frame_lock, latency_metrics, 
                   capture_t1_shared, fps_shared=None):
    """
    Captura frames da câmara selecionada com medição de latência.

    Args:
        camera_index: Índice da câmara ou caminho do dispositivo
        current_frame: Lista que contém o frame global (para permitir mutabilidade)
        frame_lock: Lock para acesso thread-safe ao frame
        latency_metrics: Dicionário para armazenar métricas de latência
        capture_t1_shared: Lista para partilhar o tempo T1 com o servidor WebSocket
        fps_shared: Lista opcional para partilhar o valor de FPS com outros módulos
    """
    print(f"\nInicializando a câmara {camera_index}...")  # Mensagem de inicialização da câmara
    
    # Utiliza o backend V4L2 para Linux
    if isinstance(camera_index, str) and camera_index.startswith('/dev/video'):
        # Se for um caminho de dispositivo, usa-o diretamente
        cap = cv2.VideoCapture(camera_index, cv2.CAP_V4L2)
    else:
        # Caso contrário, usa o índice numérico
        cap = cv2.VideoCapture(camera_index, cv2.CAP_V4L2)
    
    # Verifica se a câmara foi aberta com sucesso
    if not cap.isOpened():
        print(f"Erro: Não foi possível abrir a câmara {camera_index}")
        print("Tente selecionar uma câmara diferente")
        return
    
    # Tenta definir propriedades ótimas para V4L2
    try:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)   # Define a largura do frame
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)  # Define a altura do frame
        cap.set(cv2.CAP_PROP_FPS, 30)            # Define a taxa de frames por segundo
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))  # Define o codec MJPG
    except Exception as e:
        print(f"Nota: Utilizando as definições padrão da câmara ({e})")  # Aviso caso não seja possível definir as propriedades
    
    # Obtém as propriedades reais da câmara
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    print(f"Configurações da câmara: {width}x{height} a {fps:.1f} FPS")  # Mostra as configurações da câmara
    print("Prima Ctrl+C no terminal para interromper a captura")  # Instrução para parar a captura
    
    # Inicializa variáveis de controlo
    frame_count = 0
    start_time = time.time()
    last_print_time = time.time()
    last_fps_update = time.time()
    fps_frame_count = 0
    
    # Lista para armazenar os valores de T1 (tempo de captura) para estatísticas
    t1_values = []
    
    # Lista para armazenar os valores de FPS para estatísticas
    fps_values = []
    last_fps_record_time = time.time()
    
    try:
        # Loop principal de captura - executa continuamente até ser interrompido
        while True:
            # ============================================================
            # MEDIÇÃO DO TEMPO T1: LATÊNCIA DE CAPTURA
            # ============================================================
            t1_start = time.perf_counter_ns()  # Regista o tempo antes da leitura
            ret, frame = cap.read()  # Lê o frame da câmara
            t1_end = time.perf_counter_ns()  # Regista o tempo após a leitura
            
            # Se não conseguiu ler o frame, tenta novamente
            if not ret:
                print("Erro: não foi possível ler o quadro")
                time.sleep(0.1)  # Pequena pausa antes de tentar novamente
                continue
            
            # Calcula o tempo T1 em milissegundos
            t1_capture = (t1_end - t1_start) / 1_000_000
            
            # ============================================================
            # PARTILHA DO VALOR T1 COM O SERVIDOR WEBSOCKET
            # ============================================================
            if capture_t1_shared is not None:
                capture_t1_shared[0] = t1_capture  # Atualiza o valor partilhado
            
            # Armazena o valor T1 para estatísticas (mantém apenas os últimos 100)
            t1_values.append(t1_capture)
            if len(t1_values) > 100:
                t1_values.pop(0)  # Remove o valor mais antigo
            
            # ============================================================
            # ARMAZENAMENTO DO FRAME COM PROTEÇÃO POR LOCK
            # ============================================================
            with frame_lock:  # Adquire o lock para acesso thread-safe
                current_frame[0] = frame.copy()  # Guarda uma cópia do frame
            
            # ============================================================
            # ATUALIZAÇÃO DE CONTADORES E CÁLCULO DO FPS
            # ============================================================
            frame_count += 1
            fps_frame_count += 1
            
            # Atualiza o FPS partilhado a cada segundo
            current_time = time.time()
            if current_time - last_fps_update >= 1.0:
                # Calcula o FPS (frames por segundo)
                fps_calc = fps_frame_count / (current_time - last_fps_update)
                
                # Partilha o valor de FPS com outros módulos
                if fps_shared is not None and isinstance(fps_shared, list):
                    fps_shared[0] = fps_calc
                
                # Armazena o valor de FPS para estatísticas
                fps_values.append(fps_calc)
                if len(fps_values) > 1000:  # Mantém apenas os últimos 1000 valores
                    fps_values.pop(0)
                
                # Armazena no dicionário de métricas para estatísticas finais
                if 'fps_capture' not in latency_metrics:
                    latency_metrics['fps_capture'] = []
                latency_metrics['fps_capture'].append(fps_calc)
                
                # Reinicia os contadores para o próximo segundo
                fps_frame_count = 0
                last_fps_update = current_time
            
            # ============================================================
            # IMPRESSÃO PERIÓDICA DO ESTADO (A CADA 2 SEGUNDOS)
            # ============================================================
            current_time = time.time()
            if current_time - last_print_time >= 2:
                # Calcula o FPS médio desde o início
                elapsed = current_time - start_time
                fps_calc = frame_count / elapsed
                
                # Calcula a média dos valores T1
                avg_t1 = sum(t1_values) / len(t1_values) if t1_values else 0
                
                # Calcula as estatísticas de FPS
                if fps_values:
                    avg_fps = sum(fps_values) / len(fps_values)
                    max_fps = max(fps_values)
                    min_fps = min(fps_values)
                else:
                    avg_fps = max_fps = min_fps = 0
                
                # Apresenta o estado detalhado da captura
                print(f"\n{'='*50}")
                print(f"📊 STATUS DE CAPTURA (Servidor)")
                print(f"{'='*50}")
                print(f"  Frames: {frame_count} | FPS: {fps_calc:.1f}")
                print(f"  Tamanho do frame: {frame.shape[1]}x{frame.shape[0]}")
                print(f"    Captura T1 (último): {t1_capture:.2f}ms")
                print(f"    Captura T1 (média):  {avg_t1:.2f}ms")
                print(f"\nEstatísticas FPS (último {len(fps_values)} amostras):")
                print(f"     Média: {avg_fps:.1f} | Máx: {max_fps:.1f} | Mín: {min_fps:.1f}")
                
                # Verifica se o frame foi armazenado corretamente
                with frame_lock:
                    if current_frame[0] is not None:
                        print(f"Quadro armazenado com sucesso")
                    else:
                        print(f"AVISO: falha no armazenamento do quadro!")
                
                print(f"{'='*50}\n")
                
                last_print_time = current_time  # Atualiza o tempo da última impressão
            
            # ============================================================
            # PEQUENA PAUSA PARA EVITAR SOBRECARGA DA CPU
            # ============================================================
            # Ajusta o delay para atingir o FPS pretendido, com uma pequena margem
            time.sleep(max(0, (1.0/fps) - 0.005))
            
    # ============================================================
    # TRATAMENTO DE INTERRUPÇÕES E EXCEÇÕES
    # ============================================================
    except KeyboardInterrupt:
        print("\nCaptura interrompida pelo utilizador")  # Utilizador interrompeu a captura
    except Exception as e:
        print(f"Erro no loop de captura: {e}")  # Erro no loop de captura
        import traceback
        traceback.print_exc()  # Imprime o stack trace para depuração
    finally:
        # ============================================================
        # LIBERTAÇÃO DE RECURSOS
        # ============================================================
        cap.release()  # Liberta a câmara
        cv2.destroyAllWindows()  # Fecha quaisquer janelas abertas
        print("Câmara liberada")  # Confirma que a câmara foi libertada