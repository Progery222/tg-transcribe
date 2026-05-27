from pathlib import Path

import aiosqlite

from bot.config import settings

_conn: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    global _conn
    if _conn is None:
        db_path = Path(settings.DB_PATH)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _conn = await aiosqlite.connect(str(db_path))
        await _conn.execute("PRAGMA journal_mode=WAL")
        await _conn.execute("PRAGMA foreign_keys=ON")
    return _conn


async def _ensure_columns(conn: aiosqlite.Connection, table: str, cols: dict[str, str]) -> None:
    """Idempotent forward-only column additions (SQLite has no ADD COLUMN IF NOT EXISTS)."""
    async with conn.execute(f"PRAGMA table_info({table})") as cur:
        existing = {row[1] for row in await cur.fetchall()}
    for name, ddl in cols.items():
        if name not in existing:
            await conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


async def init_db() -> None:
    conn = await get_db()
    schema_path = Path(__file__).parent / "schema.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")
    await conn.executescript(schema_sql)
    await _ensure_columns(
        conn,
        "transcriptions",
        {
            "transcript_text": "TEXT",
            "username": "TEXT",
            "display_name": "TEXT",
            "msg_created_at": "TEXT",
        },
    )
    await conn.commit()


async def close_db() -> None:
    global _conn
    if _conn is not None:
        await _conn.close()
        _conn = None
