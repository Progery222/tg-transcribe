from dataclasses import dataclass
from datetime import UTC, datetime

import aiosqlite


@dataclass
class ChatSettings:
    chat_id: int
    provider: str
    model: str
    language: str | None
    enabled: bool


async def get_chat_settings(conn: aiosqlite.Connection, chat_id: int) -> ChatSettings | None:
    async with conn.execute(
        "SELECT chat_id, provider, model, language, enabled FROM chat_settings WHERE chat_id = ?",
        (chat_id,),
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        return None
    return ChatSettings(
        chat_id=row[0],
        provider=row[1],
        model=row[2],
        language=row[3],
        enabled=bool(row[4]),
    )


async def upsert_chat_settings(
    conn: aiosqlite.Connection,
    chat_id: int,
    *,
    provider: str | None = None,
    model: str | None = None,
    language: str | None = ...,  # type: ignore[assignment]
    enabled: bool | None = None,
) -> None:
    """Insert or update chat settings.

    Pass ``language=None`` to clear (auto-detect); omit the kwarg to keep current value.
    """
    existing = await get_chat_settings(conn, chat_id)
    default_provider = existing.provider if existing else "openai"
    default_model = existing.model if existing else "gpt-4o-mini-transcribe"
    default_language = existing.language if existing else None
    default_enabled = existing.enabled if existing else True

    new_provider = provider if provider is not None else default_provider
    new_model = model if model is not None else default_model
    new_language = default_language if language is ... else language
    new_enabled = enabled if enabled is not None else default_enabled

    await conn.execute(
        """
        INSERT INTO chat_settings (chat_id, provider, model, language, enabled, updated_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(chat_id) DO UPDATE SET
            provider   = excluded.provider,
            model      = excluded.model,
            language   = excluded.language,
            enabled    = excluded.enabled,
            updated_at = datetime('now')
        """,
        (chat_id, new_provider, new_model, new_language, int(new_enabled)),
    )
    await conn.commit()


@dataclass
class TranscriptionRow:
    chat_id: int
    user_id: int | None
    message_id: int | None
    content_type: str | None
    provider: str | None
    model: str | None
    success: bool
    error_code: str | None
    audio_seconds: int | None
    latency_ms: int | None
    transcript_text: str | None = None
    username: str | None = None
    display_name: str | None = None
    msg_created_at: str | None = None


async def log_transcription(conn: aiosqlite.Connection, row: TranscriptionRow) -> None:
    await conn.execute(
        """
        INSERT INTO transcriptions
            (chat_id, user_id, message_id, content_type, provider, model,
             success, error_code, audio_seconds, latency_ms,
             transcript_text, username, display_name, msg_created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row.chat_id,
            row.user_id,
            row.message_id,
            row.content_type,
            row.provider,
            row.model,
            int(row.success),
            row.error_code,
            row.audio_seconds,
            row.latency_ms,
            row.transcript_text,
            row.username,
            row.display_name,
            row.msg_created_at,
        ),
    )
    await conn.commit()


@dataclass
class Chat:
    chat_id: int
    title: str | None
    active: bool


async def upsert_chat(
    conn: aiosqlite.Connection,
    chat_id: int,
    title: str | None,
    *,
    active: bool = True,
) -> None:
    await conn.execute(
        """
        INSERT INTO chats (chat_id, title, active, last_seen_at)
        VALUES (?, ?, ?, datetime('now'))
        ON CONFLICT(chat_id) DO UPDATE SET
          title        = COALESCE(excluded.title, chats.title),
          active       = excluded.active,
          last_seen_at = datetime('now')
        """,
        (chat_id, title, int(active)),
    )
    await conn.commit()


async def touch_chat(conn: aiosqlite.Connection, chat_id: int, title: str | None) -> None:
    """Update title (if non-NULL) + last_seen_at without touching ``active``.

    Used by ChatSettingsMiddleware on every group message to self-heal `chats` rows
    that may pre-date the v2 chat_member handler — without overriding an explicit
    ``active=0`` set by my_chat_member when the bot was kicked.
    """
    cur = await conn.execute(
        """
        UPDATE chats
        SET title        = COALESCE(?, title),
            last_seen_at = datetime('now')
        WHERE chat_id = ?
        """,
        (title, chat_id),
    )
    if cur.rowcount == 0:
        await conn.execute(
            """
            INSERT INTO chats (chat_id, title, active, last_seen_at)
            VALUES (?, ?, 1, datetime('now'))
            """,
            (chat_id, title),
        )
    await conn.commit()


async def list_active_chats(conn: aiosqlite.Connection) -> list[Chat]:
    async with conn.execute(
        "SELECT chat_id, title, active FROM chats WHERE active=1 ORDER BY COALESCE(title, '')"
    ) as cur:
        rows = await cur.fetchall()
    return [Chat(chat_id=r[0], title=r[1], active=bool(r[2])) for r in rows]


@dataclass
class DigestRow:
    ts_iso: str
    username: str | None
    display_name: str | None
    transcript_text: str


async def fetch_digest_rows(
    conn: aiosqlite.Connection,
    chat_id: int,
    start_utc: datetime,
    end_utc: datetime,
) -> list[DigestRow]:
    """Successful transcriptions for ``chat_id`` whose effective timestamp lies in
    [start_utc, end_utc). Falls back to ``created_at`` when ``msg_created_at`` is NULL.
    """
    start_iso = start_utc.astimezone(UTC).isoformat()
    end_iso = end_utc.astimezone(UTC).isoformat()
    async with conn.execute(
        """
        SELECT COALESCE(msg_created_at, created_at) AS ts,
               username, display_name, transcript_text
        FROM transcriptions
        WHERE chat_id = ?
          AND success = 1
          AND transcript_text IS NOT NULL
          AND transcript_text <> ''
          AND COALESCE(msg_created_at, created_at) >= ?
          AND COALESCE(msg_created_at, created_at) <  ?
        ORDER BY ts ASC
        """,
        (chat_id, start_iso, end_iso),
    ) as cur:
        rows = await cur.fetchall()
    return [DigestRow(r[0], r[1], r[2], r[3]) for r in rows]
