"""
Tests for messages endpoint.
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


def insert_test_message(message_id: str, from_: str, ts: str, text: str = None):
    """Helper to insert test message."""
    payload = {
        "message_id": message_id,
        "from": from_,
        "to": "+9999999999",
        "ts": ts,
        "text": text
    }
    body = json.dumps(payload).encode()
    signature = generate_signature(body)
    
    client.post(
        "/webhook",
        content=body,
        headers={"X-Signature": signature, "Content-Type": "application/json"}
    )


def test_messages_pagination():
    """Test pagination with limit and offset."""
    # Insert test messages
    for i in range(5):
        insert_test_message(
            f"msg-page-{i}",
            "+1111111111",
            f"2024-01-15T10:00:0{i}Z",
            f"Message {i}"
        )
    
    # Test first page
    response = client.get("/messages?limit=2&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 2
    assert data["limit"] == 2
    assert data["offset"] == 0
    assert data["total"] >= 5
    
    # Test second page
    response = client.get("/messages?limit=2&offset=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 2
    assert data["offset"] == 2


def test_messages_from_filter():
    """Test filtering by sender."""
    insert_test_message("msg-filter-1", "+2222222222", "2024-01-15T11:00:00Z")
    insert_test_message("msg-filter-2", "+3333333333", "2024-01-15T11:00:01Z")
    
    response = client.get("/messages?from=%2B2222222222")
    assert response.status_code == 200
    data = response.json()
    
    # All messages should be from +2222222222
    for msg in data["data"]:
        assert msg["from"] == "+2222222222"


def test_messages_since_filter():
    """Test filtering by timestamp."""
    insert_test_message("msg-since-1", "+4444444444", "2024-01-15T09:00:00Z")
    insert_test_message("msg-since-2", "+4444444444", "2024-01-15T12:00:00Z")
    
    response = client.get("/messages?since=2024-01-15T10:00:00Z")
    assert response.status_code == 200
    data = response.json()
    
    # All messages should be >= since timestamp
    for msg in data["data"]:
        assert msg["ts"] >= "2024-01-15T10:00:00Z"


def test_messages_q_filter():
    """Test text search filter."""
    insert_test_message("msg-search-1", "+5555555555", "2024-01-15T13:00:00Z", "Hello World")
    insert_test_message("msg-search-2", "+5555555555", "2024-01-15T13:00:01Z", "Goodbye")
    
    response = client.get("/messages?q=hello")
    assert response.status_code == 200
    data = response.json()
    
    # Should find message with "Hello" (case-insensitive)
    found = any("hello" in (msg.get("text") or "").lower() for msg in data["data"])
    assert found


def test_messages_ordering():
    """Test ordering by ts ASC, message_id ASC."""
    insert_test_message("msg-order-b", "+6666666666", "2024-01-15T14:00:00Z")
    insert_test_message("msg-order-a", "+6666666666", "2024-01-15T14:00:00Z")
    insert_test_message("msg-order-c", "+6666666666", "2024-01-15T15:00:00Z")
    
    response = client.get("/messages?from=%2B6666666666")
    assert response.status_code == 200
    data = response.json()
    
    # Should be ordered by ts, then message_id
    messages = data["data"]
    for i in range(len(messages) - 1):
        current = messages[i]
        next_msg = messages[i + 1]
        
        # Either ts is less, or ts is equal and message_id is less
        assert (current["ts"] < next_msg["ts"] or 
                (current["ts"] == next_msg["ts"] and 
                 current["message_id"] <= next_msg["message_id"]))


def test_messages_limit_validation():
    """Test limit parameter validation."""
    # Min limit
    response = client.get("/messages?limit=0")
    assert response.status_code == 422
    
    # Max limit
    response = client.get("/messages?limit=101")
    assert response.status_code == 422
    
    # Valid limit
    response = client.get("/messages?limit=50")
    assert response.status_code == 200


def test_messages_offset_validation():
    """Test offset parameter validation."""
    # Negative offset
    response = client.get("/messages?offset=-1")
    assert response.status_code == 422
    
    # Valid offset
    response = client.get("/messages?offset=0")
    assert response.status_code == 200
