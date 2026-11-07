import asyncio
import tempfile
from collections.abc import Sequence
from pathlib import Path

import aiohttp
import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramEntityTooLarge, TelegramNetworkError
from aiogram.types import Message

log = structlog.get_logger(__name__)

# Pauses between getFile attempts (3 attempts in total).
FETCH_RETRY_DELAYS: tuple[float, ...] = (5.0, 15.0)


def extract_media_info(message: Message) -> tuple[str, str, int, str | None] | None:
    """Return ``(content_type, file_id, file_size, mime)`` for the first transcribable
    media in ``message``, or ``None`` if there is none.
    """
    if message.voice:
        v = message.voice
        return ("voice", v.file_id, v.file_size or 0, v.mime_type)
    if message.video_note:
        vn = message.video_note
        return ("video_note", vn.file_id, vn.file_size or 0, "video/mp4")
    if message.audio:
        a = message.audio
        return ("audio", a.file_id, a.file_size or 0, a.mime_type)
    if message.video:
        vid = message.video
        return ("video", vid.file_id, vid.file_size or 0, vid.mime_type)
    doc = getattr(message, "document", None)
    if doc is not None and _is_media_document(doc.mime_type, doc.file_name):
        return ("document", doc.file_id, doc.file_size or 0, doc.mime_type)
    return None


# Audio/video sent "as a file" (no compression) arrives as a document; clients do not
# always set a media MIME type, so fall back to the file extension.
_MEDIA_EXTENSIONS = frozenset(
    {
        ".3gp", ".aac", ".amr", ".avi", ".flac", ".m4a", ".m4v", ".mkv", ".mov", ".mp3",
        ".mp4", ".mpeg", ".mpg", ".oga", ".ogg", ".opus", ".wav", ".webm", ".wma", ".wmv",
    }
)  # fmt: skip


def _is_media_document(mime: str | None, file_name: str | None) -> bool:
    if mime and mime.split("/", 1)[0] in ("audio", "video"):
        return True
    return Path(file_name or "").suffix.lower() in _MEDIA_EXTENSIONS


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, TelegramEntityTooLarge):
        return False
    if isinstance(exc, TelegramNetworkError | aiohttp.ClientError | TimeoutError):
        return True
    return isinstance(exc, TelegramBadRequest) and "temporarily unavailable" in str(exc).lower()


async def fetch_file_path(
    bot: Bot,
    file_id: str,
    *,
    local_root: str = "",
    fetch_timeout: float = 600.0,
    retry_delays: Sequence[float] = FETCH_RETRY_DELAYS,
) -> tuple[Path, bool]:
    """Locate the Telegram file on disk, retrying transient failures.

    In local Bot API mode ``getFile`` already wrote the file to a shared volume —
    we just translate the path into the bot container's view and return it. The
    caller MUST NOT unlink that path: the file lives in the Bot API server volume.

    In production mode the file is streamed into a tempfile that we own. The
    caller is responsible for unlinking it.

    A slow download from Telegram's DC can outlive our HTTP request; the local
    Bot API server keeps downloading, so a repeated ``getFile`` usually picks up
    the finished file. Network errors and "temporarily unavailable" are retried
    after each delay in ``retry_delays``; the last error is re-raised.

    Returns ``(path, is_temp)`` — ``is_temp=True`` means caller should unlink.
    """
    for attempt, delay in enumerate([*retry_delays, None], start=1):
        try:
            return await _fetch_once(
                bot, file_id, local_root=local_root, fetch_timeout=fetch_timeout
            )
        except Exception as e:
            if delay is None or not _is_retryable(e):
                raise
            log.warning("file_fetch_retry", attempt=attempt, delay=delay, err=str(e))
            await asyncio.sleep(delay)
    raise AssertionError("unreachable")


async def _fetch_once(
    bot: Bot,
    file_id: str,
    *,
    local_root: str,
    fetch_timeout: float,
) -> tuple[Path, bool]:
    file = await bot.get_file(file_id, request_timeout=int(fetch_timeout))
    raw_path = file.file_path or ""

    if local_root and raw_path and (raw_path.startswith("/") or ":" in raw_path[:3]):
        api_root_marker = "/var/lib/telegram-bot-api"
        if api_root_marker in raw_path:
            relative = raw_path.split(api_root_marker, 1)[1].lstrip("/")
            candidate = Path(local_root) / relative
        else:
            candidate = Path(raw_path)
            if not candidate.is_absolute():
                candidate = Path(local_root) / raw_path
        if candidate.exists():
            return candidate, False

    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(raw_path).suffix or ".bin") as tmp:
        dst = Path(tmp.name)
    try:
        await bot.download_file(raw_path, destination=str(dst), timeout=int(fetch_timeout))
    except BaseException:
        # Sync on purpose: must also run when the task is being cancelled.
        dst.unlink(missing_ok=True)  # noqa: ASYNC240
        raise
    return dst, True
