import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.models.ticket import Ticket, TicketStatus
from src.repositories.ticket_repository import TicketRepository
from src.services.llm_service import LLMService
from src.services.rag_service import RAGService

logger = logging.getLogger(__name__)


class TicketProcessorPool:
    def __init__(
        self,
        session_maker: async_sessionmaker[AsyncSession],
        rag_service: RAGService,
        llm_service: LLMService,
        concurrency: int,
        poll_interval_seconds: float,
    ) -> None:
        self._session_maker = session_maker
        self._rag_service = rag_service
        self._llm_service = llm_service
        self._concurrency = max(1, concurrency)
        self._poll_interval = poll_interval_seconds
        self._wake_event = asyncio.Event()
        self._stop_event = asyncio.Event()
        self._tasks: list[asyncio.Task[None]] = []

    @property
    def wake_event(self) -> asyncio.Event:
        return self._wake_event

    async def start(self) -> None:
        async with self._session_maker() as session:
            repo = TicketRepository(session)
            await repo.reset_stale_generating_tickets()
            await session.commit()

        self._stop_event.clear()
        self._tasks = [
            asyncio.create_task(self._worker_loop())
            for _ in range(self._concurrency)
        ]

    async def stop(self) -> None:
        self._stop_event.set()
        self._wake_event.set()
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def process_ticket_by_id(self, ticket_db_id: int) -> bool:
        async with self._session_maker() as session:
            repo = TicketRepository(session)
            ticket = await repo.claim_ticket_by_id(ticket_db_id)
            if ticket is None:
                return False
            return await self._execute_claimed_ticket(session, ticket)

    async def process_one_ticket(self) -> bool:
        async with self._session_maker() as session:
            repo = TicketRepository(session)
            ticket = await repo.claim_next_new_ticket()
            if ticket is None:
                return False
            return await self._execute_claimed_ticket(session, ticket)

    async def _execute_claimed_ticket(
        self,
        claim_session: AsyncSession,
        ticket: Ticket,
    ) -> bool:
        ticket_db_id = ticket.id
        ticket_ext_id = ticket.ticket_id
        customer_message = ticket.message
        await claim_session.commit()

        try:
            async with self._session_maker() as session:
                articles = await self._rag_service.find_relevant_articles(
                    session=session,
                    query_text=customer_message,
                    top_k=2,
                )
                article_refs = [art.to_ref_dict() for art in articles]

            draft_reply = await self._llm_service.generate_draft(
                ticket_id=ticket_ext_id,
                customer_message=customer_message,
                articles=articles,
            )

            async with self._session_maker() as session:
                repo = TicketRepository(session)
                await repo.save_generated_draft(
                    ticket_db_id=ticket_db_id,
                    draft_reply=draft_reply,
                    matched_articles=article_refs,
                )
                await session.commit()
            return True
        except asyncio.CancelledError:
            async with self._session_maker() as session:
                repo = TicketRepository(session)
                locked = await repo.lock_by_id(ticket_db_id)
                if locked is not None and locked.status == TicketStatus.GENERATING_DRAFT:
                    locked.status = TicketStatus.NEW
                    await session.commit()
            raise
        except Exception as exc:
            logger.exception("Failed processing ticket %s", ticket_ext_id)
            async with self._session_maker() as session:
                repo = TicketRepository(session)
                locked = await repo.lock_by_id(ticket_db_id)
                if locked is not None and locked.status == TicketStatus.GENERATING_DRAFT:
                    locked.status = TicketStatus.NEW
                    locked.last_error = str(exc)
                    await session.commit()
            raise

    async def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                processed = await self.process_one_ticket()
                if processed:
                    continue
            except Exception:
                logger.exception("Worker loop error")

            try:
                await asyncio.wait_for(
                    self._wake_event.wait(),
                    timeout=self._poll_interval,
                )
                self._wake_event.clear()
            except TimeoutError:
                pass
