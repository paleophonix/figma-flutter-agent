# Записка: связывание через uvicorn + lifespan и внедрение через Depends

**Проект:** figma-flutter-agent
**Дата:** 2026-06-16
**Статус:** техническая записка (спутник к `control-plane-api.md`)
**Назначение:** ответить на два вопроса по реализации — можно ли связать компоненты через `lifespan` и использовать ли `Depends`. Короткий ответ: да и да, оба механизма уже присутствуют в коде; ниже — как именно и чего не хватает.

> Ссылки ведут на пакет `src/control_panel/` (бывший `discord_bot`).

---

## 1. Что уже есть

### 1.1. uvicorn → app → lifespan → app.state

Запуск сервера и единая точка инициализации уже реализованы:

- [main.py](../../../src/control_panel/main.py) — `uvicorn.run("control_panel.api.app:app", host, port)`.
- [api/app.py](../../../src/control_panel/api/app.py) — `@asynccontextmanager async def lifespan(app)` поднимает все зависимости (settings, engine, session factory, store, ARQ-пул, Redis, бот) и публикует их в `app.state`:

```python
app.state.settings = settings
app.state.store = store
app.state.bot = bot
app.state.arq_pool = arq_pool
app.state.engine = engine
```

**Вывод:** `lifespan` уже выступает composition root. ARQ-пул, БД и store поднимаются независимо от бота — они и есть «машина выполнения». Бот — лишь один из потребителей.

### 1.2. Depends: функции есть, но вызываются вручную

В [api/deps.py](../../../src/control_panel/api/deps.py) объявлены провайдеры (`get_settings`, `get_store`, `get_bot`, `get_arq_pool`, `get_redis`), читающие `request.app.state`. Роуты `/v1` и ops (`/ready`, `/metrics`) используют `Depends()`; `internal` / `webhooks` по-прежнему вызывают `get_x(request)` императивно — см. [api/routers/internal.py](../../../src/control_panel/api/routers/internal.py):

```python
async def preview_session(request: Request, ...):
    settings = get_settings(request)   # ручной вызов
    store = get_store(request)
```

Это рабочий, но «полу-DI» стиль: зависимость не декларируется в сигнатуре, не участвует в OpenAPI, не переопределяется в тестах через `app.dependency_overrides`.

---

## 2. Принцип

```text
uvicorn  ──запускает──▶  app (FastAPI)
   app  ──владеет──▶  lifespan        # единственный composition root
lifespan ──кладёт──▶  app.state.*     # все долгоживущие ресурсы
 handler ──получает──▶ Depends(get_*) # ресурсы из state, декларативно
```

Правила:
- **Долгоживущие ресурсы** (engine, pool, store, бот) создаются **один раз** в `lifespan`, не в хендлере.
- **Хендлеры** получают их **только** через `Depends`, не через прямой доступ к `request.app.state` и не через повторную загрузку.
- **Тяжёлый компьют** (пайплайн) не живёт ни в `lifespan`, ни в `Depends`, ни в хендлере — он в ARQ-воркере. `Depends` отдаёт ссылку на пул, хендлер делает `enqueue_job`.

---

## 3. Паттерн A — условный старт бота в том же lifespan

Развязка API от Discord не требует второго приложения или второго entrypoint. Достаточно сделать старт бота условным внутри существующего `lifespan`:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings(require_discord_token=False)   # токен опционален
    engine = create_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    store = JobStore(create_session_factory(engine))
    arq_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))

    app.state.settings = settings
    app.state.store = store
    app.state.arq_pool = arq_pool
    app.state.engine = engine

    bot = None
    bot_task = None
    token = settings.discord_bot_token.get_secret_value().strip()
    if settings.yaml.discord.enabled and token:
        bot = DiscordControlBot(settings=settings, store=store, arq_pool=arq_pool)
        register_generate_command(bot)
        register_repo_command(bot)
        bot_task = asyncio.create_task(bot.start(token))
    app.state.bot = bot

    try:
        yield
    finally:
        if bot_task is not None:
            bot_task.cancel()
            with suppress(asyncio.CancelledError):
                await bot_task
        await arq_pool.close()
        await engine.dispose()
```

**Что меняется:** загрузка настроек переходит на `require_discord_token=False`; требование токена переезжает в условие старта бота; `app.state.bot` может быть `None`. Машина (store + pool + engine) поднимается всегда — один и тот же uvicorn-процесс работает и как Discord-хост, и как чистый API.

---

## 4. Паттерн B — `Depends` вместо ручного `get_x(request)`

Для нового `/v1` API провайдеры из `deps.py` используются декларативно. Сами провайдеры менять не нужно — они уже читают `app.state`:

```python
# было (полу-DI, internal.py)
async def handler(request: Request, ...):
    store = get_store(request)

# стало (для /v1)
async def handler(store: JobStore = Depends(get_store), ...):
    ...
```

Выгода: зависимость видна в сигнатуре, попадает в OpenAPI, переопределяется в тестах через `app.dependency_overrides[get_store] = ...` без поднятия реальной БД.

Существующие роутеры (`internal`, `webhooks`) переводить на `Depends` в рамках развязки **не обязательно** — они работают; это опциональная унификация, не блокер.

---

## 5. Паттерн C — auth через цепочку `Depends`

`Depends` композируется: одна зависимость зависит от другой. Аутентификация по API-ключу ложится поверх `get_settings` без обращения к `request` в хендлере:

```python
# deps.py
async def require_principal(
    x_api_key: str = Header(...),
    settings: DiscordBotSettings = Depends(get_settings),
) -> str:
    """Resolve principal from X-API-Key or reject."""
    principal = match_api_key(settings, x_api_key)   # sha256 + secrets.compare_digest
    if principal is None:
        raise HTTPException(status_code=401, detail="unauthorized")
    return principal

# routers/jobs.py
@router.post("/v1/jobs", status_code=202)
async def create_job_endpoint(
    body: CreateJobRequest,
    principal: str = Depends(require_principal),
    store: JobStore = Depends(get_store),
    pool: ArqRedis = Depends(get_arq_pool),
) -> CreateJobResponse:
    job = await store.create_job(origin="api", principal=principal, ...)
    await pool.enqueue_job("run_generation_job", job.id)
    return CreateJobResponse(job_id=job.id, status=job.status)
```

Паттерн сравнения секрета берётся из существующего кода — [internal.py](../../../src/control_panel/api/routers/internal.py) уже использует `secrets.compare_digest`.

---

## 6. Анти-паттерны (запрещено)

- **`load_settings` / `load_discord_bot_settings` внутри хендлера или `Depends`-провайдера.** Настройки грузятся один раз в `lifespan`; провайдер отдаёт их из `app.state`. Повторная загрузка ломает детерминированный replay (см. project-bible §6).
- **Тяжёлая работа в `Depends`.** Зависимость должна быть дешёвой (достать ресурс, проверить ключ). Никаких сетевых вызовов к Figma, запуска Flutter, `dart analyze` — это ARQ.
- **Синхронный `run_pipeline` в хендлере.** Хендлер только `create_job` + `enqueue_job` + `202`.
- **Создание ресурсов (engine/pool) в хендлере или per-request.** Только в `lifespan`, одним экземпляром на процесс.
- **Прямой `request.app.state.x` в новых `/v1` хендлерах.** Через `Depends(get_x)`, иначе теряется тестируемость и OpenAPI.

---

## 7. Чеклист внедрения

- [x] `lifespan` грузит настройки с `require_discord_token=False`.
- [x] Старт бота обёрнут в `if discord.enabled and token`; `app.state.bot` допускает `None`.
- [x] `get_bot` возвращает `DiscordControlBot | None`; потребители корректны при `None`.
- [x] `/v1` и ops-хендлеры берут зависимости только через `Depends`.
- [x] `require_principal` / `require_metrics_token` композируются поверх `Depends(get_settings)`.
- [x] API-тесты `/v1` используют `app.dependency_overrides` без Postgres/Redis (`tests/control_panel/test_v1_jobs_api.py`).
- [x] Ни один `Depends`-провайдер не вызывает `load_settings` и не делает тяжёлой работы (rate-limit — только Redis INCR).
