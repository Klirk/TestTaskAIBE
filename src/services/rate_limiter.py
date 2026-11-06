import asyncio
import time
from collections import deque


class AsyncRateLimiter:
    def __init__(self, max_requests: int, period_seconds: float = 60.0) -> None:
        self._max_requests = max_requests
        self._period_seconds = period_seconds
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    @property
    def max_requests(self) -> int:
        return self._max_requests

    @property
    def period_seconds(self) -> float:
        return self._period_seconds

    async def acquire(self) -> float:
        total_waited = 0.0
        while True:
            async with self._lock:
                now = time.monotonic()
                while self._timestamps and (now - self._timestamps[0]) >= self._period_seconds:
                    self._timestamps.popleft()

                if len(self._timestamps) < self._max_requests:
                    self._timestamps.append(now)
                    return total_waited

                earliest = self._timestamps[0]
                wait_time = max(0.001, self._period_seconds - (now - earliest))

            await asyncio.sleep(wait_time)
            total_waited += wait_time

    def current_window_count(self) -> int:
        now = time.monotonic()
        while self._timestamps and (now - self._timestamps[0]) >= self._period_seconds:
            self._timestamps.popleft()
        return len(self._timestamps)
