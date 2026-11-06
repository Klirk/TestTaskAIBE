from typing import Annotated

from fastapi import APIRouter, Depends, status

from src.core.dependencies import (
    DBSessionDep,
    get_ticket_service,
)
from src.schemas.webhook import HelpdeskWebhookPayload, WebhookAckResponse
from src.services.ticket_service import TicketService

router = APIRouter(tags=["webhooks"])


@router.post(
    "/webhooks/helpdesk",
    response_model=WebhookAckResponse,
    status_code=status.HTTP_200_OK,
)
async def receive_helpdesk_webhook(
    payload: HelpdeskWebhookPayload,
    session: DBSessionDep,
    ticket_service: Annotated[TicketService, Depends(get_ticket_service)],
) -> WebhookAckResponse:
    return await ticket_service.ingest_webhook(
        session=session,
        payload=payload,
    )
