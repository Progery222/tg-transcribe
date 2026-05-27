from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import CallbackQuery, Message

from bot.middlewares.super_admin_only import SuperAdminOnlyMiddleware


@pytest.fixture(autouse=True)
def _admin_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    from bot.config import settings as cfg

    monkeypatch.setattr(cfg, "BOT_ADMIN_IDS", "100,200")


def _fake_message(uid: int) -> MagicMock:
    msg = MagicMock(spec=Message)
    msg.from_user = MagicMock(id=uid)
    msg.reply = AsyncMock()
    return msg


def _fake_callback(uid: int) -> MagicMock:
    cq = MagicMock(spec=CallbackQuery)
    cq.from_user = MagicMock(id=uid)
    cq.answer = AsyncMock()
    return cq


async def test_admin_passes_through() -> None:
    handler = AsyncMock(return_value="done")
    mw = SuperAdminOnlyMiddleware()
    msg = _fake_message(100)
    result = await mw(handler, msg, {})
    assert result == "done"
    handler.assert_awaited_once()


async def test_non_admin_message_rejected() -> None:
    handler = AsyncMock()
    mw = SuperAdminOnlyMiddleware()
    msg = _fake_message(999)
    result = await mw(handler, msg, {})
    assert result is None
    handler.assert_not_awaited()
    msg.reply.assert_awaited_once()


async def test_non_admin_callback_alert() -> None:
    handler = AsyncMock()
    mw = SuperAdminOnlyMiddleware()
    cq = _fake_callback(999)
    result = await mw(handler, cq, {})
    assert result is None
    handler.assert_not_awaited()
    cq.answer.assert_awaited_once()
    assert cq.answer.call_args.kwargs.get("show_alert") is True
