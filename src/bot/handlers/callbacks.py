from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.db.database import get_db
from bot.db.queries import upsert_chat_settings
from bot.keyboards.inline import CB_CANCEL, CB_PREFIX, parse_model_callback
from bot.services.transcriber import find_model_option
from bot.texts.ru import t

router = Router(name="callbacks")


@router.callback_query(F.data == CB_CANCEL)
async def on_cancel(query: CallbackQuery) -> None:
    if query.message:
        await query.message.edit_text(t("model_cancelled"))
    await query.answer()


@router.callback_query(F.data.startswith(CB_PREFIX))
async def on_model_choice(query: CallbackQuery) -> None:
    parsed = parse_model_callback(query.data or "")
    if parsed is None:
        await query.answer()
        return
    provider, model = parsed
    opt = find_model_option(provider, model)
    if opt is None or query.message is None:
        await query.answer()
        return

    conn = await get_db()
    await upsert_chat_settings(
        conn,
        query.message.chat.id,
        provider=provider,
        model=model,
    )
    await query.message.edit_text(t("model_set", label=opt.label))
    await query.answer()
