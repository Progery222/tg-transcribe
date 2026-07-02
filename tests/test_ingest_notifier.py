import httpx
import pytest
import respx

from bot.services import ingest_notifier
from bot.services.ingest_notifier import send_digest_ingest

URL = "https://supasale.test/api/tg/ingest/atomleaders"


@pytest.fixture
async def ingest_settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(ingest_notifier.settings, "INGEST_ENABLED", True)
    monkeypatch.setattr(ingest_notifier.settings, "INGEST_URL", URL)
    monkeypatch.setattr(ingest_notifier.settings, "INGEST_CHAT_IDS", "")
    monkeypatch.setattr(ingest_notifier, "_BACKOFF_S", (0, 0, 0))
    yield
    await ingest_notifier.aclose_ingest()


@respx.mock
async def test_posts_raw_body_with_plain_text_header(ingest_settings) -> None:
    route = respx.post(URL).mock(return_value=httpx.Response(200))
    data = "Дайджест группы Alpha\n\n10:23 @alice: привет\n".encode()

    ok = await send_digest_ingest(-100, data)

    assert ok is True
    assert route.call_count == 1
    req = route.calls.last.request
    assert req.content == data
    assert req.headers["content-type"] == "text/plain; charset=utf-8"


@respx.mock
async def test_retries_5xx_then_succeeds(ingest_settings) -> None:
    route = respx.post(URL).mock(
        side_effect=[httpx.Response(503, text="busy"), httpx.Response(200)]
    )
    ok = await send_digest_ingest(-100, b"data")
    assert ok is True
    assert route.call_count == 2


@respx.mock
async def test_retries_network_error_then_succeeds(ingest_settings) -> None:
    route = respx.post(URL).mock(
        side_effect=[httpx.ConnectError("boom"), httpx.Response(200)]
    )
    ok = await send_digest_ingest(-100, b"data")
    assert ok is True
    assert route.call_count == 2


@respx.mock
async def test_retries_remote_protocol_error_then_succeeds(ingest_settings) -> None:
    route = respx.post(URL).mock(
        side_effect=[
            httpx.RemoteProtocolError("Server disconnected"),
            httpx.Response(200),
        ]
    )
    ok = await send_digest_ingest(-100, b"data")
    assert ok is True
    assert route.call_count == 2


@respx.mock
async def test_persistent_5xx_stops_after_four_attempts(ingest_settings) -> None:
    route = respx.post(URL).mock(return_value=httpx.Response(503, text="down"))
    ok = await send_digest_ingest(-100, b"data")
    assert ok is False
    assert route.call_count == 4


@respx.mock
async def test_no_retry_on_4xx(ingest_settings) -> None:
    route = respx.post(URL).mock(return_value=httpx.Response(400, text="bad"))
    ok = await send_digest_ingest(-100, b"data")
    assert ok is False
    assert route.call_count == 1


@respx.mock
async def test_never_raises_when_attempts_exhausted(ingest_settings) -> None:
    route = respx.post(URL).mock(side_effect=httpx.ConnectError("down"))
    ok = await send_digest_ingest(-100, b"data")
    assert ok is False
    assert route.call_count == 4


@respx.mock
async def test_never_raises_on_malformed_chat_ids(
    ingest_settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Bypasses the startup validator; the call-time parse must hit the outer guard.
    monkeypatch.setattr(ingest_notifier.settings, "INGEST_CHAT_IDS", "-100;abc")
    route = respx.post(URL).mock(return_value=httpx.Response(200))
    ok = await send_digest_ingest(-100, b"data")
    assert ok is False
    assert route.call_count == 0


def test_malformed_chat_ids_rejected_at_startup() -> None:
    from pydantic import ValidationError

    from bot.config import Settings

    with pytest.raises(ValidationError, match="INGEST_CHAT_IDS"):
        Settings(INGEST_CHAT_IDS="-100;abc")


@respx.mock
async def test_noop_when_disabled(ingest_settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ingest_notifier.settings, "INGEST_ENABLED", False)
    route = respx.post(URL).mock(return_value=httpx.Response(200))
    ok = await send_digest_ingest(-100, b"data")
    assert ok is False
    assert route.call_count == 0


@respx.mock
async def test_noop_when_url_empty(ingest_settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ingest_notifier.settings, "INGEST_URL", "")
    route = respx.post(URL).mock(return_value=httpx.Response(200))
    ok = await send_digest_ingest(-100, b"data")
    assert ok is False
    assert route.call_count == 0


@respx.mock
async def test_chat_filter(ingest_settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ingest_notifier.settings, "INGEST_CHAT_IDS", "-100, -200")
    route = respx.post(URL).mock(return_value=httpx.Response(200))

    assert await send_digest_ingest(-300, b"data") is False
    assert route.call_count == 0

    assert await send_digest_ingest(-100, b"data") is True
    assert route.call_count == 1
