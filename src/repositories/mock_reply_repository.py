from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.mock_reply import MockReply


class MockReplyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_ticket_id(self, ticket_id: str) -> MockReply | None:
        stmt = select(MockReply).where(MockReply.ticket_id == ticket_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def record_reply_idempotent(
        self,
        ticket_id: str,
        message: str,
        idempotency_key: str | None,
    ) -> tuple[MockReply, bool]:
        stmt = (
            pg_insert(MockReply)
            .values(
                ticket_id=ticket_id,
                message=message,
                idempotency_key=idempotency_key,
            )
            .on_conflict_do_nothing(index_elements=[MockReply.ticket_id])
            .returning(MockReply)
        )
        result = await self._session.execute(stmt)
        created = result.scalar_one_or_none()
        if created is not None:
            return created, True
        existing = await self.get_by_ticket_id(ticket_id)
        assert existing is not None
        return existing, False

    async def list_all(self) -> list[MockReply]:
        stmt = select(MockReply).order_by(MockReply.created_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
