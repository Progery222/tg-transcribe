import pytest

from bot.db.database import get_db
from bot.db.queries import (
    TranscriptionRow,
    get_chat_settings,
    log_transcription,
    upsert_chat_settings,
)

pytestmark = pytest.mark.usefixtures("tmp_db")


async def test_upsert_then_read_roundtrip() -> None:
    conn = await get_db()
    await upsert_chat_settings(conn, 100, provider="gemini", model="gemini-2.5-flash")
    cs = await get_chat_settings(conn, 100)
    assert cs is not None
    assert cs.provider == "gemini"
    assert cs.model == "gemini-2.5-flash"
    assert cs.enabled is True
    assert cs.language is None


async def test_upsert_preserves_unset_fields() -> None:
    conn = await get_db()
    await upsert_chat_settings(conn, 200, provider="openai", model="whisper-1")
    await upsert_chat_settings(conn, 200, enabled=False)
    cs = await get_chat_settings(conn, 200)
    assert cs is not None
    assert cs.provider == "openai"
    assert cs.model == "whisper-1"
    assert cs.enabled is False


async def test_get_nonexistent_returns_none() -> None:
    conn = await get_db()
    assert await get_chat_settings(conn, 999) is None


async def test_log_transcription() -> None:
    conn = await get_db()
    await log_transcription(
        conn,
        TranscriptionRow(
            chat_id=1,
            user_id=2,
            message_id=3,
            content_type="voice",
            provider="openai",
            model="gpt-4o-mini-transcribe",
            success=True,
            error_code=None,
            audio_seconds=5,
            latency_ms=1200,
        ),
    )
    async with conn.execute(
        "SELECT chat_id, success, provider, audio_seconds FROM transcriptions"
    ) as cur:
        rows = await cur.fetchall()
    assert len(rows) == 1
    assert rows[0] == (1, 1, "openai", 5)
