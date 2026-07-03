# ТЗ: Публичный REST API control panel (развязка с Discord)

**Проект:** figma-flutter-agent
**Дата:** 2026-06-16
**Статус:** черновик к исполнению
**Основание:** разведка возможностей «максимальной интеграции FastAPI». Вывод: FastAPI уже присутствует как служебный хост; ценность — превратить его в первоклассный публичный интерфейс к уже построенной машине джоб, переиспользуя существующую сантехнику (Postgres + ARQ + Redis).

---

## 1. Резюме

Сейчас FastAPI обслуживает только внутренние нужды (health, вебхуки VCS, коллбэки воркера). Единственный пользовательский триггер генерации — Discord-команда `/generate`. Машина выполнения джоб (создание в БД → постановка в ARQ → коллбэки → нотификация) уже готова и не зависит от природы фронта, **кроме одного**: джоба намертво прибита к Discord на уровне схемы данных и резолва проекта.

ТЗ описывает развязку этой связи и вынос генерации в публичный REST API, доступный извне (CI, веб-морда, плагины), без переписывания ядра компилятора.

### Порядок (по убыванию ценности и зависимостям)

1. **E1** — развязать запуск бота от приложения FastAPI.
2. **E2** — ввести абстракцию `origin`/`principal` в схему джобы и резолв проекта.
3. **E3** — публичный REST jobs API (`/v1/jobs`).
4. **E4** — аутентификация по API-ключам.
5. **E5** — OpenAPI-клиент и ops-эндпоинты (`/ready`, `/metrics`).

### Не-цели (жёсткие границы)

- **Компилятор не переносится внутрь обработчика запроса.** Пайплайн остаётся в ARQ-воркере. REST-эндпоинт только создаёт джобу и ставит её в очередь — ровно как Discord-команда. Запуск `run_pipeline` синхронно в хендлере запрещён (повесит сервер; нарушает разделение I/O-слоя и компьюта).
- Не строим веб-фронтенд в рамках этого ТЗ. Только бэкенд-контракт + OpenAPI, на котором фронт можно собрать отдельно.
- Не трогаем ядро `figma_flutter_agent/` (parser, generator, pipeline). Работа изолирована в пакете `control_panel/` и схеме БД.

---

## 2. Текущее состояние (сверено с кодом)

| Факт | Источник |
|------|----------|
| FastAPI-приложение собирается фабрикой, в `lifespan` **всегда** стартует Discord-бот | [api/app.py:30-66](../../../src/control_panel/api/app.py) |
| Публичные роутеры: `health`, `webhooks` (github/gitlab), `internal` (коллбэки воркера) | [api/app.py:67-69](../../../src/control_panel/api/app.py) |
| `load_control_panel_settings(require_discord_token=True)` по умолчанию; воркер грузит с `False` | [config/load.py:102-134](../../../src/control_panel/config/load.py), [workers/tasks.py:151](../../../src/control_panel/workers/tasks.py) |
| `create_job` требует `discord_user_id` и `discord_channel_id`; в схеме БД оба `NOT NULL` | [db/store.py:115-150](../../../src/control_panel/db/store.py), [db/models.py:23-24](../../../src/control_panel/db/models.py) |
| Резолв проекта/сэндбокса завязан на `discord_user_id` | [services/projects.py:60-68](../../../src/control_panel/services/projects.py) |
| Постановка в очередь — `pool.enqueue_job("run_generation_job", job_id)`, природа фронта неважна | [bot/commands/generate.py:99-107](../../../src/control_panel/bot/commands/generate.py) |
| Диспетчер событий воркера полностью завязан на Discord (каждая ветка зовёт `bot.send_*`) | [services/events.py:25-84](../../../src/control_panel/services/events.py) |
| Авторизация — только Discord (роли/allowlist) | [bot/access.py:10-31](../../../src/control_panel/bot/access.py) |
| Секреты/бинды живут в `InternalConfig`; `DiscordBotSettings` — `frozen` | [config/models.py:181-221](../../../src/control_panel/config/models.py) |
| ARQ регистрирует `run_generation_job`, `publish_job`, `feedback_issue_job` | [workers/settings.py:15](../../../src/control_panel/workers/settings.py) |

**Вывод:** ~80% машины переиспользуемо как есть. Блокеры развязки — три: (1) бот в `lifespan`, (2) Discord-поля джобы `NOT NULL` + резолв по Discord-id, (3) диспетчер нотификаций знает только Discord.

---

## 3. Целевая архитектура

```text
            ┌──────────────── FastAPI (тонкий async I/O слой) ────────────────┐
            │  /health  /ready  /metrics                                       │
 Discord ──▶│  /webhooks/*  /internal/*           (служебные, как сейчас)      │
            │  /v1/jobs  POST/GET/list  [+SSE]    (НОВОЕ: публичный API)       │
 CI / web ─▶│  auth: API-key dependency           (НОВОЕ)                      │
            │  bot стартует в lifespan ТОЛЬКО если discord.enabled && токен    │
            └──────────────────────────┬──────────────────────────────────────┘
                                        │ create_job(origin, principal) + enqueue
                                        ▼
                          Postgres (jobs)  ◀──▶  ARQ + Redis (run_pipeline)
                                        │
                                        ▼ коллбэк /internal/jobs/{id}/events
                       origin-aware dispatch:
                         discord → bot.send_*      (как сейчас)
                         api     → no-op (статус уже в БД; клиент поллит/SSE)
```

Ключ: REST — **ещё одна дверь** к той же машине, а не вторая машина.

---

## 4. Инварианты и анти-паттерны

- **Настройки входят на границе.** Никаких `load_settings`/`load_control_panel_settings` внутри хендлеров доменной логики. Конфиг кладётся в `app.state` в `lifespan` (как сейчас) и достаётся через DI (`api/deps.py`).
- **Компьют — в ARQ.** Хендлер создаёт джобу + `enqueue_job`, отвечает `202 Accepted` с `job_id`. Никаких блокирующих вызовов пайплайна.
- **`origin` — типизированный факт джобы**, не угадывается. Каждая джоба создаётся с явным `origin ∈ {discord, api}`.
- **Идемпотентность диспетчера.** `dispatch_job_event` для `origin=api` — явный no-op, а не падение при отсутствии Discord-сообщения.
- **Никаких Discord-заглушек.** Запрещено создавать API-джобу с фиктивными `discord_user_id=0`, чтобы пролезть сквозь `NOT NULL`. Поля делаются nullable честной миграцией (E2).
- **Имя пакета `control_panel` становится неточным**, когда он хостит общий API. Переименование (`control_plane`) — вне скоупа этого ТЗ (большой diff, отдельная задача). Зафиксировать как долг.

---

## 5. Эпики

### E1 — Развязка запуска бота от FastAPI (P0)

**Цель:** приложение FastAPI можно поднять в режиме «только API», без Discord-токена и без старта бота.

**Задачи:**
1. Добавить флаг `discord.enabled: bool = True` в `DiscordSectionConfig` ([config/models.py:81](../../../src/control_panel/config/models.py)).
2. В `lifespan` ([api/app.py:30](../../../src/control_panel/api/app.py)) стартовать бота только если `settings.yaml.discord.enabled` **и** токен непустой. Иначе `app.state.bot = None`, ARQ-пул и store поднимаются как обычно.
3. Загрузку настроек в `lifespan` перевести на `require_discord_token=False`; требование токена перенести в условие старта бота (а не в загрузку).
4. `api/deps.py:get_bot` — вернуть `DiscordControlBot | None`; потребители (`webhooks`, `internal`) обязаны корректно вести себя при `None` (для api-origin Discord-ветки не вызываются — см. E2/E3).

**DoD:** `uvicorn control_panel.api.app:app` поднимается с `discord.enabled: false` без `control_panel_TOKEN`; `/health` отвечает; джоба-API (после E3) работает; существующий Discord-режим не сломан (регрессионный тест на оба режима `lifespan`).

---

### E2 — Абстракция `origin`/`principal` (P0)

**Цель:** джоба перестаёт быть Discord-специфичной на уровне схемы и резолва проекта.

**Задачи:**
1. **Схема БД** (`GenerationJobRow`, [db/models.py](../../../src/control_panel/db/models.py)):
   - добавить `origin: str NOT NULL DEFAULT 'discord'` (`discord | api`);
   - добавить `principal: str | None` (идентификатор внешнего клиента для api-origin);
   - сделать `discord_user_id`, `discord_channel_id` **nullable**.
2. **Миграция Alembic** в `alembic/versions/` (новая ревизия): add `origin`, `principal`; alter Discord-колонок в nullable; backfill `origin='discord'` для существующих строк.
3. **JobStore** ([db/store.py](../../../src/control_panel/db/store.py)):
   - `create_job` — принять `origin: str`, `principal: str | None`, сделать Discord-id опциональными;
   - добавить `list_jobs_by_principal(principal, *, limit, offset)` для api-листинга;
   - `GenerationJob` dataclass — добавить поля `origin`, `principal`.
4. **Резолв проекта по принципалу** ([services/projects.py](../../../src/control_panel/services/projects.py)):
   - ввести `resolve_sandbox_dir_for_principal(settings, principal, repo_key)` и `resolve_active_repo_key_for_principal(...)`, читающие маппинг из новой `ApiConfig` (см. E4), а не из Discord-preferences. Discord-функции не трогаем — обе ветви сосуществуют.
5. **Диспетчер событий** ([services/events.py:25](../../../src/control_panel/services/events.py)):
   - в начале `dispatch_job_event` — `if job.origin == "api": return` (статус уже персистится воркером в БД; нотификация — забота API-клиента через поллинг/SSE). Логировать на debug.

**DoD:** можно создать джобу с `origin='api'`, `discord_user_id=None`; воркер отрабатывает её без обращения к Discord; `dispatch_job_event` для неё — no-op без исключений; миграция применяется и откатывается; существующие Discord-джобы читаются (`origin='discord'`).

---

### E3 — Публичный REST jobs API (P1)

**Цель:** внешний клиент запускает генерацию и следит за статусом по HTTP.

**Новый роутер** `api/routers/jobs.py`, подключить в [api/app.py](../../../src/control_panel/api/app.py):

| Метод | Путь | Назначение |
|-------|------|------------|
| `POST` | `/v1/jobs` | Создать джобу: тело `{figma_url, repo_key?, mode?, target_file?}`. Валидация `figma_url` через `parse_figma_url`. Резолв проекта по принципалу (E2). `create_job(origin='api', principal=...)` → `enqueue_job("run_generation_job", job_id)` → `202 {job_id, status}`. |
| `GET` | `/v1/jobs/{job_id}` | Статус и метаданные джобы. Возврат — Pydantic-модель ответа (НЕ сырой ORM-row). `404` если чужой принципал/нет джобы. |
| `GET` | `/v1/jobs` | Листинг джоб принципала (`list_jobs_by_principal`, пагинация). |
| `GET` | `/v1/jobs/{job_id}/artifacts` | Отдать zip артефактов (`artifact_zip_path`), `FileResponse`; `409` если ещё не `preview_ready`. |
| `GET` | `/v1/jobs/{job_id}/events` | *(опционально)* SSE-поток смены статуса (поллинг БД/Redis). Может уехать в отдельную итерацию. |

**Требования:**
- Запросы/ответы — отдельные Pydantic-схемы в `api/schemas.py` (валидация на границе; не отдавать ORM наружу).
- Хендлеры тонкие: валидация → resolve → store → enqueue → ответ. Доменная логика создания джобы вынесена в `services/jobs.py` (`enqueue_generation`), чтобы её разделяли Discord-команда и REST (DRY).
- Рефактор: текущий [bot/commands/generate.py:66-107](../../../src/control_panel/bot/commands/generate.py) переключить на тот же `services/jobs.enqueue_generation` (origin='discord'). Поведение Discord не меняется.

**DoD:** `POST /v1/jobs` с валидным `figma_url` ставит джобу в очередь и возвращает `202`; воркер генерирует; `GET /v1/jobs/{id}` показывает переход `created → pipeline_running → preview_ready`; `GET .../artifacts` отдаёт zip; невалидный URL → `422`; чужая джоба → `404`.

---

### E4 — Аутентификация по API-ключам (P1)

**Цель:** публичные `/v1/*` закрыты; принципал извлекается из ключа.

**Задачи:**
1. Новая `ApiConfig` в YAML ([config/models.py](../../../src/control_panel/config/models.py)):
   ```yaml
   api:
     enabled: false
     keys:
       <principal>:
         key_hash: "<sha256>"      # хеш, не сырой ключ
         project_key: "<workspace>" # проект в workspace_root
         active_repo_key: "<repo>"
   ```
   Подключить в `DiscordBotYamlConfig`.
2. DI-зависимость `api/deps.py:require_principal(x_api_key: str = Header(...))` — `sha256` ключа, `compare_digest` по таблице, возврат `principal` или `401`. Паттерн взять из [api/routers/internal.py:32](../../../src/control_panel/api/routers/internal.py) (`secrets.compare_digest`).
3. Все `/v1/*` хендлеры зависят от `require_principal`; джоба создаётся с этим принципалом; листинг/чтение скоупятся по нему.
4. Ключи только из конфигурации/env, не хардкод. Хранить хеш, не сырой ключ.

**DoD:** запрос без/с неверным `X-API-Key` → `401`; с верным — принципал в логах (`logger.bind`) и в джобе; клиент A не видит джобы клиента B.

---

### E5 — OpenAPI-клиент и ops (P2)

**Задачи:**
1. Описать `summary`/`description`/`response_model` на всех `/v1/*` — FastAPI отдаёт OpenAPI/Swagger даром. Зафиксировать, что схема — контракт для будущего фронта/плагина (можно генерить TS-клиент).
2. `/ready` — readiness: проверить живость Postgres (тривиальный `SELECT 1`) и Redis (`ping`); `503` если что-то лежит. Отделить от `/health` (liveness).
3. *(опционально)* `/metrics` — Prometheus (счётчики джоб по статусам через `list_jobs_by_status`). Только при наличии прод-мониторинга; иначе park.

**DoD:** `/docs` показывает `/v1/*` с типами; `/ready` краснеет при выключенном Redis/Postgres.

---

## 6. Миграция БД (сводно)

Новая ревизия Alembic в `alembic/versions/` (родитель — текущий head):
- `ADD COLUMN origin VARCHAR(16) NOT NULL DEFAULT 'discord'`
- `ADD COLUMN principal VARCHAR(128) NULL`
- `ALTER discord_user_id, discord_channel_id → NULL`
- backfill не нужен (default покрывает существующие строки)
- `downgrade`: обратные операции, без потери данных Discord-джоб

---

## 7. Безопасность

- API-ключи: хранить sha256-хеш, сравнение `compare_digest`, передача в `X-API-Key`.
- `figma_url` валидируется `parse_figma_url` до любой работы (как в Discord-команде).
- `principal` скоупит чтение/листинг/артефакты — нет горизонтального доступа.
- Артефакты отдаются только владельцу-принципалу; путь не строится из пользовательского ввода.
- Rate-limit на `POST /v1/jobs` — желателен (например, через Redis-счётчик), но вне P1; зафиксировать как долг.

---

## 8. Тестирование

- E1: тест `lifespan` в обоих режимах (`discord.enabled` true/false) — бот стартует/не стартует, API живой.
- E2: тест миграции (upgrade/downgrade); `create_job(origin='api')`; `dispatch_job_event` no-op для api-origin.
- E3: API-тесты через `httpx.AsyncClient` + `respx`/мок ARQ-пула — `POST` ставит в очередь, `GET` отдаёт статус, скоупинг `404`.
- E4: `401` без ключа, `200` с ключом, изоляция принципалов.
- Маркер pytest `control_plane` уже есть ([pyproject.toml:102](../../../pyproject.toml)); новые тесты — под ним.
- Регрессия: существующие Discord-тесты зелёные (поведение бота не изменилось).

---

## 9. Порядок исполнения и грубая оценка

| Шаг | Эпик | Оценка | verify |
|-----|------|--------|--------|
| 1 | E1 развязка бота | ~0.5 дня | поднять api-only, `/health` ok, Discord-режим цел |
| 2 | E2 схема + миграция + резолв | ~1.5 дня | миграция up/down, api-джоба проходит воркер |
| 3 | E3 REST jobs API + `services/jobs` | ~2 дня | POST→202, GET статус, artifacts zip |
| 4 | E4 API-ключи | ~1 день | 401/200, изоляция принципалов |
| 5 | E5 OpenAPI + `/ready` | ~0.5 дня | `/docs`, `/ready` краснеет |

Итого ~5.5 человеко-дней до работающего публичного API. SSE и `/metrics` — отдельная итерация.

---

## 10. Риски и анти-паттерны

- **Соблазн запустить пайплайн в хендлере** ради «простоты» — запрещено (см. §4). Только enqueue.
- **Discord-заглушки** (`discord_user_id=0`) вместо честной nullable-миграции — запрещено.
- **Утечка ORM наружу** — отвечаем только Pydantic-схемами.
- **Дрейф двух путей создания джобы** — Discord-команда и REST обязаны идти через общий `services/jobs.enqueue_generation`, иначе разойдутся.
- **`load_settings` внутри хендлера** — запрещено; конфиг через `app.state`/DI.
- **Долги к фиксации:** переименование пакета `control_panel` → `control_plane`; rate-limit на `POST /v1/jobs`.

---

## 11. Делегирование сабагенту

**Можно** отдавать поэпично (E1→E5 строго по порядку, гейт DoD предыдущего эпика). Тип: `general-purpose`.

**Промпт сабагенту (скопировать):**

> Выполни `docs/projects/control-plane-api/control-plane-api.md` строго по эпикам E1→E5, не начиная следующий без зелёного DoD предыдущего. Не коммить и не пушить. Ядро `figma_flutter_agent/` не трогать. Запрещено запускать пайплайн в обработчике запроса — только `enqueue_job`. Конфиг — через `app.state`/DI, не `load_settings` в хендлере. После каждого эпика — verify из раздела «Порядок исполнения». Если миграция Alembic не откатывается — остановись и сообщи, не патчь схему руками.

**Вне скоупа сабагента:** ядро компилятора; переименование пакета; веб-фронтенд; `/metrics`; rate-limit.
