from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import (
    DeliveryFailedError,
    InvalidTicketStateError,
    TicketNotFoundError,
)
from src.models.ticket import Ticket, TicketStatus
from src.repositories.ticket_repository import TicketRepository
from src.repositories.webhook_repository import WebhookRepository
from src.schemas.webhook import HelpdeskWebhookPayload, WebhookAckResponse
from src.services.delivery_service import DeliveryService

TaskDispatcher = Callable[[int], Awaitable[None]]


class TicketService:
    def __init__(
        self,
        delivery_service: DeliveryService | None = None,
        task_dispatcher: TaskDispatcher | None = None,
    ) -> None:
        self._delivery_service = delivery_service
        self._task_dispatcher = task_dispatcher

    async def ingest_webhook(
        self,
        session: AsyncSession,
        payload: HelpdeskWebhookPayload,
    ) -> WebhookAckResponse:
        webhook_repo = WebhookRepository(session)
        ticket_repo = TicketRepository(session)

        is_new_event = await webhook_repo.record_event_if_new(
            event_id=payload.event_id,
            ticket_id=payload.ticket_id,
        )
        created_ticket_id: int | None = None
        if is_new_event:
            created_ticket_id = await ticket_repo.create_if_not_exists(payload)

        await session.commit()

        if created_ticket_id is not None and self._task_dispatcher is not None:
            await self._task_dispatcher(created_ticket_id)

        duplicate = not (is_new_event and created_ticket_id is not None)
        return WebhookAckResponse(
            status="accepted",
            event_id=payload.event_id,
            ticket_id=payload.ticket_id,
            duplicate=duplicate,
        )

    async def approve_ticket(
        self,
        session: AsyncSession,
        ticket_db_id: int,
        edited_draft: str | None = None,
    ) -> Ticket:
        if self._delivery_service is None:
            raise RuntimeError("DeliveryService is required for ticket approval")

        repo = TicketRepository(session)
        ticket = await repo.lock_by_id(ticket_db_id)
        if ticket is None:
            raise TicketNotFoundError(f"Ticket {ticket_db_id} not found")

        if ticket.status == TicketStatus.SENT:
            return ticket

        if ticket.status == TicketStatus.SENDING:
            raise InvalidTicketStateError("Ticket reply is already being sent")

        if ticket.status not in (
            TicketStatus.READY_FOR_REVIEW,
            TicketStatus.DELIVERY_FAILED,
        ):
            raise InvalidTicketStateError(
                f"Cannot approve ticket in status {ticket.status}"
            )

        if edited_draft is not None and edited_draft.strip():
            ticket.draft_reply = edited_draft.strip()

        if not ticket.draft_reply:
            raise InvalidTicketStateError("Ticket has no draft reply to send")

        reply_url = ticket.reply_url
        ticket_ext_id = ticket.ticket_id
        message_to_send = ticket.draft_reply

        ticket.status = TicketStatus.SENDING
        ticket.last_error = None
        await session.commit()

        try:
            attempts, _ = await self._delivery_service.send_reply(
                reply_url=reply_url,
                ticket_id=ticket_ext_id,
                message=message_to_send,
            )
            locked_ticket = await repo.lock_by_id(ticket_db_id)
            assert locked_ticket is not None
            locked_ticket.delivery_attempts += attempts
            locked_ticket.status = TicketStatus.SENT
            locked_ticket.last_error = None
            await session.commit()
            await session.refresh(locked_ticket)
            return locked_ticket
        except DeliveryFailedError as exc:
            locked_ticket = await repo.lock_by_id(ticket_db_id)
            assert locked_ticket is not None
            locked_ticket.delivery_attempts += 1
            locked_ticket.status = TicketStatus.DELIVERY_FAILED
            locked_ticket.last_error = str(exc)
            await session.commit()
            await session.refresh(locked_ticket)
            return locked_ticket

    async def reject_ticket(
        self,
        session: AsyncSession,
        ticket_db_id: int,
    ) -> Ticket:
        repo = TicketRepository(session)
        ticket = await repo.lock_by_id(ticket_db_id)
        if ticket is None:
            raise TicketNotFoundError(f"Ticket {ticket_db_id} not found")

        if ticket.status in (TicketStatus.SENT, TicketStatus.SENDING):
            raise InvalidTicketStateError(
                f"Cannot reject ticket in status {ticket.status}"
            )

        ticket.status = TicketStatus.REJECTED
        await session.commit()
        await session.refresh(ticket)
        return ticket
