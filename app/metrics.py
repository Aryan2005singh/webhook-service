"""
Prometheus-style metrics collection.
"""
from collections import defaultdict
from typing import Dict


class Metrics:
    """In-memory metrics collector."""
    
    def __init__(self):
        self.http_requests_total: Dict[tuple, int] = defaultdict(int)
        self.webhook_requests_total: Dict[tuple, int] = defaultdict(int)
    
    def increment_http_request(self, method: str, path: str, status: int):
        """Increment HTTP request counter."""
        key = (method, path, status)
        self.http_requests_total[key] += 1
    
    def increment_webhook_request(self, result: str):
        """Increment webhook request counter."""
        key = (result,)
        self.webhook_requests_total[key] += 1
    
    def export_prometheus(self) -> str:
        """Export metrics in Prometheus text format."""
        lines = []
        
        # http_requests_total
        lines.append("# HELP http_requests_total Total HTTP requests")
        lines.append("# TYPE http_requests_total counter")
        for (method, path, status), count in sorted(self.http_requests_total.items()):
            lines.append(
                f'http_requests_total{{method="{method}",path="{path}",status="{status}"}} {count}'
            )
        
        # webhook_requests_total
        lines.append("# HELP webhook_requests_total Total webhook requests")
        lines.append("# TYPE webhook_requests_total counter")
        for (result,), count in sorted(self.webhook_requests_total.items()):
            lines.append(f'webhook_requests_total{{result="{result}"}} {count}')
        
        return "\n".join(lines) + "\n"


# Global metrics instance
metrics = Metrics()
