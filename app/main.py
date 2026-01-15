"""
FastAPI application entry point.
"""
import hmac
import hashlib
from typing import Optional
from fastapi import FastAPI, Request, Response, Query, status
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import ValidationError

from app.config import get_config
from app.models import (
    WebhookPayload,
    WebhookResponse,
    ErrorResponse,
    MessagesResponse,
    StatsResponse,
    Message,
    SenderStats
)
from app.storage import Database
from app.logging_utils import (
    log_json,
    RequestTimer,
    request_id_var,
    generate_request_id
)
from app.metrics import metrics


# Initialize app
app = FastAPI(title="Webhook Service")
config = get_config()
db = Database(config.database_url)


# Middleware for request ID and logging
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Add request ID and structured logging to all requests."""
    # Generate and store request ID
    req_id = generate_request_id()
    request_id_var.set(req_id)
    
    # Time the request
    timer = RequestTimer()
    timer.__enter__()
    
    # Process request
    response = await call_next(request)
    
    # Log after response (for most endpoints)
    # Webhook endpoint handles its own logging for detailed info
    if request.url.path != "/webhook":
        log_json(
            level="INFO",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            latency_ms=timer.elapsed_ms()
        )
    
    # Track metrics
    metrics.increment_http_request(
        method=request.method,
        path=request.url.path,
        status=response.status_code
    )
    
    return response


def verify_signature(body: bytes, signature: Optional[str]) -> bool:
    """Verify HMAC-SHA256 signature."""
    if not signature:
        return False
    
    secret = config.webhook_secret.encode()
    expected = hmac.new(secret, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@app.post("/webhook", response_model=WebhookResponse, status_code=200)
async def webhook(request: Request):
    """
    Process incoming webhook with HMAC verification and idempotency.
    """
    timer = RequestTimer()
    timer.__enter__()
    
    # Read raw body
    body = await request.body()
    signature = request.headers.get("X-Signature")
    
    # Verify signature FIRST
    if not verify_signature(body, signature):
        log_json(
            level="ERROR",
            method="POST",
            path="/webhook",
            status=401,
            latency_ms=timer.elapsed_ms(),
            result="invalid_signature",
            error="invalid signature"
        )
        metrics.increment_webhook_request("invalid_signature")
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "invalid signature"}
        )
    
    # Parse and validate payload
    try:
        payload = WebhookPayload.model_validate_json(body)
    except ValidationError as e:
        log_json(
            level="ERROR",
            method="POST",
            path="/webhook",
            status=422,
            latency_ms=timer.elapsed_ms(),
            result="validation_error",
            error=str(e)
        )
        metrics.increment_webhook_request("validation_error")
        raise
    
    # Insert into database with idempotency
    success, is_duplicate = db.insert_message(
        message_id=payload.message_id,
        from_msisdn=payload.from_,
        to_msisdn=payload.to,
        ts=payload.ts,
        text=payload.text
    )
    
    if not success:
        log_json(
            level="ERROR",
            method="POST",
            path="/webhook",
            status=500,
            latency_ms=timer.elapsed_ms(),
            message_id=payload.message_id,
            dup=False,
            result="db_error"
        )
        metrics.increment_webhook_request("db_error")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "database error"}
        )
    
    # Log success
    result = "duplicate" if is_duplicate else "success"
    log_json(
        level="INFO",
        method="POST",
        path="/webhook",
        status=200,
        latency_ms=timer.elapsed_ms(),
        message_id=payload.message_id,
        dup=is_duplicate,
        result=result
    )
    metrics.increment_webhook_request(result)
    
    return WebhookResponse()


@app.get("/messages", response_model=MessagesResponse)
async def get_messages(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    from_: Optional[str] = Query(default=None, alias="from"),
    since: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None)
):
    """
    Retrieve messages with pagination and filters.
    """
    messages, total = db.get_messages(
        limit=limit,
        offset=offset,
        from_filter=from_,
        since_filter=since,
        q_filter=q
    )
    
    # Convert to Message models
    message_models = [Message(**msg) for msg in messages]
    
    return MessagesResponse(
        data=message_models,
        total=total,
        limit=limit,
        offset=offset
    )


@app.get("/stats", response_model=StatsResponse)
async def get_stats():
    """
    Get system statistics.
    """
    stats = db.get_stats()
    
    # Convert to response model
    return StatsResponse(
        total_messages=stats["total_messages"],
        senders_count=stats["senders_count"],
        messages_per_sender=[
            SenderStats(**sender) for sender in stats["messages_per_sender"]
        ],
        first_message_ts=stats["first_message_ts"],
        last_message_ts=stats["last_message_ts"]
    )


@app.get("/health/live")
async def health_live():
    """Liveness probe - always returns 200 when app is running."""
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready():
    """
    Readiness probe - returns 200 only if DB is reachable and config is valid.
    """
    if not config.is_ready():
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not ready", "reason": "missing webhook secret"}
        )
    
    if not db.is_healthy():
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not ready", "reason": "database unavailable"}
        )
    
    return {"status": "ready"}


@app.get("/metrics", response_class=PlainTextResponse)
async def get_metrics():
    """
    Export Prometheus-style metrics.
    """
    return metrics.export_prometheus()
