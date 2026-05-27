from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.db.database import get_db
from bot.db.queries import list_active_chats, upsert_chat_settings
from bot.keyboards.inline import (
    CB_MDL_CANCEL,
    CB_MDL_PREFIX,
    CB_PICK_CANCEL,
    CB_PICK_PREFIX,
    model_picker_kb,
    parse_model_callback,
    parse_pick_callback,
)
from bot.services.transcriber import find_model_option
from bot.texts.ru import t

router = Router(name="callbacks")


async def _chat_title(chat_id: int) -> str:
    conn = await get_db()
    chats = await list_active_chats(conn)
    for c in chats:
        if c.chat_id == chat_id:
            return c.title or f"Chat {chat_id}"
    return f"Chat {chat_id}"


@router.callback_query(F.data == CB_MDL_CANCEL)
async def on_cancel_model(query: CallbackQuery) -> None:
    if query.message:
        await query.message.edit_text(t("model_cancelled"))
    await query.answer()


@router.callback_query(F.data == CB_PICK_CANCEL)
async def on_cancel_pick(query: CallbackQuery) -> None:
    if query.message:
        await query.message.edit_text(t("model_cancelled"))
    await query.answer()


@router.callback_query(F.data.startswith(CB_PICK_PREFIX))
async def on_group_pick(query: CallbackQuery) -> None:
    parsed = parse_pick_callback(query.data or "")
    if parsed is None or query.message is None:
        await query.answer()
        return
    action, chat_id = parsed
    title = await _chat_title(chat_id)

    if action == "model":
        await query.message.edit_text(
            t("model_picker_title_named", chat=title),
            reply_markup=model_picker_kb(chat_id),
        )
        await query.answer()
        return

    if action in ("enable", "disable"):
        conn = await get_db()
        await upsert_chat_settings(conn, chat_id, enabled=(action == "enable"))
        key = "enabled_named" if action == "enable" else "disabled_named"
        await query.message.edit_text(t(key, chat=title))
        await query.answer()
        return

    await query.answer()


@router.callback_query(F.data.startswith(CB_MDL_PREFIX))
async def on_model_choice(query: CallbackQuery) -> None:
    parsed = parse_model_callback(query.data or "")
    if parsed is None or query.message is None:
        await query.answer()
        return
    chat_id, provider, model = parsed
    opt = find_model_option(provider, model)
    if opt is None:
        await query.answer()
        return

    conn = await get_db()
    await upsert_chat_settings(conn, chat_id, provider=provider, model=model)
    title = await _chat_title(chat_id)
    await query.message.edit_text(t("model_set_named", chat=title, label=opt.label))
    await query.answer()
