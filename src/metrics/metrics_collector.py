# src/metrics/metrics_collector.py

import time
import json
from typing import Dict, List, Optional
from datetime import datetime
from .latency_tracker import latency_metrics, get_all_metrics_summary


class MetricsCollector:
    """
    Coletor para gerir e agregar métricas de latência.
    Esta classe fornece uma interface para adicionar, consultar e exportar métricas.
    """
    
    def __init__(self, max_history: int = 1000):
        """
        Inicializa o coletor de métricas.

        Args:
            max_history: Número máximo de amostras a manter por métrica
        """
        self.max_history = max_history  # Limite de amostras por métrica
        self.start_time = time.time()   # Tempo de início da recolha
        self.frame_count = 0            # Contador de frames processados
        self._last_report_time = time.time()  # Tempo do último relatório
    
    def add_metric(self, metric_name: str, value: float):
        """
        Adiciona um único valor de métrica.

        Args:
            metric_name: Nome da métrica (ex: 't1_capture', 'total')
            value: Valor da métrica em milissegundos
        """
        # Se a métrica ainda não existe, cria uma nova lista
        if metric_name not in latency_metrics:
            latency_metrics[metric_name] = []
        
        # Adiciona o valor à lista da métrica
        latency_metrics[metric_name].append(value)
        
        # Remove valores antigos se exceder o limite máximo
        if len(latency_metrics[metric_name]) > self.max_history:
            latency_metrics[metric_name] = latency_metrics[metric_name][-self.max_history:]
    
    def add_frame_metrics(self, frame_metrics: Dict[str, float]):
        """
        Adiciona todas as métricas de um único frame.

        Args:
            frame_metrics: Dicionário com as métricas do frame (ex: {'t1_capture': 5.2, 'total': 45.3})
        """
        # Itera sobre cada métrica do frame
        for metric_name, value in frame_metrics.items():
            # Verifica se a métrica existe no dicionário global
            if metric_name in latency_metrics:
                latency_metrics[metric_name].append(value)
                # Remove valores antigos se exceder o limite
                if len(latency_metrics[metric_name]) > self.max_history:
                    latency_metrics[metric_name] = latency_metrics[metric_name][-self.max_history:]
        
        # Incrementa o contador de frames
        self.frame_count += 1
    
    def get_current_fps(self) -> float:
        """
        Calcula o FPS (frames por segundo) atual com base no número de frames processados.

        Returns:
            float: FPS atual
        """
        elapsed = time.time() - self.start_time  # Tempo decorrido desde o início
        if elapsed > 0:
            return self.frame_count / elapsed  # FPS = frames / tempo
        return 0.0  # Retorna 0 se não houve tempo decorrido
    
    def get_average_latency(self, metric_name: str, last_n: Optional[int] = None) -> float:
        """
        Obtém a latência média para uma métrica específica.

        Args:
            metric_name: Nome da métrica
            last_n: Número de amostras a considerar (None para todas)

        Returns:
            float: Latência média em milissegundos
        """
        # Verifica se a métrica existe
        if metric_name not in latency_metrics:
            return 0.0
        
        values = latency_metrics[metric_name]  # Obtém os valores da métrica
        if not values:  # Se não houver valores
            return 0.0
        
        # Se foi especificado um número de amostras, usa apenas as últimas N
        if last_n:
            values = values[-last_n:]
        
        return sum(values) / len(values)  # Calcula e retorna a média
    
    def get_total_average_latency(self, last_n: Optional[int] = None) -> float:
        """
        Obtém a latência total média.

        Args:
            last_n: Número de amostras a considerar (None para todas)

        Returns:
            float: Latência total média em milissegundos
        """
        return self.get_average_latency('total', last_n)
    
    def get_metrics_summary(self) -> dict:
        """
        Obtém um resumo abrangente das métricas.

        Returns:
            dict: Dicionário com o resumo das métricas, incluindo timestamp, uptime, FPS e estatísticas
        """
        return {
            'timestamp': time.time(),                                       # Timestamp atual
            'uptime_seconds': time.time() - self.start_time,                # Tempo de atividade em segundos
            'total_frames': self.frame_count,                              # Total de frames processados
            'current_fps': self.get_current_fps(),                         # FPS atual
            'metrics': get_all_metrics_summary()                           # Estatísticas de todas as métricas
        }
    
    def export_to_json(self, filepath: Optional[str] = None) -> str:
        """
        Exporta as métricas para formato JSON.

        Args:
            filepath: Caminho do ficheiro onde guardar o JSON (opcional)

        Returns:
            str: String JSON com os dados exportados
        """
        # Estrutura de dados para exportação
        data = {
            'export_time': datetime.now().isoformat(),  # Data/hora da exportação
            'collector_info': {
                'start_time': datetime.fromtimestamp(self.start_time).isoformat(),  # Data/hora de início
                'total_frames': self.frame_count,                                  # Total de frames
                'max_history': self.max_history                                    # Limite de histórico
            },
            'metrics': {}  # Dicionário para as métricas
        }
        
        # Itera sobre todas as métricas
        for metric_name, values in latency_metrics.items():
            if values:  # Se existirem valores
                data['metrics'][metric_name] = {
                    'samples': len(values),          # Número de amostras
                    'values': values,                # Todos os valores
                    'statistics': {                  # Estatísticas
                        'avg': sum(values) / len(values),  # Média
                        'min': min(values),                # Mínimo
                        'max': max(values)                 # Máximo
                    }
                }
        
        # Se foi fornecido um caminho, guarda o ficheiro
        if filepath:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)  # Guarda com indentação para legibilidade
        
        return json.dumps(data, indent=2)  # Retorna a string JSON
    
    def reset(self):
        """
        Reinicia todas as métricas recolhidas.
        Útil para iniciar uma nova sessão de testes.
        """
        # Limpa todas as listas de métricas
        for key in latency_metrics:
            latency_metrics[key] = []
        # Reinicia os contadores
        self.start_time = time.time()
        self.frame_count = 0
        print("✅ MetricsCollector has been reset")
    
    def should_report(self, interval_seconds: int = 5) -> bool:
        """
        Verifica se já está na altura de gerar um relatório de métricas.

        Args:
            interval_seconds: Intervalo em segundos entre relatórios

        Returns:
            bool: True se já passou o intervalo, False caso contrário
        """
        current_time = time.time()
        # Verifica se já passou o intervalo desde o último relatório
        if current_time - self._last_report_time >= interval_seconds:
            self._last_report_time = current_time  # Atualiza o tempo do último relatório
            return True
        return False