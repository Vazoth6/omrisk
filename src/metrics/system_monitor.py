# src/metrics/system_monitor.py
import psutil
import time
import threading
from collections import deque
from typing import Optional

class SystemMonitor:
    """
    Monitor system resources (CPU, RAM) in a background thread.
    Provides statistics like average, max, min and current values.
    """
    
    def __init__(self, interval: float = 1.0, max_samples: int = 60):
        """
        Initialize system monitor.
        
        Args:
            interval: Sampling interval in seconds
            max_samples: Maximum number of samples to keep in history
        """
        self.interval = interval
        self.max_samples = max_samples
        self.cpu_samples = deque(maxlen=max_samples)
        self.ram_samples = deque(maxlen=max_samples)
        self.running = False
        self.thread: Optional[threading.Thread] = None
        
    def _monitor_loop(self):
        """Background thread that samples system metrics"""
        while self.running:
            try:
                # CPU usage (percent)
                cpu_percent = psutil.cpu_percent(interval=0.1)
                self.cpu_samples.append(cpu_percent)
                
                # RAM usage (MB)
                mem = psutil.virtual_memory()
                ram_used_mb = mem.used / (1024 * 1024)
                self.ram_samples.append(ram_used_mb)
                
                time.sleep(self.interval)
            except Exception as e:
                print(f"⚠️ System monitor error: {e}")
                time.sleep(self.interval)
    
    def start(self):
        """Start monitoring in a background thread"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="SystemMonitor"
        )
        self.thread.start()
        print("✅ System monitor started")
    
    def stop(self):
        """Stop monitoring"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        print("✅ System monitor stopped")
    
    def get_stats(self) -> dict:
        """Get current statistics"""
        cpu_avg = sum(self.cpu_samples) / len(self.cpu_samples) if self.cpu_samples else 0
        cpu_max = max(self.cpu_samples) if self.cpu_samples else 0
        
        ram_avg = sum(self.ram_samples) / len(self.ram_samples) if self.ram_samples else 0
        ram_max = max(self.ram_samples) if self.ram_samples else 0
        
        return {
            'cpu': {
                'current': self.cpu_samples[-1] if self.cpu_samples else 0,
                'avg': cpu_avg,
                'max': cpu_max,
                'min': min(self.cpu_samples) if self.cpu_samples else 0,
                'samples': len(self.cpu_samples)
            },
            'ram': {
                'current': self.ram_samples[-1] if self.ram_samples else 0,
                'avg': ram_avg,
                'max': ram_max,
                'min': min(self.ram_samples) if self.ram_samples else 0,
                'samples': len(self.ram_samples)
            }
        }
    
    def get_cpu_avg(self) -> float:
        """Get average CPU usage"""
        return sum(self.cpu_samples) / len(self.cpu_samples) if self.cpu_samples else 0
    
    def get_cpu_max(self) -> float:
        """Get peak CPU usage"""
        return max(self.cpu_samples) if self.cpu_samples else 0
    
    def get_ram_avg(self) -> float:
        """Get average RAM usage in MB"""
        return sum(self.ram_samples) / len(self.ram_samples) if self.ram_samples else 0
    
    def get_ram_max(self) -> float:
        """Get peak RAM usage in MB"""
        return max(self.ram_samples) if self.ram_samples else 0


def get_system_memory_total() -> float:
    """Get total system RAM in MB"""
    return psutil.virtual_memory().total / (1024 * 1024)


def get_system_cpu_count() -> int:
    """Get number of CPU cores"""
    return psutil.cpu_count()