from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    model: str
    provider: str
    duration_ms: int
    language: str | None


class TranscriptionError(Exception):
    """Base class for transcription failures."""


class TranscriptionPermanentError(TranscriptionError):
    """Non-retryable failure: bad audio, content policy, unsupported model, etc."""


class TranscriptionTransientError(TranscriptionError):
    """Retryable failure: 5xx, timeout, rate limit."""


@runtime_checkable
class Transcriber(Protocol):
    provider: str

    async def transcribe(
        self,
        audio_path: Path,
        mime: str,
        filename: str,
        *,
        model: str,
        language: str | None = None,
    ) -> TranscriptionResult: ...


@dataclass(frozen=True)
class ModelOption:
    provider: str
    model: str
    label: str


SUPPORTED_MODELS: list[ModelOption] = [
    ModelOption("openai", "gpt-4o-mini-transcribe", "OpenAI · 4o mini (fast/cheap)"),
    ModelOption("openai", "gpt-4o-transcribe", "OpenAI · 4o (accurate)"),
    ModelOption("openai", "whisper-1", "OpenAI · whisper-1 (legacy)"),
    ModelOption("gemini", "gemini-2.5-flash", "Gemini 2.5 Flash"),
    ModelOption("gemini", "gemini-2.5-pro", "Gemini 2.5 Pro"),
]


def find_model_option(provider: str, model: str) -> ModelOption | None:
    for opt in SUPPORTED_MODELS:
        if opt.provider == provider and opt.model == model:
            return opt
    return None
