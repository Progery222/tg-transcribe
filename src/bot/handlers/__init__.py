from aiogram import Dispatcher

from bot.handlers import admin, admin_bot, callbacks, chat_member, start, voice
from bot.middlewares.chat_settings import ChatSettingsMiddleware
from bot.middlewares.super_admin_only import SuperAdminOnlyMiddleware


def register_handlers(dp: Dispatcher) -> None:
    chat_settings_mw = ChatSettingsMiddleware()
    dp.message.middleware(chat_settings_mw)
    dp.callback_query.middleware(chat_settings_mw)

    super_admin_mw = SuperAdminOnlyMiddleware()
    admin_bot.router.message.middleware(super_admin_mw)
    admin.router.message.middleware(super_admin_mw)
    admin.router.callback_query.middleware(super_admin_mw)
    callbacks.router.callback_query.middleware(super_admin_mw)

    # Order matters: start must run before voice / admin for /start TOKEN to win.
    dp.include_router(start.router)
    dp.include_router(admin_bot.router)
    dp.include_router(admin.router)
    dp.include_router(callbacks.router)
    dp.include_router(voice.router)
    dp.include_router(chat_member.router)
