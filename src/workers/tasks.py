import asyncio
import logging
import threading

import httpx

from src.core.config import settings
from src.core.database import async_session_maker
from src.services.llm_service import LLMService
from src.services.rag_service import RAGService
from src.services.rate_limiter import AsyncRateLimiter
from src.workers.celery_app import celery_app
from src.workers.ticket_processor import TicketProcessorPool

logger = logging.getLogger(__name__)


class _AsyncWorkerRuntime:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._processor: TicketProcessorPool | None = None

    def _ensure_started(self) -> tuple[asyncio.AbstractEventLoop, TicketProcessorPool]:
        with self._lock:
            if self._loop is not None and self._processor is not None:
                return self._loop, self._processor

            loop = asyncio.new_event_loop()
            thread = threading.Thread(target=loop.run_forever, daemon=True)
            thread.start()

            future = asyncio.run_coroutine_threadsafe(self._init_services(), loop)
            processor = future.result(timeout=30.0)

            self._loop = loop
            self._thread = thread
            self._processor = processor
            return loop, processor

    @staticmethod
    async def _init_services() -> TicketProcessorPool:
        rag_service = RAGService()
        async with async_session_maker() as session:
            await rag_service.seed_knowledge_base(session)

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
        return TicketProcessorPool(
            session_maker=async_session_maker,
            rag_service=rag_service,
            llm_service=llm_service,
            concurrency=settings.worker_concurrency,
            poll_interval_seconds=settings.worker_poll_interval_seconds,
        )

    def run_ticket(self, ticket_db_id: int) -> bool:
        loop, processor = self._ensure_started()
        future = asyncio.run_coroutine_threadsafe(
            processor.process_ticket_by_id(ticket_db_id),
            loop,
        )
        return future.result()


_runtime = _AsyncWorkerRuntime()


@celery_app.task(
    name="helpdesk.process_ticket",
    acks_late=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 5},
)
def process_ticket_task(ticket_db_id: int) -> bool:
    return _runtime.run_ticket(ticket_db_id)


async def enqueue_ticket_task(ticket_db_id: int) -> None:
    await asyncio.to_thread(process_ticket_task.delay, ticket_db_id)
