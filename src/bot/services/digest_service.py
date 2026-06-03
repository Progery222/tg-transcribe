import asyncio
import re
from datetime import UTC, datetime, timedelta, tzinfo

import aiosqlite
import structlog
from aiogram import Bot
from aiogram.exceptions import (
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
)
from aiogram.types import BufferedInputFile
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bot.config import settings
from bot.db.database import get_db
from bot.db.queries import fetch_digest_rows, list_active_chats
from bot.services.subscriber_service import list_dm_recipients
from bot.texts.ru import t

log = structlog.get_logger(__name__)

_SLUG_RE = re.compile(r"[^A-Za-z0-9_-]+")


def _slug(title: str | None, chat_id: int) -> str:
    base = (title or "").strip()
    s = _SLUG_RE.sub("_", base)[:48].strip("_")
    return s or f"chat_{chat_id}"


async def _build_file_for_chat(
    conn: aiosqlite.Connection,
    chat_id: int,
    title: str | None,
    start_utc: datetime,
    end_utc: datetime,
    tz: tzinfo,
) -> tuple[str, bytes] | None:
    rows = await fetch_digest_rows(conn, chat_id, start_utc, end_utc)
    if not rows:
        return None

    start_local = start_utc.astimezone(tz)
    end_local = end_utc.astimezone(tz)
    header = t(
        "digest_header",
        group=title or f"Chat {chat_id}",
        start=start_local.strftime("%Y-%m-%d %H:%M"),
        end=end_local.strftime("%Y-%m-%d %H:%M"),
        tz=settings.DIGEST_TZ,
    )
    lines: list[str] = [header, ""]
    for r in rows:
        ts = datetime.fromisoformat(r.ts_iso).astimezone(tz)
        speaker = f"@{r.username}" if r.username else (r.display_name or "—")
        lines.append(
            t(
                "digest_line",
                time=ts.strftime("%H:%M"),
                speaker=speaker,
                text=r.transcript_text,
            )
        )
    content = ("\n".join(lines) + "\n").encode("utf-8")
    fname = f"{_slug(title, chat_id)}_{end_local.strftime('%Y-%m-%d')}.txt"
    return fname, content


async def _send_digest(bot: Bot, start_utc: datetime, end_utc: datetime) -> int:
    tz = settings.digest_tz

    conn = await get_db()
    recipients = await list_dm_recipients(conn)
    if not recipients:
        log.info("digest_no_recipients")
        return 0

    chats = await list_active_chats(conn)
    files: list[tuple[str, bytes, str]] = []
    for c in chats:
        built = await _build_file_for_chat(conn, c.chat_id, c.title, start_utc, end_utc, tz)
        if built:
            fname, data = built
            files.append((fname, data, c.title or f"Chat {c.chat_id}"))

    if not files:
        log.info(
            "digest_empty_window",
            start=start_utc.isoformat(),
            end=end_utc.isoformat(),
        )
        return 0

    date_str = end_utc.astimezone(tz).strftime("%Y-%m-%d")
    sent_total = 0
    delay = settings.DM_SEND_DELAY_MS / 1000
    for uid in recipients:
        for fname, data, title in files:
            sent = await _send_doc(bot, uid, fname, data, title, date_str)
            if sent:
                sent_total += 1
            else:
                break  # if user blocked/forbid → stop sending more files to them
            await asyncio.sleep(delay)
    log.info("digest_sent", files=sent_total, recipients=len(recipients))
    return sent_total


_SEND_DOC_MAX_ATTEMPTS = 4


async def _send_doc(
    bot: Bot, user_id: int, fname: str, data: bytes, title: str, date_str: str
) -> bool:
    """Deliver a single digest file to one user, retrying transient failures.

    Retries on Telegram-side flood limits (``TelegramRetryAfter``) and on
    transport-level glitches (``TelegramNetworkError`` — covers Docker DNS
    flakes and connection resets). ``TelegramForbiddenError`` is terminal —
    the user has blocked the bot, no point retrying.
    """
    caption = t("digest_caption", group=title, date=date_str)
    last_err: Exception | None = None
    for attempt in range(1, _SEND_DOC_MAX_ATTEMPTS + 1):
        try:
            doc = BufferedInputFile(data, filename=fname)
            await bot.send_document(user_id, doc, caption=caption)
            return True
        except TelegramForbiddenError:
            log.info("digest_dm_blocked", user_id=user_id)
            return False
        except TelegramRetryAfter as e:
            last_err = e
            log.warning("digest_flood", retry_after=e.retry_after, user_id=user_id, attempt=attempt)
            await asyncio.sleep(e.retry_after + 0.5)
        except TelegramNetworkError as e:
            last_err = e
            backoff = min(2 ** (attempt - 1), 30)
            log.warning(
                "digest_network_retry",
                attempt=attempt,
                backoff=backoff,
                user_id=user_id,
                file=fname,
                err=str(e),
            )
            await asyncio.sleep(backoff)
        except Exception:
            log.exception("digest_send_failed", user_id=user_id, file=fname)
            return False

    log.error(
        "digest_send_exhausted",
        user_id=user_id,
        file=fname,
        attempts=_SEND_DOC_MAX_ATTEMPTS,
        last_err=str(last_err) if last_err else None,
    )
    return False


def _manual_window(now_local: datetime) -> tuple[datetime, datetime]:
    """Window for a manual /digest_now: from the most recent scheduled digest
    (the last DIGEST_HOUR:DIGEST_MINUTE fire) up to ``now`` — i.e. the slice of
    the day the automatic morning digest hasn't covered yet. Returns UTC bounds.
    """
    last_fire = now_local.replace(
        hour=settings.DIGEST_HOUR,
        minute=settings.DIGEST_MINUTE,
        second=0,
        microsecond=0,
    )
    if last_fire > now_local:
        last_fire -= timedelta(days=1)
    return last_fire.astimezone(UTC), now_local.astimezone(UTC)


async def run_digest_now(bot: Bot) -> int:
    """Manual trigger. Covers everything since the most recent scheduled digest
    up to now — the slice of the current day not yet sent by the automatic 10:00
    digest (see :func:`_manual_window`)."""
    start_utc, end_utc = _manual_window(datetime.now(settings.digest_tz))
    return await _send_digest(bot, start_utc, end_utc)


async def _send_digest_scheduled(bot: Bot) -> None:
    tz = settings.digest_tz
    fire_local = datetime.now(tz).replace(
        hour=settings.DIGEST_HOUR,
        minute=settings.DIGEST_MINUTE,
        second=0,
        microsecond=0,
    )
    end_utc = fire_local.astimezone(UTC)
    start_utc = end_utc - timedelta(hours=settings.DIGEST_WINDOW_HOURS)
    try:
        await _send_digest(bot, start_utc, end_utc)
    except Exception:
        # Swallow the exception so APScheduler doesn't escalate it; the next day's
        # fire will run independently. Operator can inspect this structured log.
        log.exception(
            "digest_scheduled_failed",
            scheduled_for_local=fire_local.isoformat(),
            tz=settings.DIGEST_TZ,
        )


def start_scheduler(bot: Bot) -> AsyncIOScheduler:
    sched = AsyncIOScheduler(timezone=settings.digest_tz)
    sched.add_job(
        _send_digest_scheduled,
        kwargs={"bot": bot},
        trigger=CronTrigger(
            hour=settings.DIGEST_HOUR,
            minute=settings.DIGEST_MINUTE,
            timezone=settings.digest_tz,
        ),
        id="daily_digest",
        misfire_grace_time=3600,
        coalesce=True,
        max_instances=1,
    )
    sched.start()
    log.info(
        "scheduler_started",
        hour=settings.DIGEST_HOUR,
        minute=settings.DIGEST_MINUTE,
        tz=settings.DIGEST_TZ,
    )
    return sched


def stop_scheduler(scheduler: AsyncIOScheduler | None) -> None:
    if scheduler is not None:
        scheduler.shutdown(wait=False)
