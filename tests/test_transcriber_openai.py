from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from openai import APIConnectionError, APITimeoutError, BadRequestError, RateLimitError

from bot.services.openai_transcriber import OpenAITranscriber
from bot.services.transcriber import (
    TranscriptionPermanentError,
    TranscriptionTransientError,
)


@pytest.fixture
def audio_file(tmp_path: Path) -> Path:
    p = tmp_path / "v.ogg"
    p.write_bytes(b"x")
    return p


def _make_transcriber(*, side_effects: list) -> OpenAITranscriber:
    transcriber = OpenAITranscriber(api_key="sk-test", timeout=1.0)
    mock_create = AsyncMock(side_effect=side_effects)
    transcriber._client = MagicMock()
    transcriber._client.audio.transcriptions.create = mock_create
    return transcriber


async def test_success(audio_file: Path) -> None:
    t = _make_transcriber(side_effects=[SimpleNamespace(text="hello world", language="en")])
    result = await t.transcribe(audio_file, "audio/ogg", "v.ogg", model="whisper-1")
    assert result.text == "hello world"
    assert result.provider == "openai"
    assert result.language == "en"
    assert result.model == "whisper-1"


async def test_transient_then_success(audio_file: Path) -> None:
    err = APIConnectionError(request=MagicMock())
    t = _make_transcriber(side_effects=[err, SimpleNamespace(text="ok", language=None)])
    result = await t.transcribe(audio_file, "audio/ogg", "v.ogg", model="whisper-1")
    assert result.text == "ok"


async def test_transient_exhausted(audio_file: Path) -> None:
    err = APITimeoutError(request=MagicMock())
    t = _make_transcriber(side_effects=[err, err, err])
    with pytest.raises(TranscriptionTransientError):
        await t.transcribe(audio_file, "audio/ogg", "v.ogg", model="whisper-1")


async def test_rate_limit_is_transient(audio_file: Path) -> None:
    err = RateLimitError(message="rate", response=MagicMock(), body=None)
    t = _make_transcriber(side_effects=[err, err, err])
    with pytest.raises(TranscriptionTransientError):
        await t.transcribe(audio_file, "audio/ogg", "v.ogg", model="whisper-1")


async def test_bad_request_is_permanent_no_retry(audio_file: Path) -> None:
    err = BadRequestError(message="bad", response=MagicMock(), body=None)
    t = _make_transcriber(side_effects=[err])
    with pytest.raises(TranscriptionPermanentError):
        await t.transcribe(audio_file, "audio/ogg", "v.ogg", model="whisper-1")
    # Only one call — no retry on permanent.
    assert t._client.audio.transcriptions.create.call_count == 1


async def test_language_passthrough(audio_file: Path) -> None:
    t = _make_transcriber(side_effects=[SimpleNamespace(text="ok", language="ru")])
    await t.transcribe(audio_file, "audio/ogg", "v.ogg", model="whisper-1", language="ru")
    kwargs = t._client.audio.transcriptions.create.call_args.kwargs
    assert kwargs["language"] == "ru"
