"""
Structured JSON logging utilities.
"""
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Optional
from contextvars import ContextVar

# Context variable for request ID
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def generate_request_id() -> str:
    """Generate unique request ID."""
    return str(uuid.uuid4())


def log_json(
    level: str,
    method: str,
    path: str,
    status: int,
    latency_ms: float,
    message_id: Optional[str] = None,
    dup: Optional[bool] = None,
    result: Optional[str] = None,
    error: Optional[str] = None
):
    """Emit structured JSON log."""
    log_entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "request_id": request_id_var.get(),
        "method": method,
        "path": path,
        "status": status,
        "latency_ms": round(latency_ms, 2)
    }
    
    # Add webhook-specific fields
    if message_id is not None:
        log_entry["message_id"] = message_id
    if dup is not None:
        log_entry["dup"] = dup
    if result is not None:
        log_entry["result"] = result
    if error is not None:
        log_entry["error"] = error
    
    print(json.dumps(log_entry), flush=True)


class RequestTimer:
    """Context manager for timing requests."""
    
    def __init__(self):
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, *args):
        pass
    
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        if self.start_time is None:
            return 0.0
        return (time.time() - self.start_time) * 1000
