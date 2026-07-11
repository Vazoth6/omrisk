import cv2
import numpy as np
from typing import Optional

def add_timestamp_to_frame(frame: np.ndarray, timestamp_ns: int) -> np.ndarray:
    """
    Adiciona um timestamp como texto sobreposto no frame.
    
    Args:
        frame: Imagem de entrada como array NumPy
        timestamp_ns: Timestamp em nanossegundos
    
    Returns:
        np.ndarray: Cópia do frame com o timestamp sobreposto
    """
    frame_copy = frame.copy()  # Cria uma cópia do frame para não modificar o original
    timestamp_ms = timestamp_ns // 1_000_000  # Converte nanossegundos para milissegundos
    
    # Adiciona o texto do timestamp no canto superior esquerdo do frame
    cv2.putText(frame_copy, f"TS:{timestamp_ms}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    # Parâmetros: (imagem, texto, posição, tipo de fonte, escala, cor (BGR), espessura)
    
    return frame_copy


def process_frame(frame: np.ndarray, max_dimension: int = 1280, 
                  quality: int = 70, add_timestamp: bool = True, 
                  timestamp_ns: Optional[int] = None) -> tuple:
    """
    Processa um frame: redimensiona, adiciona timestamp e codifica para JPEG.
    
    Args:
        frame: Imagem de entrada como array NumPy
        max_dimension: Dimensão máxima para redimensionamento (mantém a proporção)
        quality: Qualidade JPEG (0-100, onde 100 é a melhor qualidade)
        add_timestamp: Se True, adiciona timestamp sobreposto no frame
        timestamp_ns: Timestamp em nanossegundos (se None, usa o tempo atual)
    
    Returns:
        tuple: (buffer_codificado, tempo_processamento_ms, frame_com_timestamp)
    """
    import time  # Importa a biblioteca para medição de tempo dentro da função
    
    # ============================================================
    # PASSO 1: REDIMENSIONAMENTO DO FRAME
    # ============================================================
    height, width = frame.shape[:2]  # Obtém a altura e largura do frame
    
    # Se a largura for superior à dimensão máxima, redimensiona proporcionalmente
    if width > max_dimension:
        scale = max_dimension / width  # Fator de escala
        new_width = max_dimension       # Nova largura é a máxima permitida
        new_height = int(height * scale)  # Nova altura mantém a proporção
        frame_resized = cv2.resize(frame, (new_width, new_height))
    else:
        frame_resized = frame  # Mantém o frame original se não exceder o limite
    
    # ============================================================
    # PASSO 2: ADIÇÃO DE TIMESTAMP (SE SOLICITADO)
    # ============================================================
    if add_timestamp:
        # Se não foi fornecido timestamp, usa o tempo atual
        if timestamp_ns is None:
            timestamp_ns = int(time.time() * 1_000_000_000)  # Tempo atual em nanossegundos
        frame_with_ts = add_timestamp_to_frame(frame_resized, timestamp_ns)
    else:
        frame_with_ts = frame_resized  # Mantém o frame sem timestamp
    
    # ============================================================
    # PASSO 3: CODIFICAÇÃO PARA JPEG
    # ============================================================
    encode_start = time.perf_counter_ns()  # Regista o tempo antes da codificação
    
    # Codifica o frame para JPEG com a qualidade especificada
    _, buffer = cv2.imencode('.jpg', frame_with_ts, 
                             [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    
    encode_end = time.perf_counter_ns()  # Regista o tempo após a codificação
    
    # Calcula o tempo de processamento em milissegundos
    processing_time = (encode_end - encode_start) / 1_000_000  # Converte para ms
    
    return buffer, processing_time, frame_with_ts


def get_frame_info(frame: np.ndarray) -> dict:
    """
    Obtém informações detalhadas sobre um frame.
    
    Args:
        frame: Imagem de entrada como array NumPy
    
    Returns:
        dict: Dicionário com as propriedades do frame
    """
    # Verifica se o frame é válido
    if frame is None:
        return {'valid': False}
    
    # Retorna as propriedades do frame
    return {
        'valid': True,
        'shape': frame.shape,  # Tuplo com (altura, largura, canais)
        'width': frame.shape[1],  # Largura da imagem
        'height': frame.shape[0],  # Altura da imagem
        'channels': frame.shape[2] if len(frame.shape) > 2 else 1,  # Número de canais (RGB=3, escala de cinzentos=1)
        'dtype': str(frame.dtype),  # Tipo de dados (ex: uint8)
        'size_bytes': frame.nbytes  # Tamanho total em bytes
    }