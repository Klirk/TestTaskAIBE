import asyncio
from urllib.parse import urlparse

import httpx

from src.core.exceptions import DeliveryFailedError
from src.schemas.ticket import HelpdeskReplyPayload


class DeliveryService:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        max_retries: int,
        timeout_seconds: float,
        local_mock_base_url: str = "http://127.0.0.1:8000",
    ) -> None:
        self._http_client = http_client
        self._max_retries = max(1, max_retries)
        self._timeout_seconds = timeout_seconds
        self._local_mock_base_url = local_mock_base_url.rstrip("/")

    def _resolve_reply_url(self, reply_url: str, ticket_id: str) -> str:
        parsed = urlparse(reply_url)
        if parsed.hostname == "helpdesk.example.com":
            path = parsed.path or f"/tickets/{ticket_id}/replies"
            return f"{self._local_mock_base_url}/mock/helpdesk{path}"
        return reply_url

    async def send_reply(
        self,
        reply_url: str,
        ticket_id: str,
        message: str,
    ) -> tuple[int, str | None]:
        target_url = self._resolve_reply_url(reply_url, ticket_id)
        payload = HelpdeskReplyPayload(ticket_id=ticket_id, message=message)
        headers = {
            "Idempotency-Key": ticket_id,
            "Content-Type": "application/json",
        }

        last_error: str | None = None

        for attempt in range(1, self._max_retries + 1):
            attempts = attempt
            try:
                response = await self._http_client.post(
                    target_url,
                    json=payload.model_dump(),
                    headers=headers,
                    timeout=self._timeout_seconds,
                )
                if response.status_code == 201:
                    return attempts, None

                if 500 <= response.status_code < 600:
                    last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                else:
                    raise DeliveryFailedError(
                        f"Unexpected status {response.status_code}: {response.text[:200]}"
                    )
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"

            if attempt < self._max_retries:
                backoff = min(0.2 * (2 ** (attempt - 1)), 2.0)
                await asyncio.sleep(backoff)

        raise DeliveryFailedError(last_error or "Reply delivery failed after retries")
