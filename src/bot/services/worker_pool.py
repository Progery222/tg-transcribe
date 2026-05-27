import asyncio
from collections.abc import Awaitable, Callable

from bot.config import settings

_sem = asyncio.Semaphore(settings.MAX_CONCURRENT_TRANSCRIPTIONS)


async def with_slot[T](coro_factory: Callable[[], Awaitable[T]]) -> T:
    """Run ``coro_factory()`` while holding a global concurrency slot.

    Use a factory (not a coroutine) so the work is not started until we have a slot,
    avoiding `coroutine was never awaited` warnings on cancellation.
    """
    async with _sem:
        return await coro_factory()
