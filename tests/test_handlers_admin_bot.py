from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.db.database import get_db
from bot.handlers import admin_bot as ab
from bot.services import subscriber_service as ss

pytestmark = pytest.mark.usefixtures("tmp_db")


def _msg(uid: int = 100, text: str = "/grant 42") -> object:
    return SimpleNamespace(
        from_user=SimpleNamespace(id=uid),
        chat=SimpleNamespace(id=uid),
        reply=AsyncMock(),
        answer=AsyncMock(),
    )


def _cmd(args: str | None) -> object:
    return SimpleNamespace(args=args)


async def test_grant_with_numeric_id() -> None:
    msg = _msg()
    await ab.cmd_grant(msg, _cmd("42"))
    conn = await get_db()
    assert await ss.is_subscriber(conn, 42) is True
    msg.reply.assert_awaited_once()


async def test_grant_with_username_only_rejected() -> None:
    msg = _msg()
    await ab.cmd_grant(msg, _cmd("@alice"))
    msg.reply.assert_awaited_once()


async def test_grant_missing_arg_rejected() -> None:
    msg = _msg()
    await ab.cmd_grant(msg, _cmd(None))
    msg.reply.assert_awaited_once()


async def test_revoke_existing() -> None:
    conn = await get_db()
    await ss.grant(conn, 42, granted_by=1)
    msg = _msg()
    await ab.cmd_revoke(msg, _cmd("42"))
    assert await ss.is_subscriber(conn, 42) is False


async def test_subscribers_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    # super-admin presence shouldn't show up in /subscribers (only DB-rows do)
    monkeypatch.setattr(ss.settings, "BOT_ADMIN_IDS", "100")
    msg = _msg()
    await ab.cmd_subscribers(msg)
    msg.reply.assert_awaited_once()


async def test_chats_empty() -> None:
    msg = _msg()
    await ab.cmd_chats(msg)
    msg.reply.assert_awaited_once()


async def test_invite_creates_url() -> None:
    bot = SimpleNamespace(get_me=AsyncMock(return_value=SimpleNamespace(username="testbot")))
    msg = _msg()
    await ab.cmd_invite(msg, bot)
    msg.reply.assert_awaited_once()
    sent = msg.reply.call_args.args[0]
    assert "https://t.me/testbot?start=" in sent
