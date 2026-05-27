from aiogram import Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import Message

from bot.db.database import get_db
from bot.db.queries import list_active_chats, upsert_chat_settings
from bot.keyboards.inline import groups_picker_kb, model_picker_kb
from bot.texts.ru import t

router = Router(name="admin")


def _is_group(message: Message) -> bool:
    return message.chat.type in {ChatType.GROUP.value, ChatType.SUPERGROUP.value}


@router.message(Command("model"))
async def cmd_model(message: Message) -> None:
    if _is_group(message):
        await message.answer(t("model_picker_title"), reply_markup=model_picker_kb(message.chat.id))
        return
    conn = await get_db()
    chats = await list_active_chats(conn)
    if not chats:
        await message.answer(t("chats_empty"))
        return
    if len(chats) == 1:
        c = chats[0]
        await message.answer(
            t("model_picker_title_named", chat=c.title or f"Chat {c.chat_id}"),
            reply_markup=model_picker_kb(c.chat_id),
        )
        return
    await message.answer(
        t("groups_picker_title", action="модель"),
        reply_markup=groups_picker_kb("model", chats),
    )


@router.message(Command("enable"))
async def cmd_enable(message: Message) -> None:
    if _is_group(message):
        conn = await get_db()
        await upsert_chat_settings(conn, message.chat.id, enabled=True)
        await message.answer(t("enabled"))
        return
    conn = await get_db()
    chats = await list_active_chats(conn)
    if not chats:
        await message.answer(t("chats_empty"))
        return
    await message.answer(
        t("groups_picker_title", action="включение"),
        reply_markup=groups_picker_kb("enable", chats),
    )


@router.message(Command("disable"))
async def cmd_disable(message: Message) -> None:
    if _is_group(message):
        conn = await get_db()
        await upsert_chat_settings(conn, message.chat.id, enabled=False)
        await message.answer(t("disabled"))
        return
    conn = await get_db()
    chats = await list_active_chats(conn)
    if not chats:
        await message.answer(t("chats_empty"))
        return
    await message.answer(
        t("groups_picker_title", action="выключение"),
        reply_markup=groups_picker_kb("disable", chats),
    )
