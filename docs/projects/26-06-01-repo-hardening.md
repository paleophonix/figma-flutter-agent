# ТЗ: Приведение репозитория к production-стандартам

**Проект:** figma-flutter-agent
**Дата:** 2026-05-31
**Статус:** черновик к исполнению (можно отдавать сабагенту с ограничениями ниже)
**Основание:** аудит соответствия ТЗ, best practices и production-стандартам (весь репозиторий, безотносительно текущих правок)

---

## Делегирование сабагенту

**Да, отдавать можно** — задача изолирована от продуктового цикла «экран → preview → visual refine», если соблюдать границы ниже.

Рекомендуемый тип: `generalPurpose` или `explore` (для P0.1 — только починка импортов в 7 тестах), отдельный прогон для P1 ruff/mypy.

**Промпт сабагенту (скопировать):**

> Выполни `docs/projects/repo-hardening/repo-hardening.md` в порядке «Порядок исполнения», только пункты, явно разрешённые в разделе «Ограничения». Не коммить и не пушить. Не трогай файлы из списка «Вне скоупа». После каждого P0/P1 — указанная verify-команда. Если `WinError 112` / `No space left on device` — остановись и сообщи про диск, не чини Dart.

### Ограничения (что может помешать текущей работе)

| Риск | Что делать сабагенту |
|------|----------------------|
| Грязное рабочее дерево (много WIP: capture, visual refine, sign_in/sign_up) | **Не** делать массовый `git add` / commit. P0.2 — только отчёт «что ещё untracked», без коммита. |
| Повторный «фикс» уже закрытых багов из `logs/dart-errors/` | **Не** менять `merge_orphaned_text_style`, capture template, `test/capture/` pipeline — это отдельная линия; hardening ≠ разбор старых jsonl. |
| P0.3 пересечётся с незавершённым AST/sidecar WIP | Только если владелец ветки просит явно. Иначе: P0.1 (тесты) + ruff/mypy, **без** крупного рефакторинга `planned_dart.py` / `dart_syntax_repairs.py`. |
| P1 ruff `--fix` на весь `src/` | Делать **после** согласования или только `tests/` + перечисленные файлы с `F821`/`B023`. Иначе огромный diff в тех же модулях, где идёт feature-работа. |
| `signoff.ps1` / полный pytest на забитом диске C: | Перед gate: `Get-PSDrive C` (или `TEMP` на другой диск). При OOM на `copytree` parse gate — не трактовать как падение тестов. |
| P0.2 список untracked | Снимок **устаревает**; перед исполнением заново `git status` и сверка с таблицей P0.2. |

### Вне скоупа сабагента (не трогать без отдельного ТЗ)

- `stages/visual_refine.py`, `validation/golden_capture.py` (кроме P1.3 logging, если файл уже в списке нарушителей и согласовано)
- `generator/templates/capture_screen_test.dart.j2`, `generator/capture_screen_test.py`, `writer.py` / `planned_dart.py` логика capture
- `.ai-figma-flutter.yml`, `.env`, `demo_app/` на диске пользователя
- Рефакторинг монолитов (P3.1), Dev Mode API (TZ.1), смена эвристик interaction (P2.1) — только документ или отдельная задача

### Что сабагенту как раз полезно сделать первым

1. **P0.1** — 7 сломанных тестовых импортов (изолированно, малый diff).
2. **P1.2** — сначала `F821` / `B023` вручную по списку ruff, потом осторожный `--fix`.
3. **P3.2** — уборка debug-файлов в корне (не трогая `src/`).

**Не считать провалом hardening**, если продуктовый wizard ещё падает на `sign_up_and_sign_in` emit — это может быть отдельный продуктовый баг; hardening закрывает repo gate (pytest collect, ruff, mypy, signoff).

---

## 0. Контекст и метрики «как есть»

Все числа получены реальными прогонами инструментов, а не оценкой по конфигу.

| Проверка | Команда | Результат |
|----------|---------|-----------|
| Сбор тестов | `poetry run pytest --co -q` | **7 ошибок сборки**, 1380 тестов собрано |
| Типы | `poetry run mypy src` | **203 ошибки в 46 файлах** (из 211) |
| Линт (src) | `poetry run ruff check src` | **88 ошибок** (58 авто-фикс) |
| Линт (src+tests) | `poetry run ruff check src tests` | **180 ошибок** (117 авто-фикс) |
| Широкие `except` | grep | 21 (часть оправдана, часть без логирования) |
| Секреты в коде | grep | 0 |
| `TODO`/`FIXME` | grep | 0 |
| `import logging` | grep | 0 (правило loguru соблюдено) |

**Definition of Done проекта:** `./scripts/signoff.ps1` (ruff + mypy + demo-signoff + pytest) проходит зелёным без ручных исключений.

---

## P0 — Блокеры (чинить немедленно)

### P0.1 Сломан сбор тестов (незавершённый рефакторинг)

**Проблема.** 7 тест-файлов не импортируются — символы переехали/переименованы/удалены при рефакторинге, а тесты не обновлены. Полный список сломанных импортов:

| Тест-файл | Не находит символ | В модуле |
|-----------|-------------------|----------|
| `test_repair_ast_scope.py` | `expand_ast_reconcile_paths` | `llm/repair_scope.py` |
| `test_button_label_text_color.py` | `filled_button_label_text_color` | `generator/layout_style.py` |
| `test_ast_reconcile_cache_log.py` | `log_ast_reconcile_session_summary` | `observability/__init__.py` |
| `test_ir_stack_order_merge.py` | `merge_partial_stack_child_order` | `generator/ir_tree.py` |
| `test_ir_omit_sanitize.py` | `sanitize_screen_ir_omit_figma_ids` | `generator/ir_presence.py` |
| `test_ir_dumps.py` | `screen_ir_dump_path` | `debug/paths.py` |
| `test_transparent_material_unwrap.py` | `unwrap_transparent_material_wrappers` | `generator/dart_syntax_repairs.py` |

**Что сделать (по каждому символу):**
1. Установить судьбу символа: переименован / переехал в другой модуль / удалён за ненадобностью.
2. Если живой — обновить импорт в тесте на актуальное имя/путь (или вернуть публичный re-export, если это часть контракта).
3. Если удалён осознанно — удалить/переписать тест.
4. Прогнать `poetry run pytest --co -q` — 0 ошибок сборки.

**Важно:** это не косметика. Сломанные импорты = **эти 7 областей кода сейчас без тестового покрытия**, регрессии в них (включая IR-merge и AST-reconcile, где уже были баги) не ловятся.

**Критерий приёмки:** `pytest --co -q` собирает все тесты без ошибок; полный `pytest -q` проходит зелёным.

---

### P0.2 Незакоммиченный production-код вне git

**Проблема.** Новые модули и шаблоны существуют только в рабочем дереве (untracked). На чистой машине / в CI их не будет → импорты упадут.

**Затронутые файлы (пример на дату аудита — перепроверить `git status`):**
- `src/figma_flutter_agent/parser/render_boundary.py` (импортируется из `layout_widget.py`, `subtree_widgets.py`, `ambient_background.py`)
- `src/figma_flutter_agent/generator/templates/capture_screen_test.dart.j2`
- `tests/test_ir_merge_preserve.py`, `tests/test_process_run_stream.py`, `tests/test_render_boundary.py`, `tests/test_render_boundary_assets.py`
- фикстуры под `tests/fixtures/flutter_skeleton/...`

**Что сделать:**
1. Актуализировать список через `git status` (в активной ветке файлов может быть больше).
2. Решить по каждому файлу: коммитить или в `.gitignore` — **решение и коммит только по явной просьбе владельца ветки** (сабагент — отчёт, не `git commit`).
3. Production-код без тестов не оставлять untracked на `main`.
4. Smoke: `python -c "import figma_flutter_agent.cli"` на clean tree **после** согласованного коммита (не обязательно в том же PR, что hardening).

**Критерий приёмки:** нет untracked production-модулей в `src/`; импорт-смоук проходит на согласованном снимке ветки.

---

### P0.3 Завершить/откатить рефакторинг AST-санитайзеров

**Проблема.** Возможное полусостояние рефакторинга `dart_syntax_repairs.py` / `planned_dart.py` (AST-sidecar, delimiter balance). Часть символов могла переехать — тесты отстали (см. P0.1).

**Конфликт с текущей работой:** в ветке уже есть продуктовые правки (Text-orphan sanitize, capture tests, parse gate). **P0.3 не поручать сабагенту по умолчанию** — только владелец ветки или отдельный PR после стабилизации preview.

**Что сделать (если P0.3 в скоупе):**
1. Довести рефакторинг до конца: единый источник для `apply_planned_delimiter_balance`, `sanitize_planned_widget_syntax`, `repair_planned_dart_delimiters_if_needed`.
2. Сохранить фикс производительности (prefer prebuilt + `lru_cache` + ранний `validate_dart_delimiters` перед вызовом sidecar).
3. Добавить регрессионный тест: «при наличии prebuilt-бинаря `require_ast_compiler()` не возвращает `dart run` без флага `FIGMA_AST_COMPILER_PREFER_DART_RUN`».

**Критерий приёмки:** тест из P0.1 зелёный; новый тест на выбор компилятора зелёный; пайплайн на эталонном экране укладывается в ~1 мин.

**Улучшение инфра (опционально, отдельный микро-PR):** в `generator/validation.py` копировать `flutter_skeleton` с `ignore=(".dart_tool", "build")`, как в `golden_capture._copy_skeleton_project` — снижает нагрузку на `%TEMP%` при parse gate (не заменяет освобождение диска C:).

---

## P1 — Высокий приоритет (production gate)

### P1.1 203 ошибки mypy

**Проблема.** `strict=true` включён только для ~20 whitelisted-модулей; реально mypy находит **203 ошибки в 46 файлах**. Топ-категории (точные числа):

| Категория | Кол-во | Смысл |
|-----------|--------|-------|
| `arg-type` | 82 | неверный тип аргумента (часть — реальные баги) |
| `attr-defined` | 36 | обращение к несуществующему атрибуту / на `None` |
| `no-any-return` | 12 | возврат `Any` из типизированной функции |
| `assignment` | 12 | несовместимое присваивание |
| `union-attr` | 10 | атрибут на `X | None` без проверки |
| `no-untyped-def` | 9 | функция без аннотаций |
| `call-arg` / `call-overload` | 15 | неверные аргументы вызова |
| `name-defined` | 3 | **обращение к необъявленному имени (потенциальный NameError)** |

**Якорный пример:** `cli.py:1176-1207` — обращение к полям `result.file_name`, `result.mode` и т.д., где `result` выводится как `None` (функция `_run()` в `batch dump-file` не имеет аннотации возврата → `None`). Это реальный потенциальный `AttributeError`.

**Что сделать:**
1. Починить `attr-defined`/`union-attr`/`arg-type` (24 шт.) — это потенциальные рантайм-краши, приоритет внутри P1.
2. Аннотировать возвраты внутренних async-хелперов в `cli.py`.
3. Постепенно расширять whitelist `[[tool.mypy.overrides]] strict=true` на починенные модули, цель — весь `src/` под strict.

**Критерий приёмки:** `poetry run mypy src` → 0 ошибок; strict-список покрывает ≥80% модулей.

---

### P1.2 88 ошибок ruff в src (180 с тестами)

**Проблема.** Линт не зелёный. Разбивка по правилам (только `src/`, точные числа):

| Правило | Кол-во | Что значит |
|---------|--------|-----------|
| `I001` | 34 | несортированные импорты (авто-фикс) |
| `F401` | 20 | неиспользуемые импорты (авто-фикс) |
| `SIM103` | 19 | упрощаемый `return`-блок |
| `E402` | 9 | импорт не в начале файла |
| `B023` | 8 | **замыкание на переменную цикла (реальный баг late-binding)** |
| `SIM102/108/114/110` | 12 | упрощаемые конструкции |
| `F841` | 4 | неиспользуемые переменные |
| `F821` | 4 | **undefined name — обращение к необъявленному имени** |
| `F811` | 1 | переопределение (redefinition) |

**Приоритет внутри задачи:** `F821` (4) и `B023` (8) — это **не стиль, а потенциальные рантайм-баги**, чинить первыми и вручную.

**Что сделать:**
1. Сначала разобрать `F821` и `B023` вручную (понять, что именно сломано).
2. `poetry run ruff check src tests --fix` (закроет ~117 авто-фиксов: I001, F401, часть SIM).
3. Оставшиеся (E402, SIM103, B017 в тестах) — вручную; `assertRaises(Exception)` → конкретные исключения.

**Критерий приёмки:** `poetry run ruff check src tests` → 0 ошибок; `F821`/`B023` устранены не подавлением, а исправлением.

---

### P1.3 Широкие `except Exception` без логирования

**Проблема.** developer.md требует: «Always invoke `logger.exception()` inside `except` blocks» и запрещает blanket `except Exception`. Часть мест проглатывает ошибку молча.

**Подтверждённые нарушители (молчаливое проглатывание):**
- `generator/planned_dart.py:1755` — `except Exception: return True` (ошибка чтения Settings теряется)
- `pipeline/__init__.py:277` — `except Exception: figma_token = None`
- `validation/golden_capture.py:1075` — `except Exception:` (есть cleanup + re-raise — **допустимо**, но без лога)

**Оправданные (НЕ трогать):**
- `observability/__init__.py:45` — логирует через `stage_log.exception()` + `raise` ✓
- `cli.py` (7 шт.) — `except BaseException` с маршрутизацией в `_handle_cli_exception` (граница CLI) ✓

**Что сделать:**
1. В молчаливых местах: либо сузить тип исключения до конкретного (`OSError`, `ValidationError`), либо добавить `logger.exception()`/`logger.warning()` перед recovery.
2. Где ловим широко осознанно — оставить, но залогировать причину.

**Критерий приёмки:** каждый `except Exception` в `src/` либо логирует, либо сужен до конкретного типа; ruff `BLE001` (если включить) чист.

---

## P2 — Соответствие собственным «законам» репозитория

### P2.1 Текстовые эвристики против контракта universal-codegen

**Проблема.** `AGENTS.md` и `universal-codegen.md` декларируют: «Map widget bodies via structural signals — **never via label text** like `LOG IN`». Фактически `parser/interaction.py` матчит англоязычный текст:

- `_ACTION_HINTS = ("log in", "sign up", "submit", ...)`
- `_LINK_HINTS = ("forgot password", "terms", "privacy", ...)`
- `_SINGLE_WORD_ACTION_LABELS = {"start", "play", "home", "meditate", ...}`

**Риск.** На локализованном макете (рус/кит/нем) `«Войти»`, `«登录»` не распознаются → деградация детекции кнопок/ссылок. Противоречит цели «любой макет из 10 000».

> Примечание: это **не** screen-specific патч (правило anti-patching формально не нарушено — эвристики универсальны по структуре), но привязка к английскому тексту нарушает заявленный контракт «structural signals, not text».

**Что сделать (выбрать):**
1. **Минимум:** задокументировать ограничение явно (English-label heuristics) в README/AGENTS как осознанную MVP-дельту, с TODO на структурные сигналы.
2. **Правильно:** перевести детекцию на структурные признаки (геометрия, тип ноды, наличие surface/border-radius, позиция в дереве), а текст использовать только как вторичный буст.

**Критерий приёмки:** либо документированное ограничение со ссылкой в AGENTS.md, либо детекция работает на макете без англоязычных меток (добавить fixture).

---

### P2.2 Regex-санитайзеры Dart против «AST-only»-закона

**Проблема.** `CLAUDE.md`/`universal-codegen.md`: «All transformations via `ast_sidecar`. String-Replace & Regex Post-Processing — **Zero-Tolerance**». Фактически `dart_syntax_repairs.py`, части `dart_postprocess.py` правят Dart по regex (`collapse_duplicate_child_named_params`, `fix_garbage_closers_after_link_rich`, `fix_text_style_height_as_ratio` через `re.finditer`).

**Что сделать (выбрать):**
1. **Минимум:** легализовать как явное исключение «safety net» — добавить раздел в `universal-codegen.md`, что эти конкретные функции — допустимый последний рубеж, с инвариантом идемпотентности и обязательным `validate_dart_delimiters` после.
2. **Правильно:** перенести трансформации в AST-sidecar (новые правила в `tools/dart_ast_sidecar/`).

**Критерий приёмки:** закон и код не расходятся — либо regex-функции перенесены в AST, либо документированы как санкционированное исключение с тестами на идемпотентность.

---

## P3 — Тех. долг и гигиена (не блокеры)

### P3.1 Файлы-монолиты

**Проблема.** Против KISS/SRP: `llm_dart.py` (2479), `planned_dart.py` (2013), `layout_widget.py` (2008), `subtree_widgets.py` (1992), `client.py` (1939). В них же концентрируются broad-excepts и regex-санитайзеры; именно здесь уже произошла регрессия с тормозами AST.

**Что сделать:** декомпозировать по функциональным группам (например, `llm_dart.py` → парсинг ответа / валидация / санитайзинг). Не блокер, но снижает риск регрессий.

**Критерий приёмки:** ни один модуль `src/` > 1500 строк (ориентир, не догма).

### P3.2 Debug-мусор в корне

`_cmp.py/.txt`, `_col.*`, `_diag*`, `_fmt*`, `_pipe.*`, `_rec.*` и т.п. (не отслеживаются git, но засоряют дерево). Удалить или внести в `.gitignore`.

### P3.3 ruff `E501` отключён при line-length=100

`ignore = ["E501"]` означает, что длина строк не энфорсится. Решить: включить `ruff format` в CI (рекомендуется) либо убрать ignore. Сейчас декларация «строго Black/Ruff» расходится с реальностью.

---

## Соответствие ТЗ (отдельно от качества кода)

Все обязательные пункты §22 (MVP) закрыты, §23 проходят через `spec23.py`/`demo-signoff`. **Единственное формальное отклонение от ТЗ:**

### TZ.1 Dev Mode API не используется

§3, §5.1, §23 требуют извлечение через **Figma Dev Mode API**. Фактически — синтез стилей из REST + Styles API (`rest_css_synthesis`). Задокументировано как осознанная дельта в README.

**Что сделать:** согласовать с заказчиком, что REST-синтез приемлем как эквивалент, **либо** добавить интеграцию Dev Mode API (Enterprise) для формального закрытия §23.

**Критерий приёмки:** письменное согласование дельты ИЛИ реализованный вызов Dev Mode API.

---

## Порядок исполнения

**Для сабагента (безопасный минимум):**

```
0. Проверить свободное место на диске с TEMP (иначе стоп)
1. P0.1        → починить 7 тестовых импортов                  → verify: pytest --co -q
2. P1.2        → F821/B023 вручную, затем ruff --fix (осторожно) → verify: ruff check src tests
3. P3.2        → debug-мусор в корне
4. P0.2        → отчёт по untracked (без commit)
```

**Полный план (владелец ветки / после стабилизации feature):**

```
1. P0.1        → сбор тестов                                      → pytest --co зелёный
2. P0.3        → AST refactor (если нужно)                        → по критериям P0.3
3. P0.2        → untracked + коммит по запросу                     → clean-checkout smoke
4. P1.2 → P1.1 → ruff, mypy
5. P1.3        → broad excepts
6. P2.* / P3.* / TZ.1
```

**Финальный gate:** `./scripts/signoff.ps1` зелёный + `poetry run pytest -q` зелёный (только при достаточном месте на диске).
