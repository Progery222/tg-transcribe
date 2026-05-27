from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import Message

from bot.db.database import get_db
from bot.db.queries import upsert_chat_settings
from bot.keyboards.inline import model_picker_kb
from bot.texts.ru import t

router = Router(name="admin")
# /model /enable /disable apply to monitored groups only — never to DMs with the bot.
router.message.filter(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))


@router.message(Command("model"))
async def cmd_model(message: Message) -> None:
    await message.answer(t("model_picker_title"), reply_markup=model_picker_kb())


@router.message(Command("enable"))
async def cmd_enable(message: Message) -> None:
    conn = await get_db()
    await upsert_chat_settings(conn, message.chat.id, enabled=True)
    await message.answer(t("enabled"))


@router.message(Command("disable"))
async def cmd_disable(message: Message) -> None:
    conn = await get_db()
    await upsert_chat_settings(conn, message.chat.id, enabled=False)
    await message.answer(t("disabled"))
