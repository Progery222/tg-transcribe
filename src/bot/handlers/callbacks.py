from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.db.database import get_db
from bot.db.queries import set_model_for_all_groups, upsert_chat_settings
from bot.keyboards.inline import (
    CB_MDL_CANCEL,
    CB_MDL_GLOBAL_PREFIX,
    CB_MDL_PER_CHAT_PREFIX,
    parse_global_model_callback,
    parse_model_callback,
)
from bot.services.transcriber import find_model_option
from bot.texts.ru import t

router = Router(name="callbacks")


@router.callback_query(F.data == CB_MDL_CANCEL)
async def on_cancel_model(query: CallbackQuery) -> None:
    if query.message:
        await query.message.edit_text(t("model_cancelled"))
    await query.answer()


@router.callback_query(F.data.startswith(CB_MDL_PER_CHAT_PREFIX))
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
    await query.message.edit_text(t("model_set", label=opt.label))
    await query.answer()


@router.callback_query(F.data.startswith(CB_MDL_GLOBAL_PREFIX))
async def on_model_choice_global(query: CallbackQuery) -> None:
    parsed = parse_global_model_callback(query.data or "")
    if parsed is None or query.message is None:
        await query.answer()
        return
    provider, model = parsed
    opt = find_model_option(provider, model)
    if opt is None:
        await query.answer()
        return

    conn = await get_db()
    affected = await set_model_for_all_groups(conn, provider=provider, model=model)
    await query.message.edit_text(t("model_set_global", label=opt.label, count=affected))
    await query.answer()
