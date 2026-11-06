from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.ticket import Ticket, TicketStatus
from src.schemas.webhook import HelpdeskWebhookPayload


class TicketRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_if_not_exists(self, payload: HelpdeskWebhookPayload) -> int | None:
        stmt = (
            pg_insert(Ticket)
            .values(
                ticket_id=payload.ticket_id,
                event_id=payload.event_id,
                customer_email=str(payload.customer_email),
                message=payload.message,
                reply_url=payload.reply_url,
                status=TicketStatus.NEW,
                matched_articles=[],
                delivery_attempts=0,
            )
            .on_conflict_do_nothing(index_elements=[Ticket.ticket_id])
            .returning(Ticket.id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, ticket_db_id: int) -> Ticket | None:
        stmt = select(Ticket).where(Ticket.id == ticket_db_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_ticket_id(self, ticket_id: str) -> Ticket | None:
        stmt = select(Ticket).where(Ticket.ticket_id == ticket_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self, status_filter: TicketStatus | None = None) -> list[Ticket]:
        stmt = select(Ticket).order_by(Ticket.created_at.desc(), Ticket.id.desc())
        if status_filter is not None:
            stmt = stmt.where(Ticket.status == status_filter)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def claim_ticket_by_id(self, ticket_db_id: int) -> Ticket | None:
        stmt = (
            select(Ticket)
            .where(
                Ticket.id == ticket_db_id,
                Ticket.status == TicketStatus.NEW,
            )
            .with_for_update(skip_locked=True)
        )
        result = await self._session.execute(stmt)
        ticket = result.scalar_one_or_none()
        if ticket is None:
            return None
        ticket.status = TicketStatus.GENERATING_DRAFT
        return ticket

    async def claim_next_new_ticket(self) -> Ticket | None:
        stmt = (
            select(Ticket)
            .where(Ticket.status == TicketStatus.NEW)
            .order_by(Ticket.created_at.asc(), Ticket.id.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        result = await self._session.execute(stmt)
        ticket = result.scalar_one_or_none()
        if ticket is None:
            return None
        ticket.status = TicketStatus.GENERATING_DRAFT
        return ticket

    async def reset_stale_generating_tickets(self) -> int:
        stmt = (
            update(Ticket)
            .where(Ticket.status == TicketStatus.GENERATING_DRAFT)
            .values(status=TicketStatus.NEW)
        )
        result = await self._session.execute(stmt)
        return int(result.rowcount or 0)

    async def save_generated_draft(
        self,
        ticket_db_id: int,
        draft_reply: str,
        matched_articles: list[dict[str, Any]],
    ) -> Ticket | None:
        stmt = select(Ticket).where(Ticket.id == ticket_db_id).with_for_update()
        result = await self._session.execute(stmt)
        ticket = result.scalar_one_or_none()
        if ticket is None:
            return None
        ticket.draft_reply = draft_reply
        ticket.matched_articles = matched_articles
        if ticket.status == TicketStatus.GENERATING_DRAFT:
            ticket.status = TicketStatus.READY_FOR_REVIEW
        return ticket

    async def lock_by_id(self, ticket_db_id: int) -> Ticket | None:
        stmt = select(Ticket).where(Ticket.id == ticket_db_id).with_for_update()
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
