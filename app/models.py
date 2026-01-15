"""
Pydantic models for request/response validation.
"""
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
import re


class WebhookPayload(BaseModel):
    """Incoming webhook message payload."""
    
    message_id: str = Field(..., min_length=1)
    from_: str = Field(..., alias="from")
    to: str
    ts: str
    text: Optional[str] = Field(None, max_length=4096)
    
    @field_validator("from_", "to")
    @classmethod
    def validate_e164(cls, v: str) -> str:
        """Validate E.164-like format: + followed by digits."""
        if not re.match(r'^\+\d+$', v):
            raise ValueError(f"Invalid E.164 format: {v}")
        return v
    
    @field_validator("ts")
    @classmethod
    def validate_iso8601(cls, v: str) -> str:
        """Validate ISO-8601 UTC format with Z suffix."""
        if not re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$', v):
            raise ValueError(f"Invalid ISO-8601 format: {v}")
        return v


class WebhookResponse(BaseModel):
    """Response for successful webhook processing."""
    status: str = "ok"


class ErrorResponse(BaseModel):
    """Standard error response."""
    detail: str


class Message(BaseModel):
    """Message record returned from database."""
    message_id: str
    from_: str = Field(..., alias="from")
    to: str
    ts: str
    text: Optional[str]
    created_at: str
    
    model_config = {"populate_by_name": True}


class MessagesResponse(BaseModel):
    """Paginated messages response."""
    data: List[Message]
    total: int
    limit: int
    offset: int


class SenderStats(BaseModel):
    """Per-sender message count."""
    from_: str = Field(..., alias="from")
    count: int
    
    model_config = {"populate_by_name": True}


class StatsResponse(BaseModel):
    """System statistics response."""
    total_messages: int
    senders_count: int
    messages_per_sender: List[SenderStats]
    first_message_ts: Optional[str]
    last_message_ts: Optional[str]
