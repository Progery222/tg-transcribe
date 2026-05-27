import time
from io import BytesIO

import structlog
from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    BadRequestError,
    RateLimitError,
)
from openai import APIError as OpenAIAPIError
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from bot.services.transcriber import (
    TranscriptionPermanentError,
    TranscriptionResult,
    TranscriptionTransientError,
)

log = structlog.get_logger(__name__)


class OpenAITranscriber:
    provider = "openai"

    def __init__(self, api_key: str, *, timeout: float = 120.0) -> None:
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout)

    async def transcribe(
        self,
        audio_bytes: bytes,
        mime: str,
        filename: str,
        *,
        model: str,
        language: str | None = None,
    ) -> TranscriptionResult:
        started = time.monotonic()

        async def _call() -> TranscriptionResult:
            kwargs: dict[str, object] = {
                "model": model,
                "file": (filename, BytesIO(audio_bytes), mime),
                "response_format": "json",
            }
            if language:
                kwargs["language"] = language
            try:
                resp = await self._client.audio.transcriptions.create(**kwargs)
            except (APIConnectionError, APITimeoutError, RateLimitError) as e:
                raise TranscriptionTransientError(str(e)) from e
            except BadRequestError as e:
                raise TranscriptionPermanentError(str(e)) from e
            except OpenAIAPIError as e:
                status = getattr(e, "status_code", None)
                if status is not None and 500 <= status < 600:
                    raise TranscriptionTransientError(str(e)) from e
                raise TranscriptionPermanentError(str(e)) from e

            text = (getattr(resp, "text", "") or "").strip()
            return TranscriptionResult(
                text=text,
                model=model,
                provider=self.provider,
                duration_ms=int((time.monotonic() - started) * 1000),
                language=getattr(resp, "language", None),
            )

        try:
            async for attempt in AsyncRetrying(
                retry=retry_if_exception_type(TranscriptionTransientError),
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=2, max=8),
                reraise=True,
            ):
                with attempt:
                    return await _call()
        except RetryError as e:  # pragma: no cover — reraise=True keeps original
            raise TranscriptionTransientError(str(e)) from e

        raise TranscriptionTransientError("retry loop exited without result")
