import structlog
from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery

from bot.db.database import get_db
from bot.db.queries import set_model_for_all_groups, upsert_chat_settings
from bot.keyboards.inline import (
    CB_DIGEST_ALL,
    CB_DIGEST_CANCEL,
    CB_DIGEST_ONE_PREFIX,
    CB_MDL_CANCEL,
    CB_MDL_GLOBAL_PREFIX,
    CB_MDL_PER_CHAT_PREFIX,
    parse_digest_group_callback,
    parse_global_model_callback,
    parse_model_callback,
)
from bot.services.digest_service import run_digest_now
from bot.services.transcriber import find_model_option
from bot.texts.ru import t

log = structlog.get_logger(__name__)

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


async def _run_digest_and_report(query: CallbackQuery, bot: Bot, only_chat_id: int | None) -> None:
    await query.answer()
    if query.message is None:
        return
    await query.message.edit_text(t("digest_now_running"))
    try:
        sent = await run_digest_now(bot, only_chat_id=only_chat_id)
    except Exception:
        log.exception("digest_now_failed", only_chat_id=only_chat_id)
        await query.message.edit_text(t("digest_now_failed"))
        return
    await query.message.edit_text(t("digest_now_done", files=sent))


@router.callback_query(F.data == CB_DIGEST_CANCEL)
async def on_digest_cancel(query: CallbackQuery) -> None:
    if query.message:
        await query.message.edit_text(t("digest_cancelled"))
    await query.answer()


@router.callback_query(F.data == CB_DIGEST_ALL)
async def on_digest_all(query: CallbackQuery, bot: Bot) -> None:
    await _run_digest_and_report(query, bot, None)


@router.callback_query(F.data.startswith(CB_DIGEST_ONE_PREFIX))
async def on_digest_one(query: CallbackQuery, bot: Bot) -> None:
    chat_id = parse_digest_group_callback(query.data or "")
    if chat_id is None:
        await query.answer()
        return
    await _run_digest_and_report(query, bot, chat_id)
