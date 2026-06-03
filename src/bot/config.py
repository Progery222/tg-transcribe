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
    MAX_FILE_BYTES: int = 500 * 1024 * 1024  # 500 MB with self-hosted Bot API
    # getFile in local Bot API mode blocks until the server downloads the whole
    # file from Telegram's DC; the aiogram session default (60s) times out on
    # large forwarded videos. Give getFile/download_file a generous timeout.
    FILE_FETCH_TIMEOUT: int = 600  # seconds

    # v4 — self-hosted Telegram Bot API (для файлов >20 МБ).
    # Если TELEGRAM_BOT_API_URL пустой — работаем через api.telegram.org (потолок 20 МБ).
    TELEGRAM_BOT_API_URL: str = ""
    TELEGRAM_API_ID: str = ""
    TELEGRAM_API_HASH: str = ""
    # Путь, по которому файлы доступны изнутри bot-контейнера (mount shared volume RO).
    # Local mode getFile возвращает абсолютный путь от имени bot-api сервиса; если
    # значение задано, бот подменит префикс на этот путь.
    TELEGRAM_BOT_API_LOCAL_ROOT: str = ""

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
        if self.TELEGRAM_BOT_API_URL and not (self.TELEGRAM_API_ID and self.TELEGRAM_API_HASH):
            raise ValueError(
                "TELEGRAM_API_ID and TELEGRAM_API_HASH are required when "
                "TELEGRAM_BOT_API_URL is set"
            )
        return self

    @property
    def bot_admin_ids(self) -> list[int]:
        return [int(x.strip()) for x in self.BOT_ADMIN_IDS.split(",") if x.strip()]

    @property
    def digest_tz(self) -> ZoneInfo:
        return ZoneInfo(self.DIGEST_TZ)


settings = Settings()  # type: ignore[call-arg]
