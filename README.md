# tg-transcribe

Telegram-бот, который добавляется как админ в группу, транскрибирует голосовые сообщения и видеокружки участников и **отправляет тексты в ЛС подписчикам** (а не в исходную группу). Каждый день в 10:00 по Москве формирует .txt-сводку по каждой группе за последние сутки.

Два провайдера распознавания, переключаются командой `/model` владельцем бота:

- OpenAI: `gpt-4o-mini-transcribe`, `gpt-4o-transcribe`, `whisper-1`
- Gemini: `gemini-2.5-flash`, `gemini-2.5-pro`

## ⚠️ Group Privacy

Telegram-бот видит голосовые в группе **только если** у него отключён Group Privacy в @BotFather:
`/mybots` → бот → **Bot Settings** → **Group Privacy** → **Turn off**.
Статус админа в группе **не заменяет** эту настройку — оба должны быть.

## Подготовка

1. **@BotFather**: создайте бота, получите `BOT_TOKEN`, отключите Group Privacy.
2. **OpenAI key** — https://platform.openai.com/api-keys (для `gpt-4o-*-transcribe` нужен tier 1+; `whisper-1` доступен всем).
3. **Gemini key** — https://aistudio.google.com/app/apikey (free tier подходит).
4. **Узнайте свой Telegram user_id** (например, через @userinfobot) — это значение для `BOT_ADMIN_IDS`.

## Запуск (Docker)

```bash
cp .env.example .env
# заполните BOT_TOKEN, OPENAI_API_KEY, GEMINI_API_KEY, BOT_ADMIN_IDS=<ваш_id>
docker compose up -d --build
docker compose logs -f bot
```

## Доступ к боту

Бот **по приглашениям**: транскрипции получают только подписчики, добавленные владельцем.

**Владелец** — пользователи, чьи Telegram ID перечислены в `BOT_ADMIN_IDS`. Они автоматически считаются подписчиками и могут управлять доступом.

**Добавить подписчика:**

- `/grant <user_id>` — добавить по числовому ID (нужно знать ID заранее)
- `/invite` — сгенерировать одноразовую ссылку `t.me/<bot>?start=TOKEN` (TTL 72 ч по умолчанию). Первый, кто откроет ссылку, становится подписчиком.

`@username` без числового ID Bot API не резолвит — для незнакомых юзеров используйте `/invite`.

**Управление:**

| Команда | Где | Действие |
|---|---|---|
| `/invite` | DM | одноразовая ссылка |
| `/grant <id>` | DM | добавить подписчика |
| `/revoke <id>` | DM | отозвать доступ |
| `/subscribers` | DM | список подписчиков |
| `/chats` | DM | список групп с ботом |
| `/digest_now` | DM | сформировать сводку прямо сейчас |
| `/model` | в группе | выбрать модель распознавания |
| `/enable`, `/disable` | в группе | включить/выключить мониторинг группы |
| `/start` | DM | приветствие, статус доступа |
| `/help` | везде | справка |

## Формат сообщения подписчику

```
🎙 [Имя группы] @username · 14:23
«Привет всем, как дела?»
```

Время — в часовом поясе `DIGEST_TZ` (по умолчанию Europe/Moscow).

## Ежедневная сводка

В 10:00 (Europe/Moscow) бот:

1. Собирает все успешные транскрипции за последние 24 часа (10:00 вчера → 10:00 сегодня MSK).
2. Формирует **отдельный .txt на каждую группу** (`{слаг}_{YYYY-MM-DD}.txt`).
3. Отправляет каждый файл каждому подписчику как Telegram-документ.
4. Группы без транскрипций в окне пропускаются (пустые файлы не шлёт).

Принудительный запуск — `/digest_now` владельцем.

## Конфигурация

Все параметры через env (см. [.env.example](.env.example)):

| Переменная | Назначение |
|---|---|
| `BOT_TOKEN` | токен от @BotFather |
| `OPENAI_API_KEY` / `GEMINI_API_KEY` | ключи провайдеров |
| `DEFAULT_PROVIDER`, `DEFAULT_MODEL` | по умолчанию для новых чатов |
| `BOT_ADMIN_IDS` | Telegram ID владельцев (comma-separated) |
| `DIGEST_HOUR`, `DIGEST_MINUTE`, `DIGEST_TZ` | когда формировать сводку |
| `DIGEST_WINDOW_HOURS` | размер окна (по умолчанию 24) |
| `INVITE_TTL_HOURS` | время жизни инвайт-ссылки |
| `MAX_CONCURRENT_TRANSCRIPTIONS` | глобальный лимит параллельных задач |
| `MAX_FILE_BYTES` | максимальный размер файла (20 МБ — лимит Bot API) |
| `DM_SEND_DELAY_MS` | задержка между DM (анти-flood) |
| `DB_PATH`, `LOG_LEVEL`, `LOG_JSON` | runtime |

## Архитектура

```
src/bot/
├─ config.py             pydantic-settings + zoneinfo
├─ logging_setup.py      structlog
├─ db/                   SQLite + WAL + forward-only миграции
│  ├─ schema.sql         chat_settings, transcriptions, subscribers, invite_tokens, chats
│  └─ queries.py         + fetch_digest_rows, upsert_chat, list_active_chats
├─ services/
│  ├─ transcriber.py     Protocol + SUPPORTED_MODELS
│  ├─ openai_transcriber.py
│  ├─ gemini_transcriber.py
│  ├─ audio_pipeline.py  ffmpeg → m4a через temp-файлы
│  ├─ worker_pool.py     asyncio.Semaphore
│  ├─ subscriber_service.py    grant/revoke/invite + super_admin
│  ├─ dm_sender.py             sequential DM с RetryAfter handling
│  └─ digest_service.py        APScheduler + /digest_now + .txt rendering
├─ handlers/
│  ├─ start.py           /start (+TOKEN), /help
│  ├─ admin_bot.py       /grant /revoke /subscribers /invite /chats /digest_now (DM, super-admin)
│  ├─ admin.py           /model /enable /disable (группа, super-admin)
│  ├─ callbacks.py       выбор модели
│  ├─ voice.py           DM fanout вместо reply
│  └─ chat_member.py     my_chat_member → upsert chats
├─ middlewares/
│  ├─ chat_settings.py   инжектит ChatSettings + self-heal chats
│  └─ super_admin_only.py
├─ keyboards/            model picker
├─ utils/                tg_files, text_split
└─ texts/ru.py           t("key", **kwargs)
```

## Проверка работоспособности

1. Запустите бота, отправьте `/start` в ЛС → должен прийти `start_super_admin` (вы в `BOT_ADMIN_IDS`)
2. `/chats` → пусто (пока бот ни в одной группе)
3. Добавьте бота в тестовую группу (как админа, Group Privacy off) → `/chats` показывает её
4. Отправьте голосовое в группе → транскрипция приходит вам в ЛС, в группу — ничего
5. `/invite` → получаете URL → откройте с другого аккаунта → `invite_used`, второй аккаунт стал подписчиком
6. Голосовое в группе → транскрипция приходит обоим
7. `/digest_now` → пришёл .txt по каждой группе с транскрипциями за сутки
8. В 10:00 MSK scheduler автоматически выстреливает (для теста временно установите `DIGEST_HOUR` / `DIGEST_MINUTE` на пару минут вперёд)

## Разработка

```bash
uv sync
uv run ruff check .
uv run ruff format .
uv run pytest -v
```

## Deployment

Auto-deploy: push в `main` → GitHub Actions запускает `test` → `build-and-push` (image в GHCR) → `deploy` (SSH на VPS → `docker compose pull && up -d`).

### Первичный setup VPS

1. `sudo mkdir -p /opt/tg-transcribe && sudo chown $USER /opt/tg-transcribe`
2. С ноутбука: `scp docker-compose.prod.yml user@vps:/opt/tg-transcribe/`
3. На VPS: создать `/opt/tg-transcribe/.env` с реальными ключами (см. [.env.example](.env.example)), `chmod 600 .env`
4. На github.com → Settings → Developer settings → Personal access tokens (classic) → Generate new (scope `read:packages`, no expiration)
5. На VPS: `echo $PAT | docker login ghcr.io -u Progery222 --password-stdin`
6. `docker compose -f docker-compose.prod.yml pull && docker compose -f docker-compose.prod.yml up -d`
7. `docker compose -f docker-compose.prod.yml logs -f bot` — должны быть `transcribers_loaded`, `scheduler_started`, `bot_started`

### SSH-ключ для CI (один раз на ноутбуке)

```bash
ssh-keygen -t ed25519 -f ~/deploy_key -C github-actions-tg-transcribe -N ""
ssh-copy-id -i ~/deploy_key.pub user@vps
gh secret set VPS_SSH_KEY < ~/deploy_key
gh secret set VPS_HOST --body "<IP>"
gh secret set VPS_USER --body "<user>"
gh secret set VPS_PATH --body "/opt/tg-transcribe"
# (опц.) gh secret set VPS_SSH_PORT --body "2222"
ssh -i ~/deploy_key user@vps "docker ps"   # smoke
shred -u ~/deploy_key                       # удалить локальную копию
```

### Подмена `.env` на сервере

`.env` не управляется CI. Чтобы ротировать ключ:

```bash
ssh user@vps
sudo nano /opt/tg-transcribe/.env
docker compose -f /opt/tg-transcribe/docker-compose.prod.yml up -d
```

### Rollback

```bash
ssh user@vps
cd /opt/tg-transcribe
IMAGE_TAG=sha-<previous_full_sha> docker compose -f docker-compose.prod.yml up -d
```

Сброс: `unset IMAGE_TAG` (или `IMAGE_TAG=latest`) и повторно `up -d`.

### Backup volume

```bash
docker run --rm -v bot_data:/data -v $PWD:/backup alpine \
  tar czf /backup/bot-$(date +%F).tgz -C /data .
```

**⚠ Никогда не запускайте** `docker compose down -v` — флаг `-v` стирает named volume с SQLite (история транскрипций, подписчики, инвайты).

## Лицензия

MIT.
