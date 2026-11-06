from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.services.delivery_service import DeliveryService
from src.services.llm_service import LLMService
from src.services.rag_service import RAGService
from src.services.rate_limiter import AsyncRateLimiter
from src.services.ticket_service import TaskDispatcher, TicketService
from src.workers.tasks import enqueue_ticket_task

DBSessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def get_rate_limiter(request: Request) -> AsyncRateLimiter:
    limiter: AsyncRateLimiter = request.app.state.rate_limiter
    return limiter


def get_rag_service(request: Request) -> RAGService:
    rag: RAGService = request.app.state.rag_service
    return rag


def get_llm_service(request: Request) -> LLMService:
    llm: LLMService = request.app.state.llm_service
    return llm


def get_delivery_service(request: Request) -> DeliveryService:
    delivery: DeliveryService = request.app.state.delivery_service
    return delivery


def get_task_dispatcher() -> TaskDispatcher:
    return enqueue_ticket_task


def get_ticket_service(
    delivery_service: Annotated[DeliveryService, Depends(get_delivery_service)],
    task_dispatcher: Annotated[TaskDispatcher, Depends(get_task_dispatcher)],
) -> TicketService:
    return TicketService(
        delivery_service=delivery_service,
        task_dispatcher=task_dispatcher,
    )
