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

## Большие файлы (>20 МБ)

`api.telegram.org` не отдаёт файлы больше 20 МБ. Чтобы обрабатывать длинные видео и
голосовые до **500 МБ**, рядом с ботом поднимается собственный Telegram Bot API
server (`aiogram/telegram-bot-api`).

1. Получите `api_id` и `api_hash` на https://my.telegram.org/apps
2. Допишите в `.env`:
   ```
   TELEGRAM_BOT_API_URL=http://telegram-bot-api:8081
   TELEGRAM_API_ID=12345
   TELEGRAM_API_HASH=abcdef0123456789...
   TELEGRAM_BOT_API_LOCAL_ROOT=/var/lib/telegram-bot-api
   ```
3. **Один раз** перед первым запуском с локальным API разлогиньте бота со старого:
   ```bash
   curl -X POST "https://api.telegram.org/bot$BOT_TOKEN/logOut"
   ```
4. Запустите профиль `big-files`:
   ```bash
   docker compose --profile big-files up -d --build
   ```

После этого видео/голосовые/аудио до 500 МБ обрабатываются как обычно. Аудиодорожка
автоматически перекодируется в Opus 16 kbps mono перед отправкой в OpenAI/Gemini
(≈ 7 МБ на час речи). Если после сжатия запись всё ещё не лезет в лимит провайдера
(25 МБ OpenAI / 20 МБ Gemini) — она автоматически режется на 30-минутные чанки,
транскрипция склеивается через `\n\n`.

Если не нужны большие файлы — просто не задавайте `TELEGRAM_BOT_API_URL`, и бот будет
ходить в `api.telegram.org` с привычным лимитом 20 МБ.

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
| `MAX_FILE_BYTES` | максимальный размер файла (500 МБ при self-hosted Bot API; 20 МБ — лимит публичного API) |
| `TELEGRAM_BOT_API_URL` | URL локального Bot API (пустой = `api.telegram.org`) |
| `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` | для self-hosted Bot API (получаются на my.telegram.org) |
| `TELEGRAM_BOT_API_LOCAL_ROOT` | путь к shared volume внутри bot-контейнера |
| `DM_SEND_DELAY_MS` | задержка между DM (анти-flood) |
| `INGEST_ENABLED`, `INGEST_URL`, `INGEST_CHAT_IDS` | отправка файла ежедневного дайджеста POST'ом во внешний сервис (raw `text/plain`; только автоматический дайджест, `/digest_now` не шлёт) |
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

Production сервиса управляется Coolify. Единственный штатный поток:

```text
feature-ветка -> Pull Request -> CI -> merge в main -> Coolify auto-deploy
```

Параметры production-ресурса:

- Coolify project: `telegram-bots`
- Coolify resource: `tg-transcribe`
- Git repository: `Progery222/tg-transcribe`
- branch: `main`
- Compose file: `docker-compose.coolify.yml`

GitHub Actions выполняет `uv sync --frozen`, Ruff, Pytest, проверку Compose-файла и Docker-сборку без push. SSH-deploy, self-hosted runner и публикация GHCR не используются.

### Release

Разработка ведётся в локальном контексте Orca `tg-transcribe — исходники` из `C:\Projects\Серваки\tg-transcribe`:

1. Создайте feature-ветку от актуального `main`.
2. Внесите изменение и выполните `uv run ruff check .`, `uv run pytest -v` и `docker build --tag tg-transcribe:ci-local .`.
3. Создайте коммит, отправьте ветку в GitHub и откройте Pull Request.
4. После успешных CI-проверок выполните merge в `main`.
5. Проверьте один новый deployment в Coolify и логи ресурса `tg-transcribe`.

Файлы не копируются вручную с локального ПК на сервер через `scp` или `rsync`.

### Server diagnostics

Серверный контекст Orca `tg-transcribe — сервер` используется для диагностики. Активный production определяется меткой Coolify:

```bash
docker ps --filter 'label=coolify.resourceName=tg-transcribe' --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'
```

До любой операции подтвердите, что контейнер принадлежит ресурсу Coolify `tg-transcribe`. Не запускайте отдельный Compose-проект из `/home/atom/tg-transcribe`: это может создать второй экземпляр бота.

### Secrets and data

`.env` хранится только в Coolify environment. Именованные volumes из `docker-compose.coolify.yml` сохраняются между обычными deployments. Никогда не используйте `docker compose down -v`.

### Rollback

Откат выполняется в Coolify через историю deployments: выберите последнюю рабочую ревизию и запустите redeploy. Не используйте `docker-compose.prod.yml` параллельно активному Coolify-ресурсу.

## Лицензия

MIT.
