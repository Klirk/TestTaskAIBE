from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.knowledge_article import KnowledgeArticle


class KnowledgeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_articles(self, articles_data: list[dict[str, Any]]) -> None:
        for item in articles_data:
            stmt = (
                pg_insert(KnowledgeArticle)
                .values(
                    slug=item["slug"],
                    title=item["title"],
                    url=item["url"],
                    content=item["content"],
                    keywords=item.get("keywords", []),
                )
                .on_conflict_do_update(
                    index_elements=[KnowledgeArticle.slug],
                    set_={
                        "title": item["title"],
                        "url": item["url"],
                        "content": item["content"],
                        "keywords": item.get("keywords", []),
                    },
                )
            )
            await self._session.execute(stmt)

    async def list_all(self) -> list[KnowledgeArticle]:
        stmt = select(KnowledgeArticle).order_by(KnowledgeArticle.id.asc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
