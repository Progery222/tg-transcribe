from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest

from bot.db.database import get_db
from bot.db.queries import Chat, TranscriptionRow, log_transcription, upsert_chat
from bot.keyboards.inline import (
    CB_DIGEST_ALL,
    CB_DIGEST_CANCEL,
    CB_DIGEST_ONE_PREFIX,
    digest_group_picker_kb,
    parse_digest_group_callback,
)
from bot.services import digest_service as ds
from bot.services.digest_service import (
    _build_file_for_chat,
    _manual_window,
    _send_digest,
    _slug,
)

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


async def test_manual_window_after_fire() -> None:
    # Run at 14:30 MSK: window is [today 10:00 MSK, now).
    now = datetime(2026, 6, 3, 14, 30, tzinfo=MSK)
    start_utc, end_utc = _manual_window(now)
    assert start_utc == datetime(2026, 6, 3, 10, 0, tzinfo=MSK).astimezone(UTC)
    assert end_utc == now.astimezone(UTC)


async def test_manual_window_before_fire() -> None:
    # Run at 08:00 MSK, before today's 10:00 fire: window starts yesterday 10:00.
    now = datetime(2026, 6, 3, 8, 0, tzinfo=MSK)
    start_utc, end_utc = _manual_window(now)
    assert start_utc == datetime(2026, 6, 2, 10, 0, tzinfo=MSK).astimezone(UTC)
    assert end_utc == now.astimezone(UTC)


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


def test_digest_group_picker_kb_lists_groups_all_cancel() -> None:
    chats = [
        Chat(chat_id=-10, title="Alpha", active=True),
        Chat(chat_id=-20, title=None, active=True),
    ]
    kb = digest_group_picker_kb(chats)
    flat = [b for row in kb.inline_keyboard for b in row]
    assert len(flat) == 4  # one per group + "all" + "cancel"
    assert flat[0].text == "Alpha"
    assert flat[0].callback_data == f"{CB_DIGEST_ONE_PREFIX}-10"
    assert flat[1].text == "Chat -20"  # fallback label when title is None
    assert flat[1].callback_data == f"{CB_DIGEST_ONE_PREFIX}-20"
    assert flat[2].callback_data == CB_DIGEST_ALL
    assert flat[3].callback_data == CB_DIGEST_CANCEL


def test_parse_digest_group_callback() -> None:
    assert parse_digest_group_callback(f"{CB_DIGEST_ONE_PREFIX}-100500") == -100500
    assert parse_digest_group_callback(CB_DIGEST_ALL) is None
    assert parse_digest_group_callback(f"{CB_DIGEST_ONE_PREFIX}nope") is None


async def _seed_two_groups(monkeypatch: pytest.MonkeyPatch) -> tuple[datetime, datetime]:
    # Pin recipients so the assertions don't depend on real BOT_ADMIN_IDS from .env.
    monkeypatch.setattr(ds, "list_dm_recipients", AsyncMock(return_value={111}))
    conn = await get_db()
    await upsert_chat(conn, -10, "Alpha")
    await upsert_chat(conn, -20, "Beta")
    end_utc = datetime(2026, 6, 3, 11, 0, tzinfo=UTC)
    start_utc = end_utc - timedelta(hours=2)
    await _seed_row(chat_id=-10, text="alpha-msg", when_utc=end_utc - timedelta(minutes=30))
    await _seed_row(chat_id=-20, text="beta-msg", when_utc=end_utc - timedelta(minutes=30))
    return start_utc, end_utc


async def test_send_digest_filters_to_one_chat(monkeypatch: pytest.MonkeyPatch) -> None:
    start_utc, end_utc = await _seed_two_groups(monkeypatch)
    bot = SimpleNamespace(send_document=AsyncMock())
    sent = await _send_digest(bot, start_utc, end_utc, only_chat_id=-10)
    assert sent == 1
    assert bot.send_document.await_count == 1
    caption = bot.send_document.await_args.kwargs["caption"]
    assert "Alpha" in caption
    assert "Beta" not in caption


async def test_send_digest_all_chats_when_no_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    start_utc, end_utc = await _seed_two_groups(monkeypatch)
    bot = SimpleNamespace(send_document=AsyncMock())
    sent = await _send_digest(bot, start_utc, end_utc)
    assert sent == 2
    assert bot.send_document.await_count == 2
    captions = " ".join(c.kwargs["caption"] for c in bot.send_document.await_args_list)
    assert "Alpha" in captions
    assert "Beta" in captions
