# src/metrics/reporters.py
import time
import csv
import json
from typing import Optional, Callable
from datetime import datetime
from .latency_tracker import latency_metrics, print_latency_summary

class MetricsReporter:
    """Handles reporting and exporting of metrics"""
    
    def __init__(self, auto_print: bool = True, print_interval: int = 10):
        """
        Initialize the metrics reporter
        
        Args:
            auto_print: Whether to automatically print summaries
            print_interval: Interval in seconds between auto-prints
        """
        self.auto_print = auto_print
        self.print_interval = print_interval
        self.last_print_time = time.time()
        
    def print_summary(self):
        """Print latency summary"""
        print_latency_summary()
    
    def print_averages(self):
        """Print overall averages for all metrics"""
        print("\n📈 OVERALL AVERAGES:")
        for metric, values in latency_metrics.items():
            if values:
                avg = sum(values) / len(values)
                print(f"{metric.upper():15s}: {avg:6.2f}ms ({len(values)} samples)")
    
    def export_to_csv(self, filename: Optional[str] = None) -> str:
        """
        Export metrics to CSV file
        
        Args:
            filename: Output filename (auto-generated if None)
        
        Returns:
            Path to the created CSV file
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"latency_metrics_{timestamp}.csv"
        
        # Find maximum length of all metric lists
        max_length = max([len(values) for values in latency_metrics.values()]) if latency_metrics else 0
        
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header
            headers = ['frame_index'] + list(latency_metrics.keys())
            writer.writerow(headers)
            
            # Write data rows
            for i in range(max_length):
                row = [i + 1]  # frame index (1-based)
                for metric in latency_metrics.keys():
                    if i < len(latency_metrics[metric]):
                        row.append(f"{latency_metrics[metric][i]:.2f}")
                    else:
                        row.append('')
                writer.writerow(row)
        
        print(f"✅ Metrics exported to: {filename}")
        return filename
    
    def export_to_json(self, filename: Optional[str] = None) -> str:
        """
        Export metrics to JSON file
        
        Args:
            filename: Output filename (auto-generated if None)
        
        Returns:
            Path to the created JSON file
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"latency_metrics_{timestamp}.json"
        
        export_data = {
            'export_time': datetime.now().isoformat(),
            'metrics': {}
        }
        
        for metric_name, values in latency_metrics.items():
            if values:
                export_data['metrics'][metric_name] = {
                    'samples': len(values),
                    'values': values,
                    'avg': sum(values) / len(values),
                    'min': min(values),
                    'max': max(values)
                }
        
        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        print(f"✅ Metrics exported to: {filename}")
        return filename
    
    def auto_report_loop(self, callback: Optional[Callable] = None):
        """
        Run auto-reporting loop (meant to be called in a thread)
        
        Args:
            callback: Optional callback function to call on each report
        """
        try:
            while True:
                current_time = time.time()
                if current_time - self.last_print_time >= self.print_interval:
                    self.print_summary()
                    self.last_print_time = current_time
                    
                    if callback:
                        callback()
                
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nAuto-reporting stopped")
    
    def generate_html_report(self, filename: Optional[str] = None) -> str:
        """
        Generate an HTML report from metrics
        
        Args:
            filename: Output filename (auto-generated if None)
        
        Returns:
            Path to the created HTML file
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"latency_report_{timestamp}.html"
        
        # Calculate statistics
        stats = {}
        for metric, values in latency_metrics.items():
            if values:
                stats[metric] = {
                    'avg': sum(values) / len(values),
                    'min': min(values),
                    'max': max(values),
                    'samples': len(values)
                }
        
        # Generate HTML content
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
        
        for metric, stat in stats.items():
            html_content += f"""
            <div class="stat-card">
                <h3>{metric.upper()}</h3>
                <div class="stat-value">Avg: {stat['avg']:.2f}ms</div>
                <div>Min: {stat['min']:.2f}ms | Max: {stat['max']:.2f}ms</div>
                <div>Samples: {stat['samples']}</div>
            </div>
"""
        
        html_content += f"""
        </div>
        <div class="timestamp">
            Report generated by OMRisk Metrics Reporter
        </div>
    </div>
</body>
</html>
"""
        
        with open(filename, 'w') as f:
            f.write(html_content)
        
        print(f"✅ HTML report generated: {filename}")
        return filename