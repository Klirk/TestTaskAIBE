from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class TicketStatus(StrEnum):
    NEW = "NEW"
    GENERATING_DRAFT = "GENERATING_DRAFT"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    SENDING = "SENDING"
    SENT = "SENT"
    REJECTED = "REJECTED"
    DELIVERY_FAILED = "DELIVERY_FAILED"


class Ticket(Base, TimestampMixin):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    event_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    customer_email: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    reply_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[TicketStatus] = mapped_column(
        Enum(TicketStatus, name="ticket_status", native_enum=False),
        default=TicketStatus.NEW,
        index=True,
        nullable=False,
    )
    draft_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    matched_articles: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    delivery_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
