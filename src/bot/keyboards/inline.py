from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.db.queries import Chat
from bot.services.transcriber import SUPPORTED_MODELS
from bot.texts.ru import t

# Per-chat picker (used inside a group): ``mdl:set:<chat_id>:<provider>:<model>``
# Global picker  (used in DM):           ``mdl:all:<provider>:<model>``
# Cancel:                                ``mdl:cancel``
# Telegram caps callback_data at 64 bytes — verified to fit.

CB_MDL_PER_CHAT_PREFIX = "mdl:set:"
CB_MDL_GLOBAL_PREFIX = "mdl:all:"
CB_MDL_CANCEL = "mdl:cancel"


def model_picker_kb(chat_id: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=opt.label,
                callback_data=f"{CB_MDL_PER_CHAT_PREFIX}{chat_id}:{opt.provider}:{opt.model}",
            )
        ]
        for opt in SUPPORTED_MODELS
    ]
    rows.append([InlineKeyboardButton(text=t("model_picker_cancel"), callback_data=CB_MDL_CANCEL)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def model_picker_kb_global() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=opt.label,
                callback_data=f"{CB_MDL_GLOBAL_PREFIX}{opt.provider}:{opt.model}",
            )
        ]
        for opt in SUPPORTED_MODELS
    ]
    rows.append([InlineKeyboardButton(text=t("model_picker_cancel"), callback_data=CB_MDL_CANCEL)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def parse_model_callback(data: str) -> tuple[int, str, str] | None:
    """Return ``(chat_id, provider, model)`` or ``None`` for cancel/invalid."""
    if not data.startswith(CB_MDL_PER_CHAT_PREFIX):
        return None
    rest = data[len(CB_MDL_PER_CHAT_PREFIX) :]
    parts = rest.split(":", 2)
    if len(parts) != 3:
        return None
    try:
        chat_id = int(parts[0])
    except ValueError:
        return None
    return chat_id, parts[1], parts[2]


def parse_global_model_callback(data: str) -> tuple[str, str] | None:
    """Return ``(provider, model)`` for the DM global picker, or ``None``."""
    if not data.startswith(CB_MDL_GLOBAL_PREFIX):
        return None
    rest = data[len(CB_MDL_GLOBAL_PREFIX) :]
    parts = rest.split(":", 1)
    if len(parts) != 2:
        return None
    return parts[0], parts[1]


# Digest group picker (DM, super-admin): pick which group /digest_now runs for.
#   One group:   ``dg:one:<chat_id>``
#   All groups:  ``dg:all``
#   Cancel:      ``dg:cancel``
CB_DIGEST_ONE_PREFIX = "dg:one:"
CB_DIGEST_ALL = "dg:all"
CB_DIGEST_CANCEL = "dg:cancel"


def digest_group_picker_kb(chats: list[Chat]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=c.title or f"Chat {c.chat_id}",
                callback_data=f"{CB_DIGEST_ONE_PREFIX}{c.chat_id}",
            )
        ]
        for c in chats
    ]
    rows.append([InlineKeyboardButton(text=t("digest_picker_all"), callback_data=CB_DIGEST_ALL)])
    rows.append(
        [InlineKeyboardButton(text=t("model_picker_cancel"), callback_data=CB_DIGEST_CANCEL)]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def parse_digest_group_callback(data: str) -> int | None:
    """Return ``chat_id`` from a ``dg:one:<chat_id>`` callback, or ``None``."""
    if not data.startswith(CB_DIGEST_ONE_PREFIX):
        return None
    try:
        return int(data[len(CB_DIGEST_ONE_PREFIX) :])
    except ValueError:
        return None
