import asyncio

import httpx
import structlog

from bot.config import settings

log = structlog.get_logger(__name__)

_TIMEOUT = 30.0
_MAX_ATTEMPTS = 4
_BACKOFF_S = (1.0, 5.0, 15.0)  # sleep before attempts 2..4

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=_TIMEOUT)
    return _client


async def send_digest_ingest(chat_id: int, data: bytes) -> bool:
    """POST a digest file to the external ingest endpoint. Never raises.

    No-op (returns False) when INGEST_ENABLED is off, INGEST_URL is empty,
    or INGEST_CHAT_IDS is set and chat_id is not listed.
    """
    try:
        if not (settings.INGEST_ENABLED and settings.INGEST_URL):
            return False
        ids = settings.ingest_chat_ids
        if ids and chat_id not in ids:
            return False

        headers = {"Content-Type": "text/plain; charset=utf-8"}
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                resp = await _get_client().post(
                    settings.INGEST_URL, content=data, headers=headers
                )
            except httpx.TransportError as e:
                if attempt < _MAX_ATTEMPTS:
                    await asyncio.sleep(_BACKOFF_S[attempt - 1])
                    continue
                log.warning("ingest_failed", chat_id=chat_id, err=str(e), attempts=attempt)
                return False
            if resp.is_success:
                log.info(
                    "ingest_sent", chat_id=chat_id, status=resp.status_code, bytes=len(data)
                )
                return True
            if 500 <= resp.status_code < 600 and attempt < _MAX_ATTEMPTS:
                await asyncio.sleep(_BACKOFF_S[attempt - 1])
                continue
            log.warning(
                "ingest_http_error",
                chat_id=chat_id,
                status=resp.status_code,
                body=resp.text[:200],
            )
            return False
    except Exception:
        log.exception("ingest_failed", chat_id=chat_id)
    return False


async def aclose_ingest() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
