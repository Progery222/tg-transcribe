import pytest

from bot.db.database import get_db
from bot.services import subscriber_service as ss

pytestmark = pytest.mark.usefixtures("tmp_db")


async def test_consume_invite_ok_then_subscriber() -> None:
    conn = await get_db()
    token, _ = await ss.create_invite(conn, super_admin_id=1)
    result = await ss.consume_invite(conn, token, user_id=42, username="al", display_name="Al")
    assert result == "ok"
    assert await ss.is_subscriber(conn, 42) is True


async def test_consume_invite_invalid() -> None:
    conn = await get_db()
    assert (
        await ss.consume_invite(conn, "nope", user_id=1, username=None, display_name=None)
        == "invalid"
    )


async def test_consume_invite_used() -> None:
    conn = await get_db()
    token, _ = await ss.create_invite(conn, super_admin_id=1)
    await ss.consume_invite(conn, token, user_id=1, username=None, display_name=None)
    assert (
        await ss.consume_invite(conn, token, user_id=2, username=None, display_name=None) == "used"
    )
