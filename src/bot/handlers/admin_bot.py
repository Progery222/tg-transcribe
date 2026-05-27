import structlog
from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from bot.db.database import get_db
from bot.db.queries import list_active_chats
from bot.services import subscriber_service as ss
from bot.services.digest_service import run_digest_now
from bot.texts.ru import t

log = structlog.get_logger(__name__)

router = Router(name="admin_bot")


def _parse_user_id(arg: str | None) -> int | None:
    if not arg:
        return None
    arg = arg.strip().lstrip("@")
    if arg.lstrip("-").isdigit():
        return int(arg)
    return None


def _display_name(user) -> str | None:
    if user is None:
        return None
    parts = [p for p in (user.first_name, user.last_name) if p]
    return " ".join(parts) if parts else None


@router.message(Command("grant"))
async def cmd_grant(message: Message, command: CommandObject) -> None:
    uid = _parse_user_id(command.args)
    if uid is None:
        await message.reply(t("grant_need_id"))
        return
    conn = await get_db()
    granted = await ss.grant(
        conn,
        uid,
        granted_by=message.from_user.id if message.from_user else 0,
    )
    key = "grant_ok" if granted else "grant_already"
    await message.reply(t(key, user_id=uid))


@router.message(Command("revoke"))
async def cmd_revoke(message: Message, command: CommandObject) -> None:
    uid = _parse_user_id(command.args)
    if uid is None:
        await message.reply(t("grant_need_id"))
        return
    conn = await get_db()
    ok = await ss.revoke(conn, uid)
    key = "revoke_ok" if ok else "revoke_not_found"
    await message.reply(t(key, user_id=uid))


@router.message(Command("subscribers"))
async def cmd_subscribers(message: Message) -> None:
    conn = await get_db()
    subs = await ss.list_active_subscribers(conn)
    if not subs:
        await message.reply(t("subscribers_empty"))
        return
    lines = [
        t(
            "subscribers_line",
            uid=s.user_id,
            username=s.username or "—",
            display=s.display_name or "—",
        )
        for s in subs
    ]
    await message.reply(t("subscribers_list_template", lines="\n".join(lines)))


@router.message(Command("invite"))
async def cmd_invite(message: Message, bot: Bot) -> None:
    conn = await get_db()
    token, expires = await ss.create_invite(
        conn, super_admin_id=message.from_user.id if message.from_user else 0
    )
    me = await bot.get_me()
    url = f"https://t.me/{me.username}?start={token}"
    expires_str = expires.strftime("%Y-%m-%d %H:%M UTC") if expires else "—"
    await message.reply(t("invite_created", url=url, expires=expires_str))


@router.message(Command("chats"))
async def cmd_chats(message: Message) -> None:
    conn = await get_db()
    chats = await list_active_chats(conn)
    if not chats:
        await message.reply(t("chats_empty"))
        return
    lines = [
        t("chats_line", title=c.title or f"Chat {c.chat_id}", chat_id=c.chat_id) for c in chats
    ]
    await message.reply(t("chats_list_template", lines="\n".join(lines)))


@router.message(Command("digest_now"))
async def cmd_digest_now(message: Message, bot: Bot) -> None:
    await message.reply(t("digest_now_running"))
    try:
        sent = await run_digest_now(bot)
    except Exception:
        log.exception("digest_now_failed")
        await message.reply(t("digest_now_failed"))
        return
    await message.reply(t("digest_now_done", files=sent))
