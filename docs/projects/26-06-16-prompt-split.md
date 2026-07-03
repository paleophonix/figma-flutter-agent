# ТЗ: Prompt Split — расцепление developer-промта на три слоя

> Статус: v1.0 — план миграции
> Дата: 2026-06-16
> Источник: аудит соответствия проекта заявленным принципам (codebase-wide, 712 файлов src/).
> Цель: разделить промт-конституцию на инвариантный, чужой и проектный слой, убрав из активной цепочки правила несуществующего фреймворка.

---

# 0. Сводка

## 0.1. Проблема

Аудит показал: `.claude/prompts/developer.md` наполовину описывает **другой проект** —
агентный фреймворк *Junction / Celestial*. Грепом по `src/` подтверждено **0 упоминаний**
следующих сущностей:

```text
dependency-injector      JunctionAgent        AgentService
core.errors.JunctionError core.configs/        core.agents.basic.agent
CELESTIAL_ (env-префикс)  core/logging_setup.py main.acdp.md
```

Реальный проект использует свою архитектуру: детерминированный компиляторный пайплайн,
исключение `FigmaFlutterError`, конфиг в `config/settings.py` без префикса, boot Loguru в
`figma_flutter_agent/logging_setup.py`. Промт, который наполовину врёт про архитектуру,
дезориентирует любого исполнителя (агента или человека), сверяющегося по нему.

## 0.2. Цель

Расцепить промт на три независимых слоя так, чтобы:

```text
активная цепочка CLAUDE.md = только применимые правила
чужой фреймворк = изолированный референс, вне активной цепочки
проектные конвенции = подтверждены живым кодом, не выдуманы
```

## 0.3. Результат

```text
.claude/prompts/developer-common.md   — инвариант команды (любой Python/LLM-проект)
.claude/prompts/developer-ffa.md      — конвенции figma-flutter-agent (реальные сущности)
docs/projects/prompt-split/junction-reference.md — Junction/Celestial, как референс
CLAUDE.md                             — грузит common + ffa, не грузит junction
developer.md                          — удалён после миграции
```

---

# 1. Скоуп

## 1.1. В скоупе

- Реорганизация текста `developer.md` (полная редакция L3/L4, включая секции
  Module Size & Workspace Hygiene, Structured Output, MCP Observability, grep-mcp).
- Замена выдуманных сущностей в проектном слое на подтверждённые кодом.
- Перемонтирование `@`-импортов в `CLAUDE.md`.

## 1.2. Не в скоупе

```text
изменение кода src/ (это документация, не рефактор)
правка project-bible.md, karpathy.md, anti-patching.md, debug-common.md (отдельные слои)
закрытие реальных нарушений из аудита (Pass-импорт, размер модулей, logs/renders_GARBAGE)
```

Последнее ведётся отдельными задачами; данное ТЗ — только про промт.

---

# 2. Принцип распределения

Каждый пункт исходного промта относится ровно к одной корзине по правилу:

| Критерий                                                        | Корзина  |
| --------------------------------------------------------------- | -------- |
| Верно для любого нашего проекта, не зависит от стека репозитория | COMMON   |
| Завязано на сущность/путь/библиотеку, которых нет в этом коде    | JUNCTION |
| Описывает конкретную сущность этого репозитория                 | FFA      |

Спорные пункты (например MCP Observability) относятся в COMMON, если инструмент
универсален, и в FFA, если он привязан к конкретному модулю репозитория
(`observability/loki_sink.py`).

---

# 3. Маппинг пунктов → корзины

## 3.1. COMMON (developer-common.md)

```text
Style & Clean Code (Ruff/Black, SOLID/DRY/KISS, dead code, magic numbers,
  validate-at-boundary, trust types, clear TODO)
Docstrings & Comments (English-only, Google Style)
Living Documentation (README per module: Purpose / Usage / LLM Context)
Logging (Loguru global, English, no emoji, logger.exception, logger.bind,
  ban stdlib logging, no logger via DI)
Error Handling (raise custom exc, raise...from, log-before-recovery, targeted except)
Configuration (Pydantic BaseSettings, init-once, no hardcoded secrets, boundary access)
Module Size (300-line split) + Workspace Hygiene (.temp/, no scratch litter)
Structured Output (response_format json_schema, strict:true, no raw json.loads primary)
External Code Discovery (grep-mcp)
MCP Observability (Grafana/Loki/PostHog, read-only default)
```

## 3.2. JUNCTION (junction-reference.md — вне активной цепочки)

```text
Architecture & DI: dependency-injector, JunctionAgent, AgentService, ABC-only,
  core.agents.basic.agent, main.acdp.md, inward-arrows к core.domains
Error base: core.errors.JunctionError (наследование + Raises-маппинг)
Configuration: core/configs/, core.configs.app.AppSettings, префикс CELESTIAL_, __-nesting
Logging boot: core/logging_setup.py
```

## 3.3. FFA (developer-ffa.md — замена выдуманного на реальное)

| Аспект           | Junction (было)                | figma-flutter-agent (стало)                         |
| ---------------- | ------------------------------ | --------------------------------------------------- |
| Базовое исключение | `core.errors.JunctionError`   | `figma_flutter_agent.errors.FigmaFlutterError`      |
| Иерархия ошибок  | —                              | `ParseError`/`PipelineError`/`LlmError`/`GenerationError`/`PlannedDartGraphError`/… |
| Конфиг           | `core/configs/`, `AppSettings` | `config/settings.py`, `Settings(BaseSettings)`      |
| Env-префикс      | `CELESTIAL_…__…`               | без префикса, явные алиасы (`FIGMA_ACCESS_TOKEN`, …) |
| Секреты          | —                              | `SecretStr` + `redaction.py`                        |
| Конфиг-доступ    | Constructor DI                 | `load_settings()` только на границе; запрет в `generator/`,`parser/` |
| Logging boot     | `core/logging_setup.py`        | `figma_flutter_agent/logging_setup.py` (+`observability/loki_sink.py`) |
| Архитектура      | DI-контейнер, JunctionAgent    | компиляторный пайплайн + контексты `IrEmitContext`/`PassContext` |
| Канон правил     | `main.acdp.md`                 | `project-bible.md` (anti-patching, conservation, fidelity tiers) |
| Имена файлов     | одно слово / дефис             | `snake_case` обязателен (дефис ломает import)       |
| Размер модулей   | жёсткий 300                    | 300 для нового; крупные файлы — признанный долг bible |

---

# 4. Эпики

> Ворота: эпик не стартует без DoD предыдущего.

## E1. developer-common.md

```text
1. Создать .claude/prompts/developer-common.md из корзины 3.1.
2. Сохранить формулировки исходника; убрать любые ссылки на Junction-сущности.
   verify: grep -E "Junction|CELESTIAL|dependency-injector|core\.configs|core\.agents"
           .claude/prompts/developer-common.md  → 0 совпадений
```

## E2. junction-reference.md

```text
1. Создать docs/projects/prompt-split/junction-reference.md из корзины 3.2.
2. Шапка-дисклеймер: "Референс другого фреймворка. НЕ применяется в figma-flutter-agent.
   Не подключать в CLAUDE.md."
   verify: файл существует, не импортируется ни из одного @-инклуда CLAUDE.md
```

## E3. developer-ffa.md

```text
1. Создать .claude/prompts/developer-ffa.md из корзины 3.3 (таблица замен).
2. Каждую реальную сущность сверить с живым кодом перед фиксацией (ASK THE CODE):
   errors.py, config/settings.py, logging_setup.py, redaction.py.
   verify: каждый упомянутый путь/символ резолвится грепом в src/
```

## E4. Перемонтировать CLAUDE.md

```text
1. Заменить строку:
     @.claude/prompts/developer.md
   на:
     @.claude/prompts/developer-common.md
     @.claude/prompts/developer-ffa.md
2. Удалить .claude/prompts/developer.md.
   verify: rg "developer\.md" CLAUDE.md  → 0; оба новых файла присутствуют
```

## E5. Верификация активной цепочки

```text
1. Собрать все @-инклуды CLAUDE.md, проверить отсутствие Junction-символов в них.
   verify: для каждого активного промт-файла
           grep -E "Junction|CELESTIAL|dependency-injector" → 0
2. Проверить, что junction-reference.md НЕ попал в активную цепочку.
3. Прогнать любую короткую команду агента — убедиться, что контекст грузится без ошибок @-резолва.
```

---

# 5. DoD проекта

```text
CLAUDE.md грузит developer-common.md + developer-ffa.md
активная промт-цепочка: 0 ссылок на несуществующие сущности
junction-reference.md изолирован в docs/, помечен дисклеймером
developer.md удалён
каждый путь/символ в developer-ffa.md подтверждён живым кодом
```

---

# 6. Открытые вопросы (решения за продактом)

| #  | Вопрос                                                              | Дефолт в этом ТЗ                          |
| -- | ------------------------------------------------------------------ | ----------------------------------------- |
| Q1 | Junction-слой: сохранить как референс или удалить совсем?           | Сохранить в `docs/` (дёшево, обратимо)    |
| Q2 | Имена файлов: `developer-common` / `developer-ffa`?                 | Да, по дефис-конвенции для не-импортируемых |
| Q3 | Удалять `developer.md` или оставить тонким редиректом?              | Удалить (CLAUDE.md перемонтируется)        |
| Q4 | Брать полную редакцию L3/L4 (секции 8–11) или текущие 92 строки?    | Полную (расширенную) редакцию             |

При несогласии с дефолтом — правка точечная, структура эпиков не меняется.

---

# 7. Оценка

```text
E1  developer-common.md     ~20 мин
E2  junction-reference.md   ~10 мин
E3  developer-ffa.md        ~25 мин (со сверкой по коду)
E4  CLAUDE.md remount       ~5 мин
E5  верификация             ~10 мин
ИТОГО                       ~1.5 часа, один проход, без правок кода
```
