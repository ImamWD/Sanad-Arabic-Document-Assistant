"""Generation runs under LLM_MAX_CONCURRENCY (SYSTEM_DESIGN §6, "Queueing").

One queue per api process. Retrieval and gate refusals never wait here: only the LLM call does.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


class GenerationQueue:
    def __init__(self, capacity: int) -> None:
        self._capacity = capacity
        self._slots = asyncio.Semaphore(capacity)
        self._running = 0
        self._waiting = 0

    def ahead(self) -> int:
        """How many generations a request arriving now would wait for (0: it starts at once)."""
        busy = self._running + self._waiting
        return busy - self._capacity + 1 if busy >= self._capacity else 0

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        """Hold a generation slot. A request cancelled while waiting leaves the queue."""
        self._waiting += 1
        try:
            await self._slots.acquire()
        finally:
            self._waiting -= 1
        self._running += 1
        try:
            yield
        finally:
            self._running -= 1
            self._slots.release()
