from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.db.queries import Chat
from bot.services.transcriber import SUPPORTED_MODELS
from bot.texts.ru import t

# Model picker callbacks: ``mdl:set:<chat_id>:<provider>:<model>`` or ``mdl:cancel``.
# Group picker callbacks:  ``pick:<action>:<chat_id>`` (action ∈ model|enable|disable)
#                          or ``pick:cancel``.
# Telegram caps callback_data at 64 bytes — verified to fit.

CB_MDL_PREFIX = "mdl:set:"
CB_MDL_CANCEL = "mdl:cancel"
CB_PICK_PREFIX = "pick:"
CB_PICK_CANCEL = "pick:cancel"


def model_picker_kb(chat_id: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for opt in SUPPORTED_MODELS:
        rows.append(
            [
                InlineKeyboardButton(
                    text=opt.label,
                    callback_data=f"{CB_MDL_PREFIX}{chat_id}:{opt.provider}:{opt.model}",
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton(text=t("model_picker_cancel"), callback_data=CB_MDL_CANCEL)]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def groups_picker_kb(action: str, chats: list[Chat]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for c in chats:
        label = c.title or f"Chat {c.chat_id}"
        rows.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"{CB_PICK_PREFIX}{action}:{c.chat_id}",
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton(text=t("model_picker_cancel"), callback_data=CB_PICK_CANCEL)]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def parse_model_callback(data: str) -> tuple[int, str, str] | None:
    """Return ``(chat_id, provider, model)`` or ``None`` for cancel/invalid."""
    if not data.startswith(CB_MDL_PREFIX) or data == CB_MDL_CANCEL:
        return None
    rest = data[len(CB_MDL_PREFIX) :]
    parts = rest.split(":", 2)
    if len(parts) != 3:
        return None
    try:
        chat_id = int(parts[0])
    except ValueError:
        return None
    return chat_id, parts[1], parts[2]


def parse_pick_callback(data: str) -> tuple[str, int] | None:
    """Return ``(action, chat_id)`` or ``None`` for cancel/invalid."""
    if not data.startswith(CB_PICK_PREFIX) or data == CB_PICK_CANCEL:
        return None
    rest = data[len(CB_PICK_PREFIX) :]
    parts = rest.split(":", 1)
    if len(parts) != 2:
        return None
    try:
        chat_id = int(parts[1])
    except ValueError:
        return None
    return parts[0], chat_id
