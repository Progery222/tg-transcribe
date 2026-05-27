from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)

from bot.services.dm_sender import send_transcript_dm


def _make_bot(side_effect_per_user: dict[int, list]) -> object:
    """Returns a fake bot whose ``send_message`` mock advances per-user side effects."""

    async def send_message(uid: int, text: str, **_: object) -> None:
        effects = side_effect_per_user.get(uid)
        if not effects:
            return
        nxt = effects.pop(0)
        if isinstance(nxt, BaseException):
            raise nxt
        return nxt

    bot = AsyncMock()
    bot.send_message = AsyncMock(side_effect=send_message)
    return bot


async def test_all_recipients_succeed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DM_SEND_DELAY_MS", "0")
    from bot.config import settings as cfg

    cfg.DM_SEND_DELAY_MS = 0
    bot = _make_bot({1: [None], 2: [None], 3: [None]})
    sent = await send_transcript_dm(bot, [1, 2, 3], "hello")
    assert sent == 3
    assert bot.send_message.call_count == 3


async def test_forbidden_skipped() -> None:
    from bot.config import settings as cfg

    cfg.DM_SEND_DELAY_MS = 0
    bot = _make_bot(
        {
            1: [None],
            2: [TelegramForbiddenError(method=None, message="blocked")],
            3: [None],
        }
    )
    sent = await send_transcript_dm(bot, [1, 2, 3], "hi")
    assert sent == 2


async def test_retry_after_then_success() -> None:
    from bot.config import settings as cfg

    cfg.DM_SEND_DELAY_MS = 0
    err = TelegramRetryAfter(method=None, message="slow", retry_after=0)
    bot = _make_bot({1: [err, None]})
    sent = await send_transcript_dm(bot, [1], "hi")
    assert sent == 1
    assert bot.send_message.call_count == 2


async def test_retry_after_then_crash() -> None:
    from bot.config import settings as cfg

    cfg.DM_SEND_DELAY_MS = 0
    err = TelegramRetryAfter(method=None, message="slow", retry_after=0)
    bot = _make_bot({1: [err, RuntimeError("still bad")]})
    sent = await send_transcript_dm(bot, [1], "hi")
    assert sent == 0


async def test_bad_request_logged_no_retry() -> None:
    from bot.config import settings as cfg

    cfg.DM_SEND_DELAY_MS = 0
    err = TelegramBadRequest(method=None, message="too long")
    bot = _make_bot({1: [err], 2: [None]})
    sent = await send_transcript_dm(bot, [1, 2], "hi")
    assert sent == 1
