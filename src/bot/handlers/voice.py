import time
from datetime import UTC
from zoneinfo import ZoneInfo

import structlog
from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.types import Message, User

from bot.config import settings
from bot.db.database import get_db
from bot.db.queries import ChatSettings, TranscriptionRow, log_transcription
from bot.services.audio_pipeline import FfmpegError, prepare_payload
from bot.services.dm_sender import notify_super_admins, send_transcript_dm
from bot.services.subscriber_service import list_dm_recipients
from bot.services.transcriber import (
    Transcriber,
    TranscriptionPermanentError,
    TranscriptionTransientError,
)
from bot.services.worker_pool import with_slot
from bot.texts.ru import t
from bot.utils.text_split import split_for_telegram
from bot.utils.tg_files import download_file, extract_media_info

log = structlog.get_logger(__name__)

router = Router(name="voice")


def _speaker_label(user: User | None) -> str:
    if user is None:
        return "—"
    if user.username:
        return f"@{user.username}"
    name = " ".join(p for p in (user.first_name, user.last_name) if p)
    if name:
        return f"{name} (no username)"
    return f"User {user.id}"


def _display_name(user: User | None) -> str | None:
    if user is None:
        return None
    parts = [p for p in (user.first_name, user.last_name) if p]
    return " ".join(parts) if parts else None


@router.message(
    (F.voice | F.video_note | F.audio | F.video)
    & F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP})
)
async def on_media(
    message: Message,
    bot: Bot,
    chat_settings: ChatSettings | None = None,
    transcribers: dict[str, Transcriber] | None = None,
) -> None:
    if chat_settings is None or transcribers is None:
        log.warning("voice_missing_deps", chat_id=message.chat.id)
        return

    if not chat_settings.enabled:
        return

    media = extract_media_info(message)
    if media is None:
        return
    content_type, file_id, file_size, mime = media

    audio_seconds: int | None = None
    if message.voice:
        audio_seconds = message.voice.duration
    elif message.video_note:
        audio_seconds = message.video_note.duration
    elif message.audio:
        audio_seconds = message.audio.duration
    elif message.video:
        audio_seconds = message.video.duration

    user = message.from_user
    msg_created_at = message.date.astimezone(UTC).isoformat() if message.date else None
    chat_title = message.chat.title or f"Chat {message.chat.id}"

    base_log_kwargs = {
        "username": user.username if user else None,
        "display_name": _display_name(user),
        "msg_created_at": msg_created_at,
    }

    if file_size and file_size > settings.MAX_FILE_BYTES:
        await notify_super_admins(
            bot,
            t("transcript_failed_admin", chat_title=chat_title, error="file_too_big"),
        )
        await _log(
            message,
            content_type,
            chat_settings,
            success=False,
            error_code="file_too_big",
            latency_ms=0,
            audio_seconds=audio_seconds,
            transcript_text=None,
            **base_log_kwargs,
        )
        return

    transcriber = transcribers.get(chat_settings.provider)
    if transcriber is None:
        log.error("provider_not_configured", provider=chat_settings.provider)
        await notify_super_admins(
            bot,
            t(
                "transcript_failed_admin",
                chat_title=chat_title,
                error=f"provider {chat_settings.provider} not configured",
            ),
        )
        return

    started = time.monotonic()
    try:
        raw = await download_file(bot, file_id)
    except TelegramAPIError as e:
        log.warning("download_failed", err=str(e), file_id=file_id)
        await notify_super_admins(
            bot,
            t("transcript_failed_admin", chat_title=chat_title, error=f"download: {e}"),
        )
        await _log(
            message,
            content_type,
            chat_settings,
            success=False,
            error_code="download_failed",
            latency_ms=int((time.monotonic() - started) * 1000),
            audio_seconds=audio_seconds,
            transcript_text=None,
            **base_log_kwargs,
        )
        return

    try:
        payload = await prepare_payload(content_type, raw, mime)
    except FfmpegError as e:
        log.warning("ffmpeg_failed", err=str(e), content_type=content_type)
        await notify_super_admins(
            bot,
            t("transcript_failed_admin", chat_title=chat_title, error=f"ffmpeg: {e}"),
        )
        await _log(
            message,
            content_type,
            chat_settings,
            success=False,
            error_code="ffmpeg_failed",
            latency_ms=int((time.monotonic() - started) * 1000),
            audio_seconds=audio_seconds,
            transcript_text=None,
            **base_log_kwargs,
        )
        return

    try:
        result = await with_slot(
            lambda: transcriber.transcribe(
                payload.data,
                payload.mime,
                payload.filename,
                model=chat_settings.model,
                language=chat_settings.language,
            )
        )
    except TranscriptionTransientError as e:
        log.warning(
            "transcribe_transient",
            provider=chat_settings.provider,
            model=chat_settings.model,
            err=str(e),
        )
        await notify_super_admins(
            bot, t("transcript_failed_admin", chat_title=chat_title, error=f"transient: {e}")
        )
        await _log(
            message,
            content_type,
            chat_settings,
            success=False,
            error_code="transient",
            latency_ms=int((time.monotonic() - started) * 1000),
            audio_seconds=audio_seconds,
            transcript_text=None,
            **base_log_kwargs,
        )
        return
    except TranscriptionPermanentError as e:
        log.info(
            "transcribe_permanent",
            provider=chat_settings.provider,
            model=chat_settings.model,
            err=str(e),
        )
        await notify_super_admins(
            bot, t("transcript_failed_admin", chat_title=chat_title, error=f"permanent: {e}")
        )
        await _log(
            message,
            content_type,
            chat_settings,
            success=False,
            error_code="permanent",
            latency_ms=int((time.monotonic() - started) * 1000),
            audio_seconds=audio_seconds,
            transcript_text=None,
            **base_log_kwargs,
        )
        return
    except Exception as e:
        log.exception("transcribe_crash")
        await notify_super_admins(
            bot, t("transcript_failed_admin", chat_title=chat_title, error=f"crash: {e}")
        )
        await _log(
            message,
            content_type,
            chat_settings,
            success=False,
            error_code="crash",
            latency_ms=int((time.monotonic() - started) * 1000),
            audio_seconds=audio_seconds,
            transcript_text=None,
            **base_log_kwargs,
        )
        return

    text = result.text.strip()
    await _log(
        message,
        content_type,
        chat_settings,
        success=bool(text),
        error_code=None if text else "empty",
        latency_ms=int((time.monotonic() - started) * 1000),
        audio_seconds=audio_seconds,
        transcript_text=text or None,
        **base_log_kwargs,
    )

    if not text:
        return

    conn = await get_db()
    recipients = await list_dm_recipients(conn)
    if not recipients:
        log.info("no_dm_recipients", chat_id=message.chat.id)
        return

    tz = ZoneInfo(settings.DIGEST_TZ)
    time_local = message.date.astimezone(tz).strftime("%H:%M") if message.date else "—"
    formatted = t(
        "transcript_dm",
        group_title=chat_title,
        speaker=_speaker_label(user),
        time_msk=time_local,
        text=text,
    )
    chunks = split_for_telegram(formatted)
    sent_total = 0
    for chunk in chunks:
        sent_total += await send_transcript_dm(bot, recipients, chunk)
    log.info(
        "transcript_dm_fanout",
        chat_id=message.chat.id,
        recipients=len(recipients),
        chunks=len(chunks),
        sent=sent_total,
    )


async def _log(
    message: Message,
    content_type: str,
    cs: ChatSettings,
    *,
    success: bool,
    error_code: str | None,
    latency_ms: int,
    audio_seconds: int | None,
    transcript_text: str | None,
    username: str | None,
    display_name: str | None,
    msg_created_at: str | None,
) -> None:
    try:
        conn = await get_db()
        await log_transcription(
            conn,
            TranscriptionRow(
                chat_id=message.chat.id,
                user_id=message.from_user.id if message.from_user else None,
                message_id=message.message_id,
                content_type=content_type,
                provider=cs.provider,
                model=cs.model,
                success=success,
                error_code=error_code,
                audio_seconds=audio_seconds,
                latency_ms=latency_ms,
                transcript_text=transcript_text,
                username=username,
                display_name=display_name,
                msg_created_at=msg_created_at,
            ),
        )
    except Exception:
        log.exception("log_transcription_failed")
