import base64

import httpx
import pytest
import respx

from bot.services.gemini_transcriber import GeminiTranscriber
from bot.services.transcriber import (
    TranscriptionPermanentError,
    TranscriptionTransientError,
)


def _ok_response(text: str = "hi"):
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


@respx.mock
async def test_success_returns_transcript() -> None:
    route = respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    ).mock(return_value=httpx.Response(200, json=_ok_response("hello")))

    t = GeminiTranscriber(api_key="key", timeout=5.0)
    try:
        result = await t.transcribe(b"x", "audio/ogg", "v.ogg", model="gemini-2.5-flash")
    finally:
        await t.aclose()
    assert result.text == "hello"
    assert result.provider == "gemini"
    # Body contains inline_data with base64 of b"x" == "eA=="
    body = route.calls.last.request.read().decode()
    assert base64.b64encode(b"x").decode() in body


@respx.mock
async def test_5xx_retried_then_succeeds() -> None:
    respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    ).mock(
        side_effect=[
            httpx.Response(503, text="busy"),
            httpx.Response(200, json=_ok_response("ok")),
        ]
    )
    t = GeminiTranscriber(api_key="k", timeout=5.0)
    try:
        result = await t.transcribe(b"x", "audio/ogg", "v.ogg", model="gemini-2.5-flash")
    finally:
        await t.aclose()
    assert result.text == "ok"


@respx.mock
async def test_429_is_transient() -> None:
    respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    ).mock(return_value=httpx.Response(429, text="slow down"))
    t = GeminiTranscriber(api_key="k", timeout=5.0)
    try:
        with pytest.raises(TranscriptionTransientError):
            await t.transcribe(b"x", "audio/ogg", "v.ogg", model="gemini-2.5-flash")
    finally:
        await t.aclose()


@respx.mock
async def test_400_is_permanent() -> None:
    respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    ).mock(return_value=httpx.Response(400, text="bad request"))
    t = GeminiTranscriber(api_key="k", timeout=5.0)
    try:
        with pytest.raises(TranscriptionPermanentError):
            await t.transcribe(b"x", "audio/ogg", "v.ogg", model="gemini-2.5-flash")
    finally:
        await t.aclose()


@respx.mock
async def test_malformed_response_is_permanent() -> None:
    respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    ).mock(return_value=httpx.Response(200, json={"candidates": []}))
    t = GeminiTranscriber(api_key="k", timeout=5.0)
    try:
        with pytest.raises(TranscriptionPermanentError):
            await t.transcribe(b"x", "audio/ogg", "v.ogg", model="gemini-2.5-flash")
    finally:
        await t.aclose()
