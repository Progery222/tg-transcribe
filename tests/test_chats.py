import pytest

from bot.db.database import get_db
from bot.db.queries import list_active_chats, upsert_chat

pytestmark = pytest.mark.usefixtures("tmp_db")


async def test_upsert_then_list() -> None:
    conn = await get_db()
    await upsert_chat(conn, -100, "Family")
    await upsert_chat(conn, -200, "Work")
    chats = await list_active_chats(conn)
    titles = {c.title for c in chats}
    assert titles == {"Family", "Work"}


async def test_upsert_title_update_preserves_when_null() -> None:
    conn = await get_db()
    await upsert_chat(conn, -1, "Initial")
    await upsert_chat(conn, -1, None)  # Telegram sometimes drops title in updates
    chats = await list_active_chats(conn)
    assert chats[0].title == "Initial"


async def test_inactive_excluded_from_list() -> None:
    conn = await get_db()
    await upsert_chat(conn, -1, "Gone", active=False)
    await upsert_chat(conn, -2, "Here", active=True)
    chats = await list_active_chats(conn)
    assert {c.chat_id for c in chats} == {-2}
