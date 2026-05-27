from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import bot.handlers.voice as voice
from bot.db.queries import ChatSettings
from bot.services.transcriber import TranscriptionResult

pytestmark = pytest.mark.usefixtures("tmp_db")


def _msg() -> object:
    chat = SimpleNamespace(id=-1001, title="Family", type="supergroup")
    user = SimpleNamespace(id=42, username="alice", first_name="Al", last_name=None)
    voice_obj = SimpleNamespace(file_id="vfid", file_size=1024, mime_type="audio/ogg", duration=4)
    return SimpleNamespace(
        chat=chat,
        from_user=user,
        message_id=99,
        date=datetime(2026, 5, 26, 12, 0, tzinfo=UTC),
        voice=voice_obj,
        video_note=None,
        audio=None,
        video=None,
        reply=AsyncMock(),
        answer=AsyncMock(),
    )


def _cs(provider: str = "openai") -> ChatSettings:
    return ChatSettings(
        chat_id=-1001,
        provider=provider,
        model="gpt-4o-mini-transcribe",
        language=None,
        enabled=True,
    )


class _FakeTranscriber:
    provider = "openai"

    def __init__(self, result: TranscriptionResult) -> None:
        self._result = result

    async def transcribe(self, *args, **kwargs) -> TranscriptionResult:
        return self._result


async def test_voice_success_fanout_to_recipients(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(voice, "download_file", AsyncMock(return_value=b"oggbytes"))
    monkeypatch.setattr(
        voice,
        "prepare_payload",
        AsyncMock(
            return_value=SimpleNamespace(data=b"oggbytes", mime="audio/ogg", filename="v.ogg")
        ),
    )
    sent_calls: list[tuple[set[int], str]] = []

    async def fake_dm(bot, recipients, text):
        sent_calls.append((set(recipients), text))
        return len(set(recipients))

    monkeypatch.setattr(voice, "send_transcript_dm", fake_dm)
    monkeypatch.setattr(voice, "list_dm_recipients", AsyncMock(return_value={111, 222}))

    transcriber = _FakeTranscriber(
        TranscriptionResult(
            text="hello world",
            model="gpt-4o-mini-transcribe",
            provider="openai",
            duration_ms=100,
            language="en",
        )
    )
    bot = SimpleNamespace()

    await voice.on_media(
        _msg(),
        bot,
        chat_settings=_cs(),
        transcribers={"openai": transcriber},
    )
    assert len(sent_calls) == 1
    recipients, text = sent_calls[0]
    assert recipients == {111, 222}
    assert "Family" in text
    assert "@alice" in text
    assert "hello world" in text


async def test_voice_empty_transcript_no_fanout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(voice, "download_file", AsyncMock(return_value=b"x"))
    monkeypatch.setattr(
        voice,
        "prepare_payload",
        AsyncMock(return_value=SimpleNamespace(data=b"x", mime="audio/ogg", filename="v.ogg")),
    )
    fake_dm = AsyncMock()
    monkeypatch.setattr(voice, "send_transcript_dm", fake_dm)
    monkeypatch.setattr(voice, "list_dm_recipients", AsyncMock(return_value={111}))

    transcriber = _FakeTranscriber(
        TranscriptionResult(text="   ", model="x", provider="openai", duration_ms=10, language=None)
    )
    await voice.on_media(
        _msg(), SimpleNamespace(), chat_settings=_cs(), transcribers={"openai": transcriber}
    )
    fake_dm.assert_not_awaited()


async def test_voice_no_recipients_no_fanout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(voice, "download_file", AsyncMock(return_value=b"x"))
    monkeypatch.setattr(
        voice,
        "prepare_payload",
        AsyncMock(return_value=SimpleNamespace(data=b"x", mime="audio/ogg", filename="v.ogg")),
    )
    fake_dm = AsyncMock()
    monkeypatch.setattr(voice, "send_transcript_dm", fake_dm)
    monkeypatch.setattr(voice, "list_dm_recipients", AsyncMock(return_value=set()))

    transcriber = _FakeTranscriber(
        TranscriptionResult(text="hi", model="x", provider="openai", duration_ms=10, language=None)
    )
    await voice.on_media(
        _msg(), SimpleNamespace(), chat_settings=_cs(), transcribers={"openai": transcriber}
    )
    fake_dm.assert_not_awaited()


async def test_voice_long_text_split(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(voice, "download_file", AsyncMock(return_value=b"x"))
    monkeypatch.setattr(
        voice,
        "prepare_payload",
        AsyncMock(return_value=SimpleNamespace(data=b"x", mime="audio/ogg", filename="v.ogg")),
    )
    chunks_seen: list[str] = []

    async def fake_dm(bot, recipients, text):
        chunks_seen.append(text)
        return len(set(recipients))

    monkeypatch.setattr(voice, "send_transcript_dm", fake_dm)
    monkeypatch.setattr(voice, "list_dm_recipients", AsyncMock(return_value={1}))

    long_text = "слово " * 1000
    transcriber = _FakeTranscriber(
        TranscriptionResult(
            text=long_text, model="x", provider="openai", duration_ms=10, language=None
        )
    )
    await voice.on_media(
        _msg(), SimpleNamespace(), chat_settings=_cs(), transcribers={"openai": transcriber}
    )
    assert len(chunks_seen) >= 2
    for chunk in chunks_seen:
        assert len(chunk) <= 4000


async def test_voice_disabled_chat_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_dm = AsyncMock()
    monkeypatch.setattr(voice, "send_transcript_dm", fake_dm)
    cs = ChatSettings(
        chat_id=-1001,
        provider="openai",
        model="gpt-4o-mini-transcribe",
        language=None,
        enabled=False,
    )
    await voice.on_media(
        _msg(),
        SimpleNamespace(),
        chat_settings=cs,
        transcribers={
            "openai": _FakeTranscriber(
                TranscriptionResult(
                    text="x", model="x", provider="openai", duration_ms=1, language=None
                )
            )
        },
    )
    fake_dm.assert_not_awaited()
