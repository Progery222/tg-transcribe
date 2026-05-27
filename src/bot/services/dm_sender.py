import asyncio
from collections.abc import Iterable

import structlog
from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)

from bot.config import settings

log = structlog.get_logger(__name__)


async def send_transcript_dm(bot: Bot, recipients: Iterable[int], text: str) -> int:
    """Sequentially DM ``text`` to each recipient.

    Telegram global bot rate limit is ~30 msg/sec; sequential + small delay keeps us
    well under it and lets per-recipient errors (blocked bot, deleted account) be
    handled individually. Returns the number of successful sends.
    """
    delay = settings.DM_SEND_DELAY_MS / 1000
    sent = 0
    for uid in recipients:
        ok = await _send_one(bot, uid, text)
        if ok:
            sent += 1
        await asyncio.sleep(delay)
    return sent


async def _send_one(bot: Bot, user_id: int, text: str) -> bool:
    try:
        await bot.send_message(user_id, text)
        return True
    except TelegramRetryAfter as e:
        log.warning("dm_flood", retry_after=e.retry_after, user_id=user_id)
        await asyncio.sleep(e.retry_after + 0.5)
        try:
            await bot.send_message(user_id, text)
            return True
        except Exception:
            log.exception("dm_retry_failed", user_id=user_id)
            return False
    except TelegramForbiddenError:
        # User blocked the bot or never initiated a chat — common, not an error.
        log.info("dm_blocked", user_id=user_id)
        return False
    except TelegramBadRequest as e:
        log.warning("dm_bad_request", user_id=user_id, err=str(e))
        return False
    except Exception:
        log.exception("dm_failed", user_id=user_id)
        return False


async def notify_super_admins(bot: Bot, text: str) -> None:
    for uid in settings.bot_admin_ids:
        await _send_one(bot, uid, text)
