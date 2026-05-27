from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram
    BOT_TOKEN: str

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_TIMEOUT: int = 120

    # Gemini
    GEMINI_API_KEY: str = ""
    GEMINI_TIMEOUT: int = 120

    # Defaults applied to fresh chats; overridable per-chat via /model.
    DEFAULT_PROVIDER: Literal["openai", "gemini"] = "openai"
    DEFAULT_MODEL: str = "gpt-4o-mini-transcribe"

    # Concurrency / limits
    MAX_CONCURRENT_TRANSCRIPTIONS: int = 3
    MAX_FILE_BYTES: int = 20 * 1024 * 1024  # Telegram Bot API getFile cap

    # v2: access control + DM fanout + daily digest
    BOT_ADMIN_IDS: str = ""  # comma-separated Telegram user IDs
    DM_SEND_DELAY_MS: int = 50
    DIGEST_HOUR: int = 10
    DIGEST_MINUTE: int = 0
    DIGEST_TZ: str = "Europe/Moscow"
    DIGEST_WINDOW_HOURS: int = 24
    INVITE_TTL_HOURS: int = 72

    # Runtime
    DB_PATH: str = "data/bot.sqlite3"
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = False
    BOT_MODE: Literal["polling", "webhook"] = "polling"

    @model_validator(mode="after")
    def _check_provider_keys(self) -> "Settings":
        if self.DEFAULT_PROVIDER == "openai" and not self.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required when DEFAULT_PROVIDER=openai")
        if self.DEFAULT_PROVIDER == "gemini" and not self.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is required when DEFAULT_PROVIDER=gemini")
        return self

    @property
    def bot_admin_ids(self) -> list[int]:
        return [int(x.strip()) for x in self.BOT_ADMIN_IDS.split(",") if x.strip()]

    @property
    def digest_tz(self) -> ZoneInfo:
        return ZoneInfo(self.DIGEST_TZ)


settings = Settings()  # type: ignore[call-arg]
