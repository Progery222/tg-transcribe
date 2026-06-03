import tempfile
from pathlib import Path

from aiogram import Bot
from aiogram.types import Message


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
    return None


async def fetch_file_path(
    bot: Bot,
    file_id: str,
    *,
    local_root: str = "",
    fetch_timeout: float = 600.0,
) -> tuple[Path, bool]:
    """Locate the Telegram file on disk.

    In local Bot API mode ``getFile`` already wrote the file to a shared volume —
    we just translate the path into the bot container's view and return it. The
    caller MUST NOT unlink that path: the file lives in the Bot API server volume.

    In production mode the file is streamed into a tempfile that we own. The
    caller is responsible for unlinking it.

    Returns ``(path, is_temp)`` — ``is_temp=True`` means caller should unlink.
    """
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
    await bot.download_file(raw_path, destination=str(dst), timeout=int(fetch_timeout))
    return dst, True
