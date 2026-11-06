from typing import Any

from sqlalchemy import JSON, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class KnowledgeArticle(Base, TimestampMixin):
    __tablename__ = "knowledge_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    def to_ref_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "title": self.title,
            "url": self.url,
        }
