import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import aiosqlite

from bot.config import settings


@dataclass
class Subscriber:
    user_id: int
    username: str | None
    display_name: str | None
    granted_by: int
    granted_at: str
    active: bool


def is_super_admin(user_id: int) -> bool:
    return user_id in settings.bot_admin_ids


async def is_subscriber(conn: aiosqlite.Connection, user_id: int) -> bool:
    if is_super_admin(user_id):
        return True
    async with conn.execute(
        "SELECT 1 FROM subscribers WHERE user_id=? AND active=1", (user_id,)
    ) as cur:
        return (await cur.fetchone()) is not None


async def list_active_subscribers(conn: aiosqlite.Connection) -> list[Subscriber]:
    async with conn.execute(
        """
        SELECT user_id, username, display_name, granted_by, granted_at, active
        FROM subscribers WHERE active=1 ORDER BY granted_at
        """
    ) as cur:
        rows = await cur.fetchall()
    return [
        Subscriber(
            user_id=r[0],
            username=r[1],
            display_name=r[2],
            granted_by=r[3],
            granted_at=r[4],
            active=bool(r[5]),
        )
        for r in rows
    ]


async def list_dm_recipients(conn: aiosqlite.Connection) -> set[int]:
    """Active subscribers plus super-admins (dedup via set)."""
    subs = {s.user_id for s in await list_active_subscribers(conn)}
    subs |= set(settings.bot_admin_ids)
    return subs


async def grant(
    conn: aiosqlite.Connection,
    user_id: int,
    granted_by: int,
    *,
    username: str | None = None,
    display_name: str | None = None,
) -> bool:
    """Returns True if newly active, False if was already active."""
    async with conn.execute("SELECT active FROM subscribers WHERE user_id=?", (user_id,)) as cur:
        existing = await cur.fetchone()
    if existing and existing[0] == 1:
        return False
    await conn.execute(
        """
        INSERT INTO subscribers (user_id, username, display_name, granted_by, active, granted_at)
        VALUES (?, ?, ?, ?, 1, datetime('now'))
        ON CONFLICT(user_id) DO UPDATE SET
          active       = 1,
          username     = excluded.username,
          display_name = excluded.display_name,
          granted_by   = excluded.granted_by,
          granted_at   = datetime('now')
        """,
        (user_id, username, display_name, granted_by),
    )
    await conn.commit()
    return True


async def revoke(conn: aiosqlite.Connection, user_id: int) -> bool:
    cur = await conn.execute(
        "UPDATE subscribers SET active=0 WHERE user_id=? AND active=1", (user_id,)
    )
    await conn.commit()
    return cur.rowcount > 0


async def create_invite(
    conn: aiosqlite.Connection,
    super_admin_id: int,
    *,
    ttl_hours: int | None = None,
) -> tuple[str, datetime | None]:
    token = secrets.token_urlsafe(16)
    ttl = ttl_hours if ttl_hours is not None else settings.INVITE_TTL_HOURS
    expires = (datetime.now(UTC) + timedelta(hours=ttl)) if ttl > 0 else None
    await conn.execute(
        "INSERT INTO invite_tokens (token, created_by, expires_at) VALUES (?, ?, ?)",
        (token, super_admin_id, expires.isoformat() if expires else None),
    )
    await conn.commit()
    return token, expires


async def consume_invite(
    conn: aiosqlite.Connection,
    token: str,
    user_id: int,
    *,
    username: str | None = None,
    display_name: str | None = None,
) -> str:
    """Returns one of: ``'ok' | 'invalid' | 'used' | 'expired'``."""
    async with conn.execute(
        "SELECT created_by, expires_at, consumed_by FROM invite_tokens WHERE token=?",
        (token,),
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        return "invalid"
    created_by, expires_at, consumed_by = row
    if consumed_by is not None:
        return "used"
    if expires_at is not None:
        exp = datetime.fromisoformat(expires_at)
        if datetime.now(UTC) >= exp:
            return "expired"

    cur = await conn.execute(
        """
        UPDATE invite_tokens
        SET consumed_by=?, consumed_at=datetime('now')
        WHERE token=? AND consumed_by IS NULL
        """,
        (user_id, token),
    )
    if cur.rowcount == 0:
        await conn.commit()
        return "used"
    await grant(
        conn,
        user_id,
        granted_by=created_by,
        username=username,
        display_name=display_name,
    )
    return "ok"
