import psutil
import time
import threading
from collections import deque
from typing import Optional


class SystemMonitor:
    """
    Monitoriza os recursos do sistema (CPU, RAM) numa thread de fundo.
    Fornece estatísticas como média, máximo, mínimo e valores atuais.
    Esta classe é essencial para avaliar o desempenho do sistema em tempo real.
    """
    
    def __init__(self, interval: float = 1.0, max_samples: int = 60):
        """
        Inicializa o monitor do sistema.

        Args:
            interval: Intervalo de amostragem em segundos
            max_samples: Número máximo de amostras a manter no histórico
        """
        self.interval = interval  # Intervalo entre amostragens
        self.max_samples = max_samples  # Limite de amostras no histórico
        
        # Deques (filas com limite) para armazenar as amostras
        self.cpu_samples = deque(maxlen=max_samples)  # Histórico de uso da CPU (%)
        self.ram_samples = deque(maxlen=max_samples)  # Histórico de uso da RAM (MB)
        
        self.running = False  # Estado da monitorização (ativa/inativa)
        self.thread: Optional[threading.Thread] = None  # Thread de monitorização
        
    def _monitor_loop(self):
        """
        Thread de fundo que recolhe as métricas do sistema.
        Este método é executado continuamente enquanto a monitorização estiver ativa.
        """
        while self.running:
            try:
                # ============================================================
                # MEDIÇÃO DO USO DA CPU
                # ============================================================
                # O parâmetro interval=0.1 garante uma medição estável
                cpu_percent = psutil.cpu_percent(interval=0.1)
                self.cpu_samples.append(cpu_percent)  # Adiciona ao histórico
                
                # ============================================================
                # MEDIÇÃO DO USO DA RAM
                # ============================================================
                mem = psutil.virtual_memory()  # Obtém informações da memória
                ram_used_mb = mem.used / (1024 * 1024)  # Converte bytes para MB
                self.ram_samples.append(ram_used_mb)  # Adiciona ao histórico
                
                # Aguarda o intervalo definido antes da próxima amostragem
                time.sleep(self.interval)
                
            except Exception as e:
                # Em caso de erro, mostra aviso e continua
                print(f"Erro no monitor do sistema: {e}")
                time.sleep(self.interval)  # Aguarda antes de tentar novamente
    
    def start(self):
        """
        Inicia a monitorização numa thread de fundo.
        A thread é criada como daemon para ser encerrada automaticamente com o programa.
        """
        if self.running:
            return  # Se já estiver a correr, não faz nada
        
        self.running = True  # Marca como ativa
        self.thread = threading.Thread(
            target=self._monitor_loop,  # Função a executar na thread
            daemon=True,  # Thread daemon (termina com o programa principal)
            name="SystemMonitor"  # Nome da thread para identificação
        )
        self.thread.start()  # Inicia a thread
        print("Monitor do sistema iniciado")  # Confirma o início
    
    def stop(self):
        """
        Para a monitorização e aguarda o término da thread.
        """
        self.running = False  # Marca como inativa
        
        # Aguarda que a thread termine (com timeout de 2 segundos)
        if self.thread:
            self.thread.join(timeout=2.0)
        
        print("Monitor do sistema parado")  # Confirma a paragem
    
    def get_stats(self) -> dict:
        """
        Obtém as estatísticas atuais do sistema.

        Returns:
            dict: Dicionário com as estatísticas de CPU e RAM
        """
        # ============================================================
        # CÁLCULO DAS ESTATÍSTICAS DA CPU
        # ============================================================
        cpu_avg = sum(self.cpu_samples) / len(self.cpu_samples) if self.cpu_samples else 0
        cpu_max = max(self.cpu_samples) if self.cpu_samples else 0
        
        # ============================================================
        # CÁLCULO DAS ESTATÍSTICAS DA RAM
        # ============================================================
        ram_avg = sum(self.ram_samples) / len(self.ram_samples) if self.ram_samples else 0
        ram_max = max(self.ram_samples) if self.ram_samples else 0
        
        # ============================================================
        # CONSTRUÇÃO DO DICIONÁRIO DE RESULTADOS
        # ============================================================
        return {
            'cpu': {
                'current': self.cpu_samples[-1] if self.cpu_samples else 0,  # Último valor
                'avg': cpu_avg,   # Média
                'max': cpu_max,   # Máximo
                'min': min(self.cpu_samples) if self.cpu_samples else 0,  # Mínimo
                'samples': len(self.cpu_samples)  # Número de amostras
            },
            'ram': {
                'current': self.ram_samples[-1] if self.ram_samples else 0,  # Último valor
                'avg': ram_avg,   # Média
                'max': ram_max,   # Máximo
                'min': min(self.ram_samples) if self.ram_samples else 0,  # Mínimo
                'samples': len(self.ram_samples)  # Número de amostras
            }
        }
    
    def get_cpu_avg(self) -> float:
        """
        Obtém o uso médio da CPU.

        Returns:
            float: Percentagem média de uso da CPU
        """
        return sum(self.cpu_samples) / len(self.cpu_samples) if self.cpu_samples else 0
    
    def get_cpu_max(self) -> float:
        """
        Obtém o pico de uso da CPU.

        Returns:
            float: Percentagem máxima de uso da CPU
        """
        return max(self.cpu_samples) if self.cpu_samples else 0
    
    def get_ram_avg(self) -> float:
        """
        Obtém o uso médio da RAM.

        Returns:
            float: Uso médio da RAM em MB
        """
        return sum(self.ram_samples) / len(self.ram_samples) if self.ram_samples else 0
    
    def get_ram_max(self) -> float:
        """
        Obtém o pico de uso da RAM.

        Returns:
            float: Uso máximo da RAM em MB
        """
        return max(self.ram_samples) if self.ram_samples else 0


def get_system_memory_total() -> float:
    """
    Obtém a quantidade total de RAM do sistema.

    Returns:
        float: Memória RAM total em MB
    """
    return psutil.virtual_memory().total / (1024 * 1024)  # Converte bytes para MB


def get_system_cpu_count() -> int:
    """
    Obtém o número de núcleos de CPU do sistema.

    Returns:
        int: Número de núcleos de CPU
    """
    return psutil.cpu_count()  # Retorna o número de núcleos lógicos (incluindo hyper-threading)