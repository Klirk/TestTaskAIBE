from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.webhook_event import WebhookEvent


class WebhookRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record_event_if_new(self, event_id: str, ticket_id: str) -> bool:
        stmt = (
            pg_insert(WebhookEvent)
            .values(event_id=event_id, ticket_id=ticket_id)
            .on_conflict_do_nothing(index_elements=[WebhookEvent.event_id])
            .returning(WebhookEvent.id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None
