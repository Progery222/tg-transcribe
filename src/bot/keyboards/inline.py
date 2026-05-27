from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.services.transcriber import SUPPORTED_MODELS
from bot.texts.ru import t

# Callback data format: ``mdl:{provider}:{model}`` or ``mdl:cancel``.
# Telegram caps callback_data at 64 bytes. Provider+model under ~50 chars covers all
# entries in SUPPORTED_MODELS; verified manually.

CB_PREFIX = "mdl:"
CB_CANCEL = "mdl:cancel"


def model_picker_kb() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for opt in SUPPORTED_MODELS:
        rows.append(
            [
                InlineKeyboardButton(
                    text=opt.label,
                    callback_data=f"{CB_PREFIX}{opt.provider}:{opt.model}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text=t("model_picker_cancel"), callback_data=CB_CANCEL)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def parse_model_callback(data: str) -> tuple[str, str] | None:
    """Return ``(provider, model)`` or ``None`` for cancel/invalid."""
    if not data.startswith(CB_PREFIX) or data == CB_CANCEL:
        return None
    rest = data[len(CB_PREFIX) :]
    parts = rest.split(":", 1)
    if len(parts) != 2:
        return None
    return parts[0], parts[1]
