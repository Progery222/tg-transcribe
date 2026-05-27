import os
from pathlib import Path

# Configure env BEFORE bot.config imports anywhere. pydantic-settings reads it on first import.
os.environ.setdefault("BOT_TOKEN", "test:token")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini")
os.environ.setdefault("DEFAULT_PROVIDER", "openai")
os.environ.setdefault("DEFAULT_MODEL", "gpt-4o-mini-transcribe")

import pytest

import bot.db.database as database_mod


@pytest.fixture
async def tmp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "test.sqlite3"
    # Force the singleton to re-open against the temp path.
    monkeypatch.setattr(database_mod.settings, "DB_PATH", str(db_path))
    database_mod._conn = None
    from bot.db.database import close_db, init_db

    await init_db()
    yield
    await close_db()


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"
