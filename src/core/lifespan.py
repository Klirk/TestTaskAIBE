from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from src.core.config import settings
from src.core.database import async_session_maker, engine
from src.models.base import Base
from src.models.ticket import TicketStatus
from src.repositories.ticket_repository import TicketRepository
from src.services.delivery_service import DeliveryService
from src.services.llm_service import LLMService
from src.services.rag_service import RAGService
from src.services.rate_limiter import AsyncRateLimiter
from src.workers.tasks import enqueue_ticket_task


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    rag_service = RAGService()
    async with async_session_maker() as session:
        await rag_service.seed_knowledge_base(session)
        ticket_repo = TicketRepository(session)
        await ticket_repo.reset_stale_generating_tickets()
        await session.commit()
        pending_tickets = await ticket_repo.list_all(status_filter=TicketStatus.NEW)
        for pending in pending_tickets:
            await enqueue_ticket_task(pending.id)

    limits = httpx.Limits(max_connections=100, max_keepalive_connections=30)
    http_client = httpx.AsyncClient(limits=limits)

    rate_limiter = AsyncRateLimiter(
        max_requests=settings.llm_rpm_limit,
        period_seconds=60.0,
    )
    llm_service = LLMService(
        http_client=http_client,
        rate_limiter=rate_limiter,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        min_latency_seconds=settings.llm_min_latency_seconds,
        max_latency_seconds=settings.llm_max_latency_seconds,
    )
    delivery_service = DeliveryService(
        http_client=http_client,
        max_retries=settings.delivery_max_retries,
        timeout_seconds=settings.delivery_timeout_seconds,
    )

    app.state.http_client = http_client
    app.state.rate_limiter = rate_limiter
    app.state.rag_service = rag_service
    app.state.llm_service = llm_service
    app.state.delivery_service = delivery_service

    try:
        yield
    finally:
        await http_client.aclose()
        await engine.dispose()
