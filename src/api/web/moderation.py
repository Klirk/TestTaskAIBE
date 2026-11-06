from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.core.dependencies import DBSessionDep, get_ticket_service
from src.core.exceptions import InvalidTicketStateError, TicketNotFoundError
from src.models.ticket import TicketStatus
from src.repositories.mock_reply_repository import MockReplyRepository
from src.repositories.ticket_repository import TicketRepository
from src.services.ticket_service import TicketService

router = APIRouter(tags=["moderation"])

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


@router.get("/", response_class=HTMLResponse)
async def moderation_dashboard(
    request: Request,
    session: DBSessionDep,
    status_filter: str | None = None,
) -> HTMLResponse:
    ticket_repo = TicketRepository(session)
    reply_repo = MockReplyRepository(session)

    parsed_status: TicketStatus | None = None
    if status_filter and status_filter in TicketStatus.__members__:
        parsed_status = TicketStatus(status_filter)

    tickets = await ticket_repo.list_all(status_filter=parsed_status)
    all_tickets = tickets if parsed_status is None else await ticket_repo.list_all()
    delivered_replies = await reply_repo.list_all()

    counts = {
        "total": len(all_tickets),
        "pending": sum(
            1
            for t in all_tickets
            if t.status in (TicketStatus.NEW, TicketStatus.GENERATING_DRAFT)
        ),
        "ready": sum(1 for t in all_tickets if t.status == TicketStatus.READY_FOR_REVIEW),
        "sent": sum(1 for t in all_tickets if t.status == TicketStatus.SENT),
        "rejected": sum(1 for t in all_tickets if t.status == TicketStatus.REJECTED),
    }

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "tickets": tickets,
            "counts": counts,
            "status_filter": status_filter or "",
            "delivered_replies": delivered_replies[:10],
        },
    )


@router.post("/tickets/{ticket_db_id}/approve", response_model=None)
async def approve_ticket_route(
    request: Request,
    ticket_db_id: int,
    session: DBSessionDep,
    ticket_service: Annotated[TicketService, Depends(get_ticket_service)],
    draft_reply: Annotated[str | None, Form()] = None,
) -> HTMLResponse | RedirectResponse:
    try:
        ticket = await ticket_service.approve_ticket(
            session=session,
            ticket_db_id=ticket_db_id,
            edited_draft=draft_reply,
        )
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidTicketStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if request.headers.get("HX-Request") == "true":
        return templates.TemplateResponse(
            request=request,
            name="partials/ticket_row.html",
            context={"ticket": ticket},
        )
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/tickets/{ticket_db_id}/reject", response_model=None)
async def reject_ticket_route(
    request: Request,
    ticket_db_id: int,
    session: DBSessionDep,
    ticket_service: Annotated[TicketService, Depends(get_ticket_service)],
) -> HTMLResponse | RedirectResponse:
    try:
        ticket = await ticket_service.reject_ticket(
            session=session,
            ticket_db_id=ticket_db_id,
        )
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidTicketStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if request.headers.get("HX-Request") == "true":
        return templates.TemplateResponse(
            request=request,
            name="partials/ticket_row.html",
            context={"ticket": ticket},
        )
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
