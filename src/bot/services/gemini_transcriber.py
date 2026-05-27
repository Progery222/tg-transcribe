import asyncio
import base64
import time
from pathlib import Path

import httpx
import structlog
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

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
_PROMPT = "Transcribe this audio verbatim. Output only the transcript, no preamble."


class GeminiTranscriber:
    provider = "gemini"

    def __init__(self, api_key: str, *, timeout: float = 120.0) -> None:
        self._api_key = api_key
        self._client = httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def transcribe(
        self,
        audio_path: Path,
        mime: str,
        filename: str,
        *,
        model: str,
        language: str | None = None,
    ) -> TranscriptionResult:
        started = time.monotonic()
        url = f"{_BASE_URL}/{model}:generateContent"
        params = {"key": self._api_key}
        prompt = _PROMPT
        if language:
            prompt += f" The spoken language is {language}."
        raw = await asyncio.to_thread(audio_path.read_bytes)
        body = {
            "contents": [
                {
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": mime,
                                "data": base64.b64encode(raw).decode("ascii"),
                            }
                        },
                        {"text": prompt},
                    ]
                }
            ]
        }

        async def _call() -> TranscriptionResult:
            try:
                resp = await self._client.post(url, params=params, json=body)
            except (httpx.TimeoutException, httpx.NetworkError) as e:
                raise TranscriptionTransientError(str(e)) from e

            if resp.status_code in (429,) or 500 <= resp.status_code < 600:
                raise TranscriptionTransientError(
                    f"gemini http {resp.status_code}: {resp.text[:200]}"
                )
            if resp.status_code >= 400:
                raise TranscriptionPermanentError(
                    f"gemini http {resp.status_code}: {resp.text[:200]}"
                )

            try:
                payload = resp.json()
                parts = payload["candidates"][0]["content"]["parts"]
                text = "".join(p.get("text", "") for p in parts).strip()
            except (KeyError, IndexError, ValueError) as e:
                raise TranscriptionPermanentError(f"gemini response shape: {e}") from e

            return TranscriptionResult(
                text=text,
                model=model,
                provider=self.provider,
                duration_ms=int((time.monotonic() - started) * 1000),
                language=language,
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
        except RetryError as e:  # pragma: no cover
            raise TranscriptionTransientError(str(e)) from e

        raise TranscriptionTransientError("retry loop exited without result")
