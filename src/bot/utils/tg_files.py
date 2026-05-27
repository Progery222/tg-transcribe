from io import BytesIO

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


async def download_file(bot: Bot, file_id: str) -> bytes:
    """Download a Telegram file into memory. Caller must enforce size limit beforehand."""
    buf = BytesIO()
    await bot.download(file_id, destination=buf)
    return buf.getvalue()
