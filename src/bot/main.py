import structlog
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramNetworkError
from aiogram.fsm.storage.memory import MemoryStorage
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from bot.config import settings
from bot.db.database import close_db, init_db
from bot.handlers import register_handlers
from bot.logging_setup import configure_logging
from bot.services.commands_menu import setup_bot_commands
from bot.services.digest_service import start_scheduler, stop_scheduler
from bot.services.gemini_transcriber import GeminiTranscriber
from bot.services.ingest_notifier import aclose_ingest
from bot.services.openai_transcriber import OpenAITranscriber
from bot.services.transcriber import Transcriber

log = structlog.get_logger(__name__)


def _build_transcribers() -> dict[str, Transcriber]:
    out: dict[str, Transcriber] = {}
    if settings.OPENAI_API_KEY:
        out["openai"] = OpenAITranscriber(
            api_key=settings.OPENAI_API_KEY,
            timeout=settings.OPENAI_TIMEOUT,
            base_url=settings.OPENAI_BASE_URL,
        )
    if settings.GEMINI_API_KEY:
        out["gemini"] = GeminiTranscriber(
            api_key=settings.GEMINI_API_KEY,
            timeout=settings.GEMINI_TIMEOUT,
        )
    return out


async def run() -> None:
    configure_logging(settings.LOG_LEVEL, settings.LOG_JSON)
    await init_db()

    transcribers = _build_transcribers()
    log.info("transcribers_loaded", providers=list(transcribers.keys()))

    session: AiohttpSession | None = None
    if settings.TELEGRAM_BOT_API_URL:
        api_server = TelegramAPIServer.from_base(settings.TELEGRAM_BOT_API_URL, is_local=True)
        session = AiohttpSession(api=api_server)
        log.info("bot_api_local_mode", url=settings.TELEGRAM_BOT_API_URL)

    bot = Bot(
        token=settings.BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Docker DNS sometimes flakes for the first few seconds after a container restart;
    # retry get_me with exponential backoff so the container doesn't enter crash-loop.
    async for attempt in AsyncRetrying(
        retry=retry_if_exception_type(TelegramNetworkError),
        stop=stop_after_attempt(6),
        wait=wait_exponential(multiplier=1, min=2, max=15),
        reraise=True,
    ):
        with attempt:
            me = await bot.get_me()

    if not getattr(me, "can_read_all_group_messages", False):
        log.warning(
            "privacy_mode_enabled",
            hint=(
                "Disable Group Privacy via @BotFather → /mybots → bot → "
                "Bot Settings → Group Privacy → Turn off. "
                "Otherwise the bot won't see voice/video_note messages in groups."
            ),
        )

    dp = Dispatcher(storage=MemoryStorage())
    dp["transcribers"] = transcribers
    register_handlers(dp)

    if not settings.bot_admin_ids:
        log.warning(
            "no_bot_admins_configured",
            hint="Set BOT_ADMIN_IDS in .env to your Telegram user_id(s) to use admin commands.",
        )

    scheduler = start_scheduler(bot)

    await setup_bot_commands(bot, settings.bot_admin_ids)

    log.info("bot_started", mode=settings.BOT_MODE, username=me.username)

    try:
        if settings.BOT_MODE == "polling":
            await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        else:
            log.warning("webhook_mode_not_implemented")
    finally:
        stop_scheduler(scheduler)
        gemini = transcribers.get("gemini")
        if gemini is not None and hasattr(gemini, "aclose"):
            await gemini.aclose()  # type: ignore[union-attr]
        await aclose_ingest()
        await bot.session.close()
        await close_db()
