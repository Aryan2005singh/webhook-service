"""
Tests for webhook endpoint.
"""
import hmac
import hashlib
import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import get_config


client = TestClient(app)
config = get_config()


def generate_signature(body: bytes) -> str:
    """Generate HMAC signature for test."""
    secret = config.webhook_secret.encode()
    return hmac.new(secret, body, hashlib.sha256).hexdigest()


def test_webhook_success():
    """Test successful webhook processing."""
    payload = {
        "message_id": "msg-001",
        "from": "+1234567890",
        "to": "+9876543210",
        "ts": "2024-01-15T10:30:00.000Z",
        "text": "Hello World"
    }
    body = json.dumps(payload).encode()
    signature = generate_signature(body)
    
    response = client.post(
        "/webhook",
        content=body,
        headers={"X-Signature": signature, "Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_webhook_duplicate():
    """Test idempotency - duplicate message_id."""
    payload = {
        "message_id": "msg-duplicate",
        "from": "+1234567890",
        "to": "+9876543210",
        "ts": "2024-01-15T10:30:00Z",
        "text": "Duplicate test"
    }
    body = json.dumps(payload).encode()
    signature = generate_signature(body)
    
    # First request
    response1 = client.post(
        "/webhook",
        content=body,
        headers={"X-Signature": signature, "Content-Type": "application/json"}
    )
    assert response1.status_code == 200
    
    # Second request with same message_id
    response2 = client.post(
        "/webhook",
        content=body,
        headers={"X-Signature": signature, "Content-Type": "application/json"}
    )
    assert response2.status_code == 200


def test_webhook_invalid_signature():
    """Test webhook with invalid signature."""
    payload = {
        "message_id": "msg-002",
        "from": "+1234567890",
        "to": "+9876543210",
        "ts": "2024-01-15T10:30:00Z"
    }
    body = json.dumps(payload).encode()
    
    response = client.post(
        "/webhook",
        content=body,
        headers={"X-Signature": "invalid", "Content-Type": "application/json"}
    )
    
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid signature"}


def test_webhook_missing_signature():
    """Test webhook with missing signature."""
    payload = {
        "message_id": "msg-003",
        "from": "+1234567890",
        "to": "+9876543210",
        "ts": "2024-01-15T10:30:00Z"
    }
    body = json.dumps(payload).encode()
    
    response = client.post(
        "/webhook",
        content=body,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid signature"}


def test_webhook_invalid_e164():
    """Test webhook with invalid E.164 format."""
    payload = {
        "message_id": "msg-004",
        "from": "1234567890",  # Missing +
        "to": "+9876543210",
        "ts": "2024-01-15T10:30:00Z"
    }
    body = json.dumps(payload).encode()
    signature = generate_signature(body)
    
    response = client.post(
        "/webhook",
        content=body,
        headers={"X-Signature": signature, "Content-Type": "application/json"}
    )
    
    assert response.status_code == 422


def test_webhook_invalid_timestamp():
    """Test webhook with invalid timestamp format."""
    payload = {
        "message_id": "msg-005",
        "from": "+1234567890",
        "to": "+9876543210",
        "ts": "2024-01-15 10:30:00"  # Wrong format
    }
    body = json.dumps(payload).encode()
    signature = generate_signature(body)
    
    response = client.post(
        "/webhook",
        content=body,
        headers={"X-Signature": signature, "Content-Type": "application/json"}
    )
    
    assert response.status_code == 422


def test_webhook_text_too_long():
    """Test webhook with text exceeding 4096 characters."""
    payload = {
        "message_id": "msg-006",
        "from": "+1234567890",
        "to": "+9876543210",
        "ts": "2024-01-15T10:30:00Z",
        "text": "a" * 4097
    }
    body = json.dumps(payload).encode()
    signature = generate_signature(body)
    
    response = client.post(
        "/webhook",
        content=body,
        headers={"X-Signature": signature, "Content-Type": "application/json"}
    )
    
    assert response.status_code == 422
