"""Verify ``_ensure_columns`` heals a legacy v1 ``transcriptions`` table."""

from pathlib import Path

import aiosqlite
import pytest

import bot.db.database as db_mod
from bot.db.database import _ensure_columns, init_db


@pytest.fixture
async def legacy_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Create a DB containing the v1 transcriptions schema (missing v2 columns)."""
    db_path = tmp_path / "legacy.sqlite3"
    monkeypatch.setattr(db_mod.settings, "DB_PATH", str(db_path))
    db_mod._conn = None

    # Hand-craft the v1 transcriptions table (no transcript_text / username / etc.)
    async with aiosqlite.connect(str(db_path)) as conn:
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.executescript(
            """
            CREATE TABLE transcriptions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              chat_id INTEGER NOT NULL,
              user_id INTEGER,
              message_id INTEGER,
              content_type TEXT,
              provider TEXT,
              model TEXT,
              success INTEGER NOT NULL,
              error_code TEXT,
              audio_seconds INTEGER,
              latency_ms INTEGER,
              created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            INSERT INTO transcriptions (chat_id, user_id, content_type, success)
            VALUES (-1, 99, 'voice', 1);
            """
        )
        await conn.commit()

    yield db_path

    if db_mod._conn is not None:
        await db_mod._conn.close()
        db_mod._conn = None


async def test_init_db_adds_missing_columns(legacy_db: Path) -> None:
    await init_db()
    conn = await db_mod.get_db()

    async with conn.execute("PRAGMA table_info(transcriptions)") as cur:
        cols = {row[1] for row in await cur.fetchall()}
    assert {"transcript_text", "username", "display_name", "msg_created_at"} <= cols

    # Existing row preserved
    async with conn.execute("SELECT chat_id, user_id FROM transcriptions") as cur:
        rows = await cur.fetchall()
    assert rows == [(-1, 99)]


async def test_ensure_columns_idempotent(legacy_db: Path) -> None:
    await init_db()
    conn = await db_mod.get_db()
    # Second call must not raise.
    await _ensure_columns(
        conn,
        "transcriptions",
        {
            "transcript_text": "TEXT",
            "username": "TEXT",
        },
    )
    async with conn.execute("PRAGMA table_info(transcriptions)") as cur:
        cols = {row[1] for row in await cur.fetchall()}
    assert "transcript_text" in cols
