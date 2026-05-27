from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from bot.db.database import get_db
from bot.db.queries import TranscriptionRow, log_transcription, upsert_chat
from bot.services.digest_service import _build_file_for_chat, _slug

pytestmark = pytest.mark.usefixtures("tmp_db")


MSK = ZoneInfo("Europe/Moscow")


async def _seed_row(
    *,
    chat_id: int,
    text: str,
    when_utc: datetime,
    username: str | None = "alice",
    success: bool = True,
) -> None:
    conn = await get_db()
    await log_transcription(
        conn,
        TranscriptionRow(
            chat_id=chat_id,
            user_id=42,
            message_id=1,
            content_type="voice",
            provider="openai",
            model="whisper-1",
            success=success,
            error_code=None if success else "transient",
            audio_seconds=3,
            latency_ms=500,
            transcript_text=text if success else None,
            username=username,
            display_name="Alice",
            msg_created_at=when_utc.isoformat(),
        ),
    )


async def test_build_file_filters_window_and_empty() -> None:
    conn = await get_db()
    await upsert_chat(conn, -100, "Family")
    end_utc = datetime(2026, 5, 26, 7, 0, tzinfo=UTC)  # 10:00 MSK
    start_utc = end_utc - timedelta(hours=24)

    await _seed_row(chat_id=-100, text="inside one", when_utc=end_utc - timedelta(hours=1))
    await _seed_row(chat_id=-100, text="inside two", when_utc=end_utc - timedelta(hours=23))
    before_ts = start_utc - timedelta(minutes=1)
    failed_ts = end_utc - timedelta(hours=2)
    empty_ts = end_utc - timedelta(hours=3)
    await _seed_row(chat_id=-100, text="before window", when_utc=before_ts)
    await _seed_row(chat_id=-100, text="at end (excluded)", when_utc=end_utc)
    await _seed_row(chat_id=-100, text="failed", when_utc=failed_ts, success=False)
    await _seed_row(chat_id=-100, text="", when_utc=empty_ts)

    built = await _build_file_for_chat(conn, -100, "Family", start_utc, end_utc, MSK)
    assert built is not None
    fname, data = built
    text = data.decode("utf-8")
    assert "inside one" in text
    assert "inside two" in text
    assert "before window" not in text
    assert "at end (excluded)" not in text
    assert "failed" not in text
    assert fname == "Family_2026-05-26.txt"
    # Header mentions MSK window endpoints.
    assert "2026-05-26 10:00" in text
    assert "2026-05-25 10:00" in text


async def test_build_file_returns_none_when_no_rows() -> None:
    conn = await get_db()
    end_utc = datetime(2026, 5, 26, 7, 0, tzinfo=UTC)
    start_utc = end_utc - timedelta(hours=24)
    assert await _build_file_for_chat(conn, -999, "Nothing", start_utc, end_utc, MSK) is None


async def test_slug_cyrillic_fallback() -> None:
    assert _slug("Семья", 100) == "chat_100"
    assert _slug(None, 200) == "chat_200"
    assert _slug("Work Chat", 300) == "Work_Chat"
    assert _slug("a/b/c", 400) == "a_b_c"


async def test_per_chat_files_separate() -> None:
    conn = await get_db()
    await upsert_chat(conn, -10, "Alpha")
    await upsert_chat(conn, -20, "Beta")
    end_utc = datetime(2026, 5, 26, 7, 0, tzinfo=UTC)
    start_utc = end_utc - timedelta(hours=24)
    await _seed_row(chat_id=-10, text="alpha-msg", when_utc=end_utc - timedelta(hours=1))
    await _seed_row(chat_id=-20, text="beta-msg", when_utc=end_utc - timedelta(hours=2))

    a = await _build_file_for_chat(conn, -10, "Alpha", start_utc, end_utc, MSK)
    b = await _build_file_for_chat(conn, -20, "Beta", start_utc, end_utc, MSK)
    assert a is not None and b is not None
    assert "alpha-msg" in a[1].decode()
    assert "beta-msg" in b[1].decode()
    assert "beta-msg" not in a[1].decode()
    assert "alpha-msg" not in b[1].decode()
