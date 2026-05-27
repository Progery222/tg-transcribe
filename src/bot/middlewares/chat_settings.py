from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from aiogram import BaseMiddleware
from aiogram.enums import ChatType
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.config import settings
from bot.db.database import get_db
from bot.db.queries import (
    ChatSettings,
    get_chat_settings,
    touch_chat,
    upsert_chat_settings,
)

log = structlog.get_logger(__name__)


class ChatSettingsMiddleware(BaseMiddleware):
    """Loads :class:`ChatSettings` for the event's chat into ``data['chat_settings']``.

    Auto-creates a default row on first encounter so downstream code never sees None.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        chat_id: int | None = None
        if isinstance(event, Message) and event.chat:
            chat_id = event.chat.id
        elif isinstance(event, CallbackQuery) and event.message and event.message.chat:
            chat_id = event.message.chat.id

        if chat_id is not None:
            try:
                conn = await get_db()
                cs = await get_chat_settings(conn, chat_id)
                if cs is None:
                    await upsert_chat_settings(
                        conn,
                        chat_id,
                        provider=settings.DEFAULT_PROVIDER,
                        model=settings.DEFAULT_MODEL,
                        enabled=True,
                    )
                    cs = ChatSettings(
                        chat_id=chat_id,
                        provider=settings.DEFAULT_PROVIDER,
                        model=settings.DEFAULT_MODEL,
                        language=None,
                        enabled=True,
                    )
                data["chat_settings"] = cs

                # Self-heal `chats` table for groups: covers installs that had the
                # bot before `my_chat_member` handler shipped. ``touch_chat`` updates
                # title/last_seen_at without overriding ``active`` (so a late message
                # arriving after a kick can't flip the row back to active=1).
                if isinstance(event, Message) and event.chat.type in {
                    ChatType.GROUP,
                    ChatType.SUPERGROUP,
                }:
                    await touch_chat(conn, event.chat.id, event.chat.title)
            except Exception:
                log.exception(
                    "chat_settings_load_failed",
                    chat_id=chat_id,
                    consequence="downstream handlers will receive chat_settings=None",
                )
        return await handler(event, data)
