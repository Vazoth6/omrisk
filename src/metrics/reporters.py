import time
import csv
import json
from typing import Optional, Callable
from datetime import datetime
from .latency_tracker import latency_metrics, print_latency_summary

class MetricsReporter:
    """
    Responsável pela geração de relatórios e exportação de métricas.
    Esta classe fornece funcionalidades para imprimir, exportar e gerar relatórios
    a partir dos dados de latência recolhidos.
    """
    
    def __init__(self, auto_print: bool = True, print_interval: int = 10):
        """
        Inicializa o gerador de relatórios de métricas.

        Args:
            auto_print: Se True, imprime resumos automaticamente
            print_interval: Intervalo em segundos entre impressões automáticas
        """
        self.auto_print = auto_print  # Ativa/desativa a impressão automática
        self.print_interval = print_interval  # Intervalo entre impressões
        self.last_print_time = time.time()  # Tempo da última impressão
        
    def print_summary(self):
        """
        Imprime um resumo das métricas de latência.
        Utiliza a função print_latency_summary do módulo latency_tracker.
        """
        print_latency_summary()
    
    def print_averages(self):
        """
        Imprime as médias globais de todas as métricas.
        Útil para obter uma visão geral do desempenho do sistema.
        """
        print("\nMÉDIAS GERAIS:")
        # Itera sobre todas as métricas
        for metric, values in latency_metrics.items():
            if values:  # Se existirem valores
                avg = sum(values) / len(values)  # Calcula a média
                print(f"{metric.upper():15s}: {avg:6.2f}ms ({len(values)} amostras)")
    
    def export_to_csv(self, filename: Optional[str] = None) -> str:
        """
        Exporta as métricas para um ficheiro CSV.

        Args:
            filename: Nome do ficheiro de saída (gerado automaticamente se None)

        Returns:
            str: Caminho do ficheiro CSV criado
        """
        # Se não foi fornecido nome, gera um com timestamp
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"latency_metrics_{timestamp}.csv"
        
        # Encontra o comprimento máximo de todas as listas de métricas
        max_length = max([len(values) for values in latency_metrics.values()]) if latency_metrics else 0
        
        # Abre o ficheiro para escrita
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            
            # Escreve o cabeçalho (nomes das métricas)
            headers = ['frame_index'] + list(latency_metrics.keys())
            writer.writerow(headers)
            
            # Escreve os dados linha por linha (cada linha corresponde a um frame)
            for i in range(max_length):
                row = [i + 1]  # Índice do frame (baseado em 1)
                for metric in latency_metrics.keys():
                    if i < len(latency_metrics[metric]):
                        row.append(f"{latency_metrics[metric][i]:.2f}")  # Valor com 2 casas decimais
                    else:
                        row.append('')  # Campo vazio se não houver valor
                writer.writerow(row)
        
        print(f"As métricas exportadas para: {filename}")
        return filename
    
    def export_to_json(self, filename: Optional[str] = None) -> str:
        """
        Exporta as métricas para um ficheiro JSON.

        Args:
            filename: Nome do ficheiro de saída (gerado automaticamente se None)

        Returns:
            str: Caminho do ficheiro JSON criado
        """
        # Se não foi fornecido nome, gera um com timestamp
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"latency_metrics_{timestamp}.json"
        
        # Estrutura de dados para exportação
        export_data = {
            'export_time': datetime.now().isoformat(),  # Data/hora da exportação
            'metrics': {}  # Dicionário para as métricas
        }
        
        # Itera sobre todas as métricas
        for metric_name, values in latency_metrics.items():
            if values:  # Se existirem valores
                export_data['metrics'][metric_name] = {
                    'samples': len(values),          # Número de amostras
                    'values': values,                # Todos os valores
                    'avg': sum(values) / len(values),  # Média
                    'min': min(values),              # Mínimo
                    'max': max(values)               # Máximo
                }
        
        # Guarda o ficheiro JSON com indentação para legibilidade
        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        print(f"As métricas exportadas para: {filename}")
        return filename
    
    def auto_report_loop(self, callback: Optional[Callable] = None):
        """
        Executa um loop de relatórios automáticos (para ser chamado numa thread).

        Args:
            callback: Função de callback opcional a chamar em cada relatório
        """
        try:
            while True:
                current_time = time.time()
                # Verifica se já passou o intervalo desde a última impressão
                if current_time - self.last_print_time >= self.print_interval:
                    self.print_summary()  # Imprime o resumo
                    self.last_print_time = current_time  # Atualiza o tempo
                    
                    # Se foi fornecido um callback, executa-o
                    if callback:
                        callback()
                
                time.sleep(1)  # Aguarda 1 segundo antes da próxima verificação
        except KeyboardInterrupt:
            print("\nRelatório automático interrompido")  # Interrompido pelo utilizador
    
    def generate_html_report(self, filename: Optional[str] = None) -> str:
        """
        Gera um relatório HTML a partir das métricas.

        Args:
            filename: Nome do ficheiro de saída (gerado automaticamente se None)

        Returns:
            str: Caminho do ficheiro HTML criado
        """
        # Se não foi fornecido nome, gera um com timestamp
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"latency_report_{timestamp}.html"
        
        # Calcula as estatísticas para cada métrica
        stats = {}
        for metric, values in latency_metrics.items():
            if values:  # Se existirem valores
                stats[metric] = {
                    'avg': sum(values) / len(values),  # Média
                    'min': min(values),                # Mínimo
                    'max': max(values),                # Máximo
                    'samples': len(values)             # Número de amostras
                }
        
        # ============================================================
        # GERAÇÃO DO CONTEÚDO HTML
        # ============================================================
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Latency Metrics Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            border-bottom: 2px solid #4CAF50;
            padding-bottom: 10px;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}
        .stat-card {{
            background: #f9f9f9;
            padding: 15px;
            border-radius: 5px;
            border-left: 4px solid #4CAF50;
        }}
        .stat-card h3 {{
            margin: 0 0 10px 0;
            color: #555;
        }}
        .stat-value {{
            font-size: 24px;
            font-weight: bold;
            color: #2196F3;
        }}
        .timestamp {{
            color: #999;
            font-size: 12px;
            margin-top: 20px;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Latency Metrics Report</h1>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        
        <div class="stats-grid">
"""
        
        # Adiciona um cartão de estatísticas para cada métrica
        for metric, stat in stats.items():
            html_content += f"""
            <div class="stat-card">
                <h3>{metric.upper()}</h3>
                <div class="stat-value">Avg: {stat['avg']:.2f}ms</div>
                <div>Min: {stat['min']:.2f}ms | Max: {stat['max']:.2f}ms</div>
                <div>Samples: {stat['samples']}</div>
            </div>
"""
        
        # Fecha o conteúdo HTML
        html_content += f"""
        </div>
        <div class="timestamp">
            Report generated by OMRisk Metrics Reporter
        </div>
    </div>
</body>
</html>
"""
        
        # Guarda o ficheiro HTML
        with open(filename, 'w') as f:
            f.write(html_content)
        
        print(f"Relatório HTML gerado: {filename}")
        return filename