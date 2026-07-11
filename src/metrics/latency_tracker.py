from typing import Dict, List

# ============================================================
# ARMAZENAMENTO GLOBAL DE MÉTRICAS DE LATÊNCIA
# ============================================================

# Dicionário que armazena listas de valores para cada métrica de latência
# Cada lista contém os valores em milissegundos (ms)
latency_metrics: Dict[str, List[float]] = {
    't1_capture': [],     # Tempo de captura da câmara (camera → memória)
    't2_processing': [],  # Tempo de processamento no servidor (redimensionamento + compressão)
    't3_network': [],     # Tempo de transmissão em rede (servidor → cliente)
    't4_decoding': [],    # Tempo de descodificação da imagem (JPEG → bitmap)
    't5_rendering': [],   # Tempo de renderização no ecrã (exibição)
    'total': []           # Tempo total (soma de todas as componentes)
}

def print_latency_summary():
    """
    Imprime um resumo das estatísticas de latência atuais.
    Esta função é chamada periodicamente para mostrar o estado do sistema.
    """
    print("\n" + "="*60)
    print("RESUMO DAS MÉTRICAS DE LATÊNCIA")
    print("="*60)
    
    # Verifica se existem dados de latência
    if not latency_metrics['total']:
        print("Nenhum dado de latência recolhido ainda.")  # Ainda não há dados
        return
    
    # Itera sobre cada métrica e imprime as estatísticas
    for metric_name, values in latency_metrics.items():
        if values:  # Se a lista não estiver vazia
            avg = sum(values) / len(values)  # Valor médio
            min_val = min(values)            # Valor mínimo
            max_val = max(values)            # Valor máximo
            print(f"{metric_name.upper():15s} | Médio: {avg:6.2f}ms | Mín: {min_val:6.2f}ms | Máx: {max_val:6.2f}ms | Amostras: {len(values):3d}")
    
    # Imprime as métricas dos últimos 5 frames para análise detalhada
    print("-"*60)
    print("LATÊNCIA DO FRAME ATUAL (Últimos 5 frames):")
    for i in range(min(5, len(latency_metrics['total']))):
        idx = len(latency_metrics['total']) - i - 1  # Índice do frame (do mais recente para o mais antigo)
        if idx >= 0:
            print(f"Frame {idx+1:3d}: T1={latency_metrics['t1_capture'][idx]:5.1f}ms, "
                  f"T2={latency_metrics['t2_processing'][idx]:5.1f}ms, "
                  f"T3={latency_metrics['t3_network'][idx]:5.1f}ms, "
                  f"T4={latency_metrics['t4_decoding'][idx]:5.1f}ms, "
                  f"T5={latency_metrics['t5_rendering'][idx]:5.1f}ms, "
                  f"TOTAL={latency_metrics['total'][idx]:5.1f}ms")
    print("="*60)


def reset_metrics():
    """
    Reinicia todas as métricas de latência, limpando todos os dados armazenados.
    Útil para iniciar uma nova sessão de testes.
    """
    for key in latency_metrics:
        latency_metrics[key] = []  # Esvazia cada lista
    print("As métricas de latência foram redefinidas")


def get_metric_statistics(metric_name: str) -> dict:
    """
    Obtém estatísticas para uma métrica específica.

    Args:
        metric_name: Nome da métrica (ex: 't1_capture', 'total')

    Returns:
        dict: Dicionário com as estatísticas da métrica (média, mínimo, máximo, etc.)
              Se a métrica não existir, retorna um dicionário com erro.
    """
    # Verifica se a métrica existe
    if metric_name not in latency_metrics:
        return {'error': f'Métrica {metric_name} não encontrada'}
    
    values = latency_metrics[metric_name]  # Obtém a lista de valores
    
    # Se não houver dados, retorna valores padrão
    if not values:
        return {'samples': 0, 'avg': 0, 'min': 0, 'max': 0}
    
    # Calcula e retorna as estatísticas
    return {
        'samples': len(values),                                           # Número de amostras
        'avg': sum(values) / len(values),                                 # Valor médio
        'min': min(values),                                              # Valor mínimo
        'max': max(values),                                              # Valor máximo
        'last_10_avg': sum(values[-10:]) / min(10, len(values))          # Média dos últimos 10 valores
    }


def get_all_metrics_summary() -> dict:
    """
    Obtém um resumo de todas as métricas de latência.

    Returns:
        dict: Dicionário contendo as estatísticas de todas as métricas
    """
    summary = {}  # Dicionário para armazenar o resumo
    for metric_name in latency_metrics:  # Itera sobre todas as métricas
        summary[metric_name] = get_metric_statistics(metric_name)  # Adiciona as estatísticas
    return summary