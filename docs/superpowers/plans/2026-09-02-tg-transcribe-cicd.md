# tg-transcribe CI/CD и Coolify Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Перевести `tg-transcribe` на единый поток `GitHub -> CI -> Coolify -> production`, убрать зависимость от offline self-hosted runner и сохранить данные/секреты сервиса.

**Architecture:** Локальная папка `C:\Projects\Серваки\tg-transcribe` остаётся местом разработки, GitHub `Progery222/tg-transcribe` — единственным источником кода, а Coolify — единственным контроллером production-развертывания. GitHub Actions выполняет lint, тесты и проверочную Docker-сборку, но не подключается к серверу и не публикует production через SSH или GHCR.

**Tech Stack:** Python 3.12, `uv`, Ruff, Pytest, Docker/Docker Compose, GitHub Actions, GitHub Pull Requests, Coolify, Orca local/server contexts.

**Spec:** `docs/superpowers/specs/2026-09-02-tg-transcribe-cicd-design.md`

## Global Constraints

- Исходный репозиторий: `Progery222/tg-transcribe`.
- Локальный корень исходников: `C:\Projects\Серваки\tg-transcribe`.
- Production-ресурс Coolify: проект `telegram-bots`, ресурс `tg-transcribe`.
- Production Compose-файл: `docker-compose.coolify.yml`.
- Production-ветка: `main`.
- GitHub Actions запускается на `ubuntu-latest`; self-hosted runner не используется.
- `uv sync --frozen`, `uv run ruff check .` и `uv run pytest -v` остаются обязательными CI-проверками.
- `.env`, Telegram-токены, API-ключи, SSH-ключи, cookies и локальные сессии не добавляются в Git.
- Не запускать `docker compose down -v`.
- Не запускать `/home/atom/tg-transcribe/docker-compose.prod.yml` параллельно активному Coolify-ресурсу.
- Изменения в production доставляются только через merge в `main` и Coolify auto-deploy.
- Проект `F:\Projects\FarmTransfer` не изменяется.

---

### Task 1: Подготовить изолированную ветку внедрения

**Files:**
- Read: `C:\Projects\Серваки\tg-transcribe\.git`
- Read: `C:\Projects\Серваки\tg-transcribe\.github\workflows\deploy.yml`
- Read: `C:\Projects\Серваки\tg-transcribe\docs\superpowers\specs\2026-09-02-tg-transcribe-cicd-design.md`

**Interfaces:**
- Consumes: текущая локальная ветка `main` с коммитами `c8858e0` и `74c91b1`, которых ещё нет в `origin/main`.
- Produces: ветка `chore/coolify-ci-only`, содержащая текущее состояние `main` и готовая для Pull Request.

- [ ] **Step 1: Проверить чистоту рабочей директории и положение веток**

    git status --short --branch
    git log --oneline --decorate -5
    git log --oneline origin/main..main

Ожидаемый результат: рабочее дерево чистое, локальная `main` опережает `origin/main` на два согласованных коммита, а удаление или переписывание этих коммитов не выполняется.

- [ ] **Step 2: Просмотреть оба локальных коммита перед включением в PR**

    git show --stat --oneline c8858e0
    git show --stat --oneline 74c91b1
    git diff origin/main..main --stat

Проверить, что `c8858e0` содержит ожидаемое изменение OpenAI-compatible base URL, а `74c91b1` — только согласованную архитектурную спецификацию.

- [ ] **Step 3: Создать feature-ветку без изменения production**

    git branch --list chore/coolify-ci-only
    git switch -c chore/coolify-ci-only

Если ветка уже существует, сначала сравнить её с текущим `main`; существующую ветку не перезаписывать.

**Commit:** Не требуется; ветка создаётся от уже проверенного локального состояния.

---

### Task 2: Превратить GitHub Actions в CI-only workflow

**Files:**
- Modify: `.github/workflows/deploy.yml:1-74`

**Interfaces:**
- Consumes: GitHub `pull_request` и `push` в `main`.
- Produces: jobs с идентификаторами `test` и `docker-build`; оба выполняются на GitHub-hosted runner и не имеют production-доступа.

- [ ] **Step 1: Заменить workflow на следующий точный вариант**

```
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions:
  contents: read

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "0.11.x"
          enable-cache: true

      - name: Install Python
        run: uv python install 3.12

      - name: Install dependencies
        run: uv sync --frozen

      - name: Lint
        run: uv run ruff check .

      - name: Test
        run: uv run pytest -v

  docker-build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: docker/setup-buildx-action@v3

      - name: Validate Coolify Compose file
        run: |
          cp .env.example .env
          docker compose -f docker-compose.coolify.yml config --quiet

      - name: Build Docker image for validation
        uses: docker/build-push-action@v6
        with:
          context: .
          file: ./Dockerfile
          push: false
          tags: tg-transcribe:ci-${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

Этот вариант удаляет `packages: write`, login в GHCR, публикацию `latest`/SHA-образов и job `deploy` на `self-hosted` runner. Временный `.env` создаётся только внутри ephemeral GitHub runner из `.env.example`; production-секреты туда не попадают.

- [ ] **Step 2: Проверить изменение workflow локально**

    git diff -- .github/workflows/deploy.yml
    git diff --check

Убедиться, что в diff нет `self-hosted`, `docker/login-action`, `ghcr.io`, `secrets.GITHUB_TOKEN` с правом записи, `docker compose ... up -d` и SSH-команд.

- [ ] **Step 3: Зафиксировать CI-only workflow отдельным коммитом**

    git add -- .github/workflows/deploy.yml
    git commit -m "ci: make Coolify the only deployment path"

---

### Task 3: Выполнить локальный эквивалент CI

**Files:**
- Read: `pyproject.toml`
- Read: `uv.lock`
- Read: `Dockerfile`
- Read: `.env.example`

**Interfaces:**
- Consumes: workflow из Task 2 и зависимости из `uv.lock`.
- Produces: подтверждение, что локальная версия проходит lint, tests и Docker build до отправки в GitHub.

- [ ] **Step 1: Установить locked-зависимости**

    uv sync --frozen

Ожидаемый результат: команда завершается с кодом `0` и не изменяет `uv.lock`.

- [ ] **Step 2: Выполнить lint и тесты**

    uv run ruff check .
    uv run pytest -v

Ожидаемый результат: Ruff не сообщает ошибок, все тесты завершаются успешно.

- [ ] **Step 3: Собрать Docker-образ без публикации**

    docker build --tag tg-transcribe:ci-local .

Ожидаемый результат: сборка завершается успешно; registry login, push и запуск production не выполняются.

- [ ] **Step 4: Проверить, что проверки не создали изменений**

    git status --short

Ожидаемый результат: нет изменённых `uv.lock`, исходников или production-файлов.

**Commit:** Не требуется, если проверки не исправляли файлы.

---

### Task 4: Обновить README под фактическую Coolify-схему

**Files:**
- Modify: `README.md:187-243`

**Interfaces:**
- Consumes: спецификация и текущая конфигурация `docker-compose.coolify.yml`.
- Produces: актуальная инструкция release, диагностики и rollback, не предлагающая offline runner или ручной production Compose как штатный путь.

- [ ] **Step 1: Заменить старый раздел Deployment**

Удалить описание потока `push -> GHCR -> self-hosted runner`, инструкции установки self-hosted runner, `scp` в `~/tg-transcribe` и штатного запуска `docker-compose.prod.yml`. Вставить следующий смысловой раздел:

~~~markdown
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
docker ps --filter 'label=coolify.resourceName=tg-transcribe' --format 'table {{.Names}}\\t{{.Status}}\\t{{.Image}}'
```

До любой операции подтвердите, что контейнер принадлежит ресурсу Coolify `tg-transcribe`. Не запускайте отдельный Compose-проект из `/home/atom/tg-transcribe`: это может создать второй экземпляр бота.

### Secrets and data

`.env` хранится только в Coolify environment. Именованные volumes из `docker-compose.coolify.yml` сохраняются между обычными deployments. Никогда не используйте `docker compose down -v`.

### Rollback

Откат выполняется в Coolify через историю deployments: выберите последнюю рабочую ревизию и запустите redeploy. Не используйте `docker-compose.prod.yml` параллельно активному Coolify-ресурсу.
~~~

- [ ] **Step 2: Проверить README на устаревшие инструкции**

    rg -n "self-hosted|self-hosted runner|build-and-push|GHCR|scp docker-compose.prod|actions-runner|docker compose down -v" README.md

Допустимо оставить только предупреждение о том, что `docker-compose.prod.yml` — аварийный legacy-путь и `down -v` запрещён. Инструкции штатного deploy через self-hosted runner удалить.

- [ ] **Step 3: Проверить форматирование и зафиксировать документацию**

    git diff --check
    git add -- README.md
    git commit -m "docs: document Coolify deployment workflow"

---

### Task 5: Отправить изменения в GitHub и включить защиту `main`

**Files:**
- External configuration: GitHub repository `Progery222/tg-transcribe`.
- Review: `.github/workflows/deploy.yml`, `README.md`.

**Interfaces:**
- Consumes: feature-ветка `chore/coolify-ci-only` с двумя изменениями workflow и README.
- Produces: Pull Request в `main`, успешные checks `test` и `docker-build`, защита `main` до merge.

- [ ] **Step 1: Отправить feature-ветку в GitHub**

    git push --set-upstream origin chore/coolify-ci-only

Ожидаемый результат: отправляется только feature-ветка; прямой push в `main` не выполняется.

- [ ] **Step 2: Создать Pull Request**

    gh pr create --repo Progery222/tg-transcribe --base main --head chore/coolify-ci-only --title "ci: make Coolify the only deployment path" --body "Switch GitHub Actions to CI-only, remove the offline self-hosted deploy path, and document Coolify as the production controller."

- [ ] **Step 3: Дождаться и проверить оба CI job**

    gh pr checks --repo Progery222/tg-transcribe chore/coolify-ci-only --watch

Ожидаемый результат: `test` и `docker-build` завершаются успешно; job с `self-hosted` или `deploy` отсутствует.

- [ ] **Step 4: Настроить branch protection в GitHub UI**

Открыть `Settings -> Branches -> Branch protection rules -> Add classic branch protection rule` для pattern `main` и включить:

- требование Pull Request перед merge;
- required status checks: `test` и `docker-build`;
- запрет force-push;
- запрет удаления ветки;
- требование актуальной ветки перед merge, если этот пункт доступен.

Для одного владельца репозитория обязательное число approving reviews оставить `0`, чтобы защита требовала PR и CI, но не блокировала работу отсутствием второго ревьюера.

- [ ] **Step 5: Проверить правило до merge**

    gh api repos/Progery222/tg-transcribe/branches/main/protection --jq '{required_status_checks: .required_status_checks.contexts, enforce_admins: .enforce_admins.enabled, required_pull_request_reviews: .required_pull_request_reviews}'

Убедиться, что созданное classic branch protection rule для `main` требует успешные `test` и `docker-build` перед merge.

---

### Task 6: Проверить и настроить источник Coolify без ручного запуска

**Files:**
- External configuration: Coolify project `telegram-bots`, resource `tg-transcribe`.
- Read-only server context: `/home/atom/tg-transcribe`.

**Interfaces:**
- Consumes: GitHub repository and Compose contract from `docker-compose.coolify.yml`.
- Produces: Coolify resource, который следит за `main`, использует правильный Compose-файл и готов к auto-deploy после merge.

- [ ] **Step 1: Зафиксировать текущий production перед изменением настроек**

В UI Coolify открыть ресурс `telegram-bots -> tg-transcribe` и сохранить без секретных значений:

- текущую deployed Git revision;
- source repository и branch;
- Compose file path;
- список имён environment variables без значений;
- имена и типы persistent volumes;
- дату последнего успешного deployment.

- [ ] **Step 2: Сверить ресурс с целевой конфигурацией**

Проверить, что source repository равен `Progery222/tg-transcribe`, branch равен `main`, Compose file равен `docker-compose.coolify.yml`, а build использует `Dockerfile` из репозитория. Если найден второй production-ресурс с тем же Telegram-ботом, остановить работу и сначала выбрать, какой ресурс является единственным владельцем токена.

- [ ] **Step 3: Включить штатный auto-deploy Coolify**

В настройках ресурса включить deploy on push через штатную GitHub integration/webhook Coolify. Не добавлять SSH-ключи GitHub Actions и не запускать `docker compose pull/up` на сервере.

- [ ] **Step 4: Сверить environment keys и volumes без раскрытия секретов**

Сверить только имена переменных с `.env.example`: `BOT_TOKEN`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `BOT_ADMIN_IDS`, `DEFAULT_PROVIDER`, `DEFAULT_MODEL`, параметры `TELEGRAM_BOT_API_*`, `DIGEST_*`, `DB_PATH`, `LOG_*` и `INGEST_*`. Значения не выводить в чат, терминал или GitHub logs. Убедиться, что volumes `bot_data` и `telegram_bot_api_data` не помечены на удаление при redeploy.

- [ ] **Step 5: Не выполнять production deployment до merge PR**

После сохранения настроек убедиться, что ресурс не был перезапущен вручную и в Coolify нет второго параллельного deployment.

---

### Task 7: Выполнить первый контролируемый deployment через merge

**Files:**
- External state: Pull Request и Coolify deployment history.
- Read-only server context: контейнеры с меткой `coolify.resourceName=tg-transcribe`.

**Interfaces:**
- Consumes: успешно проверенный Pull Request и Coolify auto-deploy.
- Produces: один production deployment из merge-коммита `main` с подтверждёнными логами и сохранёнными volumes.

- [ ] **Step 1: Выполнить merge только после зелёного CI**

В Pull Request нажать `Merge` после успешных `test` и `docker-build`. После merge локально обновить сведения без переписывания истории:

    git fetch origin
    git log -1 --oneline origin/main

- [ ] **Step 2: Проверить GitHub Actions после merge**

    gh run list --repo Progery222/tg-transcribe --branch main --limit 5

Ожидаемый результат: для merge-коммита выполняются только `test` и `docker-build`; queued job на `self-hosted` runner отсутствует.

- [ ] **Step 3: Проверить один Coolify deployment**

В Coolify открыть deployment history ресурса `tg-transcribe` и убедиться, что новый deployment связан с merge-коммитом `main`, а не с произвольной feature-веткой. Не запускать второй ручной redeploy поверх уже выполняющегося deployment.

- [ ] **Step 4: Проверить контейнеры и логи read-only командой**

    docker ps --filter 'label=coolify.resourceName=tg-transcribe' --format 'table {{.Names}}\\t{{.Status}}\\t{{.Image}}'

Должны быть видны `bot`, `telegram-bot-api` и завершившийся `init-perms`, относящиеся к одному Coolify compose project. В логах `bot` проверить отсутствие немедленного циклического падения и наличие признаков запуска.

- [ ] **Step 5: Выполнить функциональный smoke test**

Проверить через Telegram: `/start` в ЛС, наличие владельца в `BOT_ADMIN_IDS`, добавление бота в тестовую группу с отключённым Group Privacy и обработку одного короткого голосового сообщения. Для production-данных не выполнять destructive-тесты и не менять рабочие подписки.

---

### Task 8: Зафиксировать rollback и закрыть внедрение

**Files:**
- Modify if needed: `README.md`.
- External state: Coolify deployment history and GitHub branch ruleset.

**Interfaces:**
- Consumes: первый успешный Coolify deployment и его commit SHA.
- Produces: проверяемая эксплуатационная схема с documented rollback и чистым локальным feature-branch.

- [ ] **Step 1: Сохранить идентификатор успешного deployment**

Записать в рабочую заметку или issue номер deployment и полный SHA merge-коммита. Секретные значения environment не записывать.

- [ ] **Step 2: Проверить путь rollback в UI без запуска разрушительного теста**

Открыть Coolify deployment history, убедиться, что предыдущая рабочая ревизия доступна для выбора и redeploy. Не создавать намеренно сломанный production deployment только ради теста отката.

- [ ] **Step 3: Проверить отсутствие старого deploy-пути**

    gh run list --repo Progery222/tg-transcribe --limit 20
    git grep -n "self-hosted\\|build-and-push\\|docker/login-action\\|ghcr.io" -- .github/workflows README.md

Допустимы только исторические упоминания legacy-пути и предупреждения в README; активный workflow не должен содержать SSH-deploy, self-hosted runner или GHCR push.

- [ ] **Step 4: Проверить финальное состояние репозитория**

    git status --short --branch
    git log --oneline --decorate -5
    git diff --check

Ожидаемый результат: feature-изменения закоммичены, рабочее дерево чистое, а GitHub и Coolify используют согласованную историю.

- [ ] **Step 5: Обновить Orca-контексты и правила для следующих задач**

В локальном контексте оставить разработку и Git, в серверном — диагностику и явно запрошенные операции. Для каждой новой задачи начинать с feature-ветки и завершать PR, CI, merge и проверкой одного Coolify deployment.

**Commit:** Если в Task 8 изменён README, создать отдельный коммит `docs: finalize production runbook`; иначе новый коммит не требуется.
