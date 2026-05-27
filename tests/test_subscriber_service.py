from datetime import UTC, datetime, timedelta

import pytest

from bot.db.database import get_db
from bot.services import subscriber_service as ss

pytestmark = pytest.mark.usefixtures("tmp_db")


async def test_grant_then_double_grant() -> None:
    conn = await get_db()
    assert await ss.grant(conn, 100, granted_by=1) is True
    assert await ss.grant(conn, 100, granted_by=1) is False


async def test_revoke_round_trip() -> None:
    conn = await get_db()
    await ss.grant(conn, 200, granted_by=1)
    assert await ss.revoke(conn, 200) is True
    assert await ss.revoke(conn, 200) is False
    assert await ss.is_subscriber(conn, 200) is False


async def test_regrant_after_revoke_is_new() -> None:
    conn = await get_db()
    await ss.grant(conn, 300, granted_by=1)
    await ss.revoke(conn, 300)
    assert await ss.grant(conn, 300, granted_by=1) is True
    assert await ss.is_subscriber(conn, 300) is True


async def test_super_admin_is_subscriber_without_row(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ss.settings, "BOT_ADMIN_IDS", "777,888")
    conn = await get_db()
    assert ss.is_super_admin(777) is True
    assert await ss.is_subscriber(conn, 777) is True
    recipients = await ss.list_dm_recipients(conn)
    assert {777, 888}.issubset(recipients)


async def test_invite_happy_path() -> None:
    conn = await get_db()
    token, expires = await ss.create_invite(conn, super_admin_id=1, ttl_hours=24)
    assert expires is not None
    result = await ss.consume_invite(
        conn, token, user_id=42, username="alice", display_name="Alice"
    )
    assert result == "ok"
    assert await ss.is_subscriber(conn, 42) is True


async def test_invite_double_consume_rejected() -> None:
    conn = await get_db()
    token, _ = await ss.create_invite(conn, super_admin_id=1)
    first = await ss.consume_invite(conn, token, user_id=1, username=None, display_name=None)
    second = await ss.consume_invite(conn, token, user_id=2, username=None, display_name=None)
    assert first == "ok"
    assert second == "used"


async def test_invite_invalid_token() -> None:
    conn = await get_db()
    result = await ss.consume_invite(conn, "garbage", user_id=1, username=None, display_name=None)
    assert result == "invalid"


async def test_invite_expired() -> None:
    conn = await get_db()
    token, _ = await ss.create_invite(conn, super_admin_id=1, ttl_hours=1)
    past = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    await conn.execute("UPDATE invite_tokens SET expires_at=? WHERE token=?", (past, token))
    await conn.commit()
    result = await ss.consume_invite(conn, token, user_id=3, username=None, display_name=None)
    assert result == "expired"


async def test_list_subscribers_empty_then_one() -> None:
    conn = await get_db()
    assert await ss.list_active_subscribers(conn) == []
    await ss.grant(conn, 9, granted_by=1, username="bob", display_name="Bob")
    subs = await ss.list_active_subscribers(conn)
    assert len(subs) == 1
    assert subs[0].user_id == 9
    assert subs[0].username == "bob"
