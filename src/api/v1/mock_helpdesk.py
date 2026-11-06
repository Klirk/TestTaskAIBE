import asyncio
import random
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, Header, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse

from src.core.config import settings
from src.core.dependencies import (
    DBSessionDep,
    get_ticket_service,
)
from src.repositories.mock_reply_repository import MockReplyRepository
from src.schemas.ticket import HelpdeskReplyPayload
from src.schemas.webhook import HelpdeskWebhookPayload
from src.services.ticket_service import TicketService

router = APIRouter(prefix="/mock/helpdesk", tags=["mock-helpdesk"])

_SAMPLE_TICKETS: list[tuple[str, str]] = [
    ("user@example.com", "Не можу експортувати звіт у PDF"),
    ("finance@client.ua", "Де завантажити рахунок-фактуру (інвойс) за минулий місяць?"),
    ("security@corp.ua", "Втратив телефон із додатком 2FA, як відновити доступ до акаунту?"),
    ("dev@startup.io", "Отримую помилку 401 при запиті до REST API з новим токеном"),
    ("analyst@retail.ua", "Не вдається імпортувати таблицю CSV, вибиває помилку кодування UTF-8"),
    ("pm@agency.ua", "Як запросити колегу в команду з правами лише на перегляд дашбордів?"),
    ("ops@logistics.ua", "Дашборд продажів за рік завантажується дуже повільно"),
    ("marketing@brand.ua", "Як підключити сповіщення про аномалії у Telegram-бот?"),
]


@router.post(
    "/tickets/{ticket_id}/replies",
    status_code=status.HTTP_201_CREATED,
)
async def receive_client_reply(
    ticket_id: str,
    payload: HelpdeskReplyPayload,
    session: DBSessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    x_simulate_failure: Annotated[str | None, Header(alias="X-Simulate-Failure")] = None,
) -> dict[str, Any]:
    if payload.ticket_id != ticket_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ticket_id mismatch between URL path and body",
        )

    repo = MockReplyRepository(session)
    existing = await repo.get_by_ticket_id(ticket_id)
    if existing is not None:
        return {
            "status": "created",
            "ticket_id": existing.ticket_id,
            "message": existing.message,
            "deduplicated": True,
        }

    if x_simulate_failure == "500":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Simulated Helpdesk 503 error",
        )
    if x_simulate_failure == "timeout":
        await asyncio.sleep(10.0)

    if (
        x_simulate_failure is None
        and settings.mock_helpdesk_failure_rate > 0
        and random.random() < settings.mock_helpdesk_failure_rate
    ):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Simulated intermittent Helpdesk 502 error",
        )

    reply, created = await repo.record_reply_idempotent(
        ticket_id=ticket_id,
        message=payload.message,
        idempotency_key=idempotency_key,
    )
    await session.commit()

    return {
        "status": "created",
        "ticket_id": reply.ticket_id,
        "message": reply.message,
        "deduplicated": not created,
    }


@router.get("/replies")
async def list_delivered_replies(session: DBSessionDep) -> list[dict[str, Any]]:
    repo = MockReplyRepository(session)
    replies = await repo.list_all()
    return [
        {
            "id": r.id,
            "ticket_id": r.ticket_id,
            "idempotency_key": r.idempotency_key,
            "message": r.message,
            "created_at": r.created_at.isoformat(),
        }
        for r in replies
    ]


@router.post("/simulate", response_model=None)
async def simulate_incoming_tickets(
    session: DBSessionDep,
    ticket_service: Annotated[TicketService, Depends(get_ticket_service)],
    count: Annotated[int, Form()] = 1,
    custom_message: Annotated[str, Form()] = "",
    custom_email: Annotated[str, Form()] = "",
) -> HTMLResponse | RedirectResponse:
    safe_count = max(1, min(count, 50))
    for _ in range(safe_count):
        short_id = uuid.uuid4().hex[:6].upper()
        evt_id = f"evt_{uuid.uuid4().hex[:8]}"
        t_id = f"T-{short_id}"
        if custom_message.strip():
            email = custom_email.strip() or "user@example.com"
            msg = custom_message.strip()
        else:
            email, msg = random.choice(_SAMPLE_TICKETS)

        webhook_payload = HelpdeskWebhookPayload(
            event_id=evt_id,
            ticket_id=t_id,
            customer_email=email,
            message=msg,
            reply_url=f"https://helpdesk.example.com/tickets/{t_id}/replies",
        )
        await ticket_service.ingest_webhook(
            session=session,
            payload=webhook_payload,
        )

    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
