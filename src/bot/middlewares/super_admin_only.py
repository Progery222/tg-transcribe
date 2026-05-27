from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.config import settings
from bot.texts.ru import t


class SuperAdminOnlyMiddleware(BaseMiddleware):
    """Rejects events whose ``from_user.id`` is not in ``settings.bot_admin_ids``."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        if user is None or user.id not in settings.bot_admin_ids:
            if isinstance(event, CallbackQuery):
                await event.answer(t("super_admin_only"), show_alert=True)
            elif isinstance(event, Message):
                await event.reply(t("super_admin_only"))
            return None
        return await handler(event, data)
