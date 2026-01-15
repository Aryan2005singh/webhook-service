"""
Tests for stats endpoint.
"""
import hmac
import hashlib
import json
from fastapi.testclient import TestClient
from app.main import app
from app.config import get_config


client = TestClient(app)
config = get_config()


def generate_signature(body: bytes) -> str:
    """Generate HMAC signature for test."""
    secret = config.webhook_secret.encode()
    return hmac.new(secret, body, hashlib.sha256).hexdigest()


def insert_test_message(message_id: str, from_: str, ts: str):
    """Helper to insert test message."""
    payload = {
        "message_id": message_id,
        "from": from_,
        "to": "+9999999999",
        "ts": ts
    }
    body = json.dumps(payload).encode()
    signature = generate_signature(body)
    
    client.post(
        "/webhook",
        content=body,
        headers={"X-Signature": signature, "Content-Type": "application/json"}
    )


def test_stats_empty():
    """Test stats with no messages (fresh DB)."""
    response = client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    
    assert "total_messages" in data
    assert "senders_count" in data
    assert "messages_per_sender" in data
    assert "first_message_ts" in data
    assert "last_message_ts" in data


def test_stats_with_messages():
    """Test stats with multiple messages."""
    # Insert messages from different senders
    insert_test_message("msg-stats-1", "+1111111111", "2024-01-15T08:00:00Z")
    insert_test_message("msg-stats-2", "+1111111111", "2024-01-15T08:00:01Z")
    insert_test_message("msg-stats-3", "+2222222222", "2024-01-15T08:00:02Z")
    
    response = client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    
    assert data["total_messages"] >= 3
    assert data["senders_count"] >= 2
    assert len(data["messages_per_sender"]) >= 1


def test_stats_top_senders():
    """Test top senders sorting."""
    # Insert messages with varying counts
    for i in range(5):
        insert_test_message(f"msg-top-1-{i}", "+7777777777", f"2024-01-15T16:00:0{i}Z")
    
    for i in range(3):
        insert_test_message(f"msg-top-2-{i}", "+8888888888", f"2024-01-15T16:01:0{i}Z")
    
    response = client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    
    # Should have top senders sorted by count DESC
    top_senders = data["messages_per_sender"]
    if len(top_senders) > 1:
        for i in range(len(top_senders) - 1):
            assert top_senders[i]["count"] >= top_senders[i + 1]["count"]


def test_stats_timestamps():
    """Test first and last message timestamps."""
    insert_test_message("msg-ts-1", "+9999999999", "2024-01-15T07:00:00Z")
    insert_test_message("msg-ts-2", "+9999999999", "2024-01-15T20:00:00Z")
    
    response = client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    
    # Should have valid timestamps
    if data["first_message_ts"]:
        assert data["first_message_ts"] <= data["last_message_ts"]
