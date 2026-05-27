import structlog
from aiogram import Router
from aiogram.enums import ChatMemberStatus
from aiogram.types import ChatMemberUpdated

from bot.db.database import get_db
from bot.db.queries import upsert_chat

log = structlog.get_logger(__name__)

router = Router(name="chat_member")

_LEFT_STATUSES = {ChatMemberStatus.LEFT, ChatMemberStatus.KICKED, ChatMemberStatus.RESTRICTED}


@router.my_chat_member()
async def on_my_chat_member(event: ChatMemberUpdated) -> None:
    new_status = event.new_chat_member.status
    active = new_status not in _LEFT_STATUSES
    conn = await get_db()
    await upsert_chat(conn, event.chat.id, event.chat.title, active=active)
    log.info(
        "my_chat_member_updated",
        chat_id=event.chat.id,
        title=event.chat.title,
        status=str(new_status),
        active=active,
    )
