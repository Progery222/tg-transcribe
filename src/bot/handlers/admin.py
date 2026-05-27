from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import Message

from bot.db.database import get_db
from bot.db.queries import upsert_chat_settings
from bot.keyboards.inline import model_picker_kb, model_picker_kb_global
from bot.texts.ru import t

router = Router(name="admin")


@router.message(Command("model"))
async def cmd_model(message: Message) -> None:
    if message.chat.type in {ChatType.GROUP.value, ChatType.SUPERGROUP.value}:
        await message.answer(t("model_picker_title"), reply_markup=model_picker_kb(message.chat.id))
        return
    await message.answer(t("model_picker_title_global"), reply_markup=model_picker_kb_global())


@router.message(
    Command("enable"), F.chat.type.in_({ChatType.GROUP.value, ChatType.SUPERGROUP.value})
)
async def cmd_enable(message: Message) -> None:
    conn = await get_db()
    await upsert_chat_settings(conn, message.chat.id, enabled=True)
    await message.answer(t("enabled"))


@router.message(
    Command("disable"), F.chat.type.in_({ChatType.GROUP.value, ChatType.SUPERGROUP.value})
)
async def cmd_disable(message: Message) -> None:
    conn = await get_db()
    await upsert_chat_settings(conn, message.chat.id, enabled=False)
    await message.answer(t("disabled"))


@router.message(Command("enable"))
@router.message(Command("disable"))
async def cmd_toggle_in_dm(message: Message) -> None:
    await message.answer(t("toggle_group_only"))
