import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllChatAdministrators,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeChat,
)

log = structlog.get_logger(__name__)


_PUBLIC_DM = [
    BotCommand(command="start", description="Приветствие и статус доступа"),
    BotCommand(command="help", description="Справка"),
]

_SUPER_ADMIN_DM = [
    BotCommand(command="invite", description="Одноразовая ссылка для подписчика"),
    BotCommand(command="grant", description="Добавить подписчика по user_id"),
    BotCommand(command="revoke", description="Отозвать доступ"),
    BotCommand(command="subscribers", description="Список активных подписчиков"),
    BotCommand(command="chats", description="Группы под мониторингом"),
    BotCommand(command="digest_now", description="Собрать сводку прямо сейчас"),
    BotCommand(command="help", description="Справка"),
]

_GROUP_ADMIN = [
    BotCommand(command="model", description="Выбрать модель распознавания"),
    BotCommand(command="enable", description="Включить мониторинг группы"),
    BotCommand(command="disable", description="Выключить мониторинг группы"),
]


async def setup_bot_commands(bot: Bot, super_admin_ids: list[int]) -> None:
    """Register the bot's command menu in three scopes.

    1. Public DMs — start/help only.
    2. Each super-admin's DM — full owner toolbox.
    3. Any group's admins — model/enable/disable.
    """
    await bot.set_my_commands(_PUBLIC_DM, scope=BotCommandScopeAllPrivateChats())
    await bot.set_my_commands(_GROUP_ADMIN, scope=BotCommandScopeAllChatAdministrators())

    for admin_id in super_admin_ids:
        try:
            await bot.set_my_commands(
                _SUPER_ADMIN_DM, scope=BotCommandScopeChat(chat_id=admin_id)
            )
        except TelegramAPIError as e:
            log.warning("set_commands_failed_for_admin", admin_id=admin_id, err=str(e))

    log.info(
        "bot_commands_registered",
        public=len(_PUBLIC_DM),
        group_admin=len(_GROUP_ADMIN),
        super_admins=len(super_admin_ids),
    )
