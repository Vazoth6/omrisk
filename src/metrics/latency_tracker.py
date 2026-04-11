# src/metrics/latency_tracker.py
from typing import Dict, List

# Global latency metrics storage
latency_metrics: Dict[str, List[float]] = {
    't1_capture': [],
    't2_processing': [],
    't3_network': [],
    't4_decoding': [],
    't5_rendering': [],
    'total': []
}

def print_latency_summary():
    """Print current latency statistics"""
    print("\n" + "="*60)
    print("📊 LATENCY METRICS SUMMARY")
    print("="*60)
    
    if not latency_metrics['total']:
        print("No latency data collected yet.")
        return
    
    for metric_name, values in latency_metrics.items():
        if values:
            avg = sum(values) / len(values)
            min_val = min(values)
            max_val = max(values)
            print(f"{metric_name.upper():15s} | Avg: {avg:6.2f}ms | Min: {min_val:6.2f}ms | Max: {max_val:6.2f}ms | Samples: {len(values):3d}")
    
    # Print current frame metrics
    print("-"*60)
    print("📈 CURRENT FRAME LATENCY (Last 5 frames):")
    for i in range(min(5, len(latency_metrics['total']))):
        idx = len(latency_metrics['total']) - i - 1
        if idx >= 0:
            print(f"Frame {idx+1:3d}: T1={latency_metrics['t1_capture'][idx]:5.1f}ms, "
                  f"T2={latency_metrics['t2_processing'][idx]:5.1f}ms, "
                  f"T3={latency_metrics['t3_network'][idx]:5.1f}ms, "
                  f"T4={latency_metrics['t4_decoding'][idx]:5.1f}ms, "
                  f"T5={latency_metrics['t5_rendering'][idx]:5.1f}ms, "
                  f"TOTAL={latency_metrics['total'][idx]:5.1f}ms")
    print("="*60)

def reset_metrics():
    """Reset all latency metrics"""
    for key in latency_metrics:
        latency_metrics[key] = []
    print("✅ Latency metrics have been reset")

def get_metric_statistics(metric_name: str) -> dict:
    """Get statistics for a specific metric"""
    if metric_name not in latency_metrics:
        return {'error': f'Metric {metric_name} not found'}
    
    values = latency_metrics[metric_name]
    if not values:
        return {'samples': 0, 'avg': 0, 'min': 0, 'max': 0}
    
    return {
        'samples': len(values),
        'avg': sum(values) / len(values),
        'min': min(values),
        'max': max(values),
        'last_10_avg': sum(values[-10:]) / min(10, len(values))
    }

def get_all_metrics_summary() -> dict:
    """Get summary of all metrics"""
    summary = {}
    for metric_name in latency_metrics:
        summary[metric_name] = get_metric_statistics(metric_name)
    return summary