# src/metrics/metrics_collector.py
import time
import json
from typing import Dict, List, Optional
from datetime import datetime
from .latency_tracker import latency_metrics, get_all_metrics_summary

class MetricsCollector:
    """Collector for managing and aggregating latency metrics"""
    
    def __init__(self, max_history: int = 1000):
        """
        Initialize the metrics collector
        
        Args:
            max_history: Maximum number of samples to keep per metric
        """
        self.max_history = max_history
        self.start_time = time.time()
        self.frame_count = 0
        self._last_report_time = time.time()
        
    def add_metric(self, metric_name: str, value: float):
        """Add a single metric value"""
        if metric_name not in latency_metrics:
            # Create new metric if it doesn't exist
            latency_metrics[metric_name] = []
        
        latency_metrics[metric_name].append(value)
        
        # Trim if exceeds max history
        if len(latency_metrics[metric_name]) > self.max_history:
            latency_metrics[metric_name] = latency_metrics[metric_name][-self.max_history:]
    
    def add_frame_metrics(self, frame_metrics: Dict[str, float]):
        """Add all metrics for a single frame"""
        for metric_name, value in frame_metrics.items():
            if metric_name in latency_metrics:
                latency_metrics[metric_name].append(value)
                # Trim if needed
                if len(latency_metrics[metric_name]) > self.max_history:
                    latency_metrics[metric_name] = latency_metrics[metric_name][-self.max_history:]
        
        self.frame_count += 1
    
    def get_current_fps(self) -> float:
        """Calculate current FPS based on frame count"""
        elapsed = time.time() - self.start_time
        if elapsed > 0:
            return self.frame_count / elapsed
        return 0.0
    
    def get_average_latency(self, metric_name: str, last_n: Optional[int] = None) -> float:
        """Get average latency for a specific metric"""
        if metric_name not in latency_metrics:
            return 0.0
        
        values = latency_metrics[metric_name]
        if not values:
            return 0.0
        
        if last_n:
            values = values[-last_n:]
        
        return sum(values) / len(values)
    
    def get_total_average_latency(self, last_n: Optional[int] = None) -> float:
        """Get average total latency"""
        return self.get_average_latency('total', last_n)
    
    def get_metrics_summary(self) -> dict:
        """Get comprehensive metrics summary"""
        return {
            'timestamp': time.time(),
            'uptime_seconds': time.time() - self.start_time,
            'total_frames': self.frame_count,
            'current_fps': self.get_current_fps(),
            'metrics': get_all_metrics_summary()
        }
    
    def export_to_json(self, filepath: Optional[str] = None) -> str:
        """Export metrics to JSON format"""
        data = {
            'export_time': datetime.now().isoformat(),
            'collector_info': {
                'start_time': datetime.fromtimestamp(self.start_time).isoformat(),
                'total_frames': self.frame_count,
                'max_history': self.max_history
            },
            'metrics': {}
        }
        
        for metric_name, values in latency_metrics.items():
            if values:
                data['metrics'][metric_name] = {
                    'samples': len(values),
                    'values': values,
                    'statistics': {
                        'avg': sum(values) / len(values),
                        'min': min(values),
                        'max': max(values)
                    }
                }
        
        if filepath:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
        
        return json.dumps(data, indent=2)
    
    def reset(self):
        """Reset all collected metrics"""
        for key in latency_metrics:
            latency_metrics[key] = []
        self.start_time = time.time()
        self.frame_count = 0
        print("✅ MetricsCollector has been reset")
    
    def should_report(self, interval_seconds: int = 5) -> bool:
        """Check if it's time to report metrics"""
        current_time = time.time()
        if current_time - self._last_report_time >= interval_seconds:
            self._last_report_time = current_time
            return True
        return False