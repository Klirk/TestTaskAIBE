from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.models.ticket import TicketStatus


class HelpdeskReplyPayload(BaseModel):
    ticket_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1)


class TicketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: str
    event_id: str
    customer_email: str
    message: str
    reply_url: str
    status: TicketStatus
    draft_reply: str | None
    matched_articles: list[dict[str, Any]]
    delivery_attempts: int
    last_error: str | None
    created_at: datetime
    updated_at: datetime
