CREATE TABLE IF NOT EXISTS chat_settings (
  chat_id     INTEGER PRIMARY KEY,
  provider    TEXT    NOT NULL DEFAULT 'openai',
  model       TEXT    NOT NULL DEFAULT 'gpt-4o-mini-transcribe',
  language    TEXT,
  enabled     INTEGER NOT NULL DEFAULT 1,
  created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
  updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS transcriptions (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  chat_id         INTEGER NOT NULL,
  user_id         INTEGER,
  message_id      INTEGER,
  content_type    TEXT,
  provider        TEXT,
  model           TEXT,
  success         INTEGER NOT NULL,
  error_code      TEXT,
  audio_seconds   INTEGER,
  latency_ms      INTEGER,
  created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_tx_chat_date ON transcriptions(chat_id, created_at);
CREATE INDEX IF NOT EXISTS idx_tx_chat_success_date ON transcriptions(chat_id, success, created_at);

CREATE TABLE IF NOT EXISTS subscribers (
  user_id      INTEGER PRIMARY KEY,
  username     TEXT,
  display_name TEXT,
  granted_by   INTEGER NOT NULL,
  granted_at   TEXT    NOT NULL DEFAULT (datetime('now')),
  active       INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS invite_tokens (
  token       TEXT PRIMARY KEY,
  created_by  INTEGER NOT NULL,
  created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
  expires_at  TEXT,
  consumed_by INTEGER,
  consumed_at TEXT
);

CREATE TABLE IF NOT EXISTS chats (
  chat_id      INTEGER PRIMARY KEY,
  title        TEXT,
  added_at     TEXT    NOT NULL DEFAULT (datetime('now')),
  last_seen_at TEXT    NOT NULL DEFAULT (datetime('now')),
  active       INTEGER NOT NULL DEFAULT 1
);
