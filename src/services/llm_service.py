import asyncio
import random
import time
from typing import Any

import httpx

from src.models.knowledge_article import KnowledgeArticle
from src.services.rate_limiter import AsyncRateLimiter


class LLMService:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        rate_limiter: AsyncRateLimiter,
        base_url: str,
        model: str,
        api_key: str,
        min_latency_seconds: float,
        max_latency_seconds: float,
    ) -> None:
        self._http_client = http_client
        self._rate_limiter = rate_limiter
        self._base_url = base_url
        self._model = model
        self._api_key = api_key.strip()
        self._min_latency = min_latency_seconds
        self._max_latency = max_latency_seconds

    async def generate_draft(
        self,
        ticket_id: str,
        customer_message: str,
        articles: list[KnowledgeArticle],
    ) -> str:
        await self._rate_limiter.acquire()

        target_duration = random.uniform(self._min_latency, self._max_latency)
        started_at = time.monotonic()

        provider_reply = await self._call_provider(
            ticket_id=ticket_id,
            customer_message=customer_message,
            articles=articles,
        )

        elapsed = time.monotonic() - started_at
        remaining = target_duration - elapsed
        if remaining > 0:
            await asyncio.sleep(remaining)

        if provider_reply:
            return provider_reply

        return self._build_fallback_draft(articles)

    async def _call_provider(
        self,
        ticket_id: str,
        customer_message: str,
        articles: list[KnowledgeArticle],
    ) -> str | None:
        kb_context = "\n\n".join(
            f"Стаття: {art.title}\nURL: {art.url}\nЗміст: {art.content}"
            for art in articles
        )
        system_prompt = (
            "Ти — помічник служби підтримки CloudFlow. Напиши ввічливу чернетку відповіді клієнту "
            "українською мовою на основі наведених статей бази знань та обов'язково додай "
            "посилання на них."
        )
        user_prompt = (
            f"Звернення #{ticket_id}: {customer_message}\n\n"
            f"Релевантні статті бази знань:\n{kb_context}"
        )

        token = self._api_key if self._api_key else "no-api-key-configured"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
        }

        try:
            response = await self._http_client.post(
                self._base_url,
                headers=headers,
                json=payload,
                timeout=25.0,
            )
            if self._api_key and response.status_code == 200:
                body = response.json()
                choices = body.get("choices") or []
                if choices:
                    content = choices[0].get("message", {}).get("content")
                    if isinstance(content, str) and content.strip():
                        return content.strip()
        except httpx.HTTPError:
            return None

        return None

    @staticmethod
    def _build_fallback_draft(articles: list[KnowledgeArticle]) -> str:
        if not articles:
            return (
                "Вітаємо! Дякуємо за звернення до служби підтримки CloudFlow. "
                "Ми вже перевіряємо ваше питання та повернемося з детальною відповіддю."
            )

        primary = articles[0]
        links_lines = [f"- {art.title}: {art.url}" for art in articles]
        links_block = "\n".join(links_lines)

        return (
            f"{primary.content}\n\n"
            f"Корисні матеріали з бази знань:\n{links_block}"
        )
