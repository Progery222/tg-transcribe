from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message, User

from bot.db.database import get_db
from bot.services import subscriber_service as ss
from bot.texts.ru import t

router = Router(name="start")


def _display_name(user: User | None) -> str | None:
    if user is None:
        return None
    parts = [p for p in (user.first_name, user.last_name) if p]
    return " ".join(parts) if parts else None


@router.message(CommandStart(deep_link=True), F.chat.type == ChatType.PRIVATE)
async def cmd_start_with_token(message: Message, command: CommandObject) -> None:
    token = (command.args or "").strip()
    if not token:
        await _greet(message)
        return
    if message.from_user is None:
        return
    conn = await get_db()
    result = await ss.consume_invite(
        conn,
        token,
        user_id=message.from_user.id,
        username=message.from_user.username,
        display_name=_display_name(message.from_user),
    )
    if result == "ok":
        await message.answer(t("invite_used"))
    else:
        await message.answer(t("invite_invalid_or_expired"))


@router.message(CommandStart(), F.chat.type == ChatType.PRIVATE)
async def cmd_start_dm(message: Message) -> None:
    await _greet(message)


@router.message(CommandStart())
async def cmd_start_group(message: Message) -> None:
    await message.answer(t("start_group"))


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    if message.from_user and ss.is_super_admin(message.from_user.id):
        await message.answer(t("help_super_admin"))
    else:
        await message.answer(t("help"))


async def _greet(message: Message) -> None:
    if message.from_user is None:
        return
    uid = message.from_user.id
    if ss.is_super_admin(uid):
        await message.answer(t("start_super_admin"))
        return
    conn = await get_db()
    if await ss.is_subscriber(conn, uid):
        await message.answer(t("start_subscriber"))
    else:
        await message.answer(t("start_outsider"))
