# ТЗ: Robustness / fail-fast / runtime-safety (ROB-01..11)

> **Implementation status (2026-06-05):** ROB-01..05, ROB-07..11 closed in code; ROB-06 remains SYS-CORE-016.
> Invariant matrix — [systemic-core-audit.md §3](../../systemic-core-audit.md).

> Ось: НЕ геометрия-калибровка, а **надёжность** — runtime-ассерты, fail-silent, инъекции, само-краш
> логгера, валидность generated Dart. Источник — статический code-review проход по dirty-tree
> (параллельный агент), **верифицирован мной по живому коду 2026-06-05** (ни одного stale/ложного claim).
> Компаньон к [geometry-remainder-tz.md](geometry-remainder-tz.md) (в работе) — там геометрия; здесь robustness.
> Диагноз-SSOT — [systemic-core-audit.md](../../systemic-core-audit.md).

## 0. Сводка верификации (live vs latent)

| ROB | Agent # | Статус | Путь | Sev | Локализация (verified) |
|-----|---------|--------|------|-----|------------------------|
| **ROB-01** | #1 | ✅ verified | **planner** (latent до флипа) | **P0 runtime** | `geometry_planner.py:296-302` + `layout_widget.py:1516-1529` |
| **ROB-02** | #2 | ✅ verified | **live (любой путь)** | P1 | `figma_anchor.py:52` |
| **ROB-03** | #3 | ✅ verified | planner | P1 | `geometry_frames.py:affine2_from_figma_node` |
| **ROB-05** | #5 | ✅ verified | live (parse) | P1 | `stack_paint.py:69`, `overlap_sweep.py` |
| **ROB-06** | #6 | ✅ known | live (legacy) | P2 | `ast_sidecar.py` (= SYS-CORE-016/CORE-05) |
| **ROB-07** | #7 | ✅ verified | live (sidecar) | P1 | `figma_widget.dart:_parseCompilationUnit`; `test_replace_widget_invalid_replacement_leaves_source_unchanged` |
| **ROB-08** | #8 | ✅ verified+острее | **live (любой путь)** | **P0 (тривиально)** | `dart_error_log.py:147,153,158` |
| (defer) | #4 | ✅ = WP-R1 | planner | — | intrinsic=AABB → **не дублировать**, см. geometry-remainder-tz WP-R1 |

**Ключевой синтез:** ROB-01 — не просто баг, а **блокер WP-R2** (флип `use_geometry_planner`): поднять
флаг = уронить генерацию на первом INPUT <48px. ROB-02/07/08 — **path-independent**, бьют уже сейчас
(в т.ч. legacy), чинить не дожидаясь флипа. ROB-01/03/05 — на planner-пути (детонируют при флипе).

---

## ROB-01 — Невозможные `BoxConstraints(minHeight > maxHeight)` для низкого INPUT  [P0 runtime, блокер WP-R2]

**Verified:** `geometry_planner.py:296-302`:
```
if node.type == INPUT:
    min_height = min_input_height(node.sizing.height)   # = max(frame_h, 48) → ≥48
    if node.sizing.height > 0:
        max_height = float(node.sizing.height)           # = raw frame_h (может быть < 48)
```
Emit `layout_widget.py:1516-1529` кладёт `min_lit`/`max_lit` **без нормализации**. Инпут высотой 40 →
`BoxConstraints(minHeight: 48.0, maxHeight: 40.0)` → Flutter assert `minHeight <= maxHeight` → красный экран.
Это **runtime-краш**, не drift. На planner-пути (latent), но детонирует ровно при WP-R2.

**Фикс:**
- [ ] В планировщике при `height_fit == HeightFit.MIN`: `max_height = None` (нижняя граница есть, верхней нет —
  инпут растёт вниз), либо `max_height = max(min_height, frame_h)`.
- [ ] В emit (`layout_widget:1516`) добавить страховку: `max_lit` ≥ `min_lit` (если задан max и max<min → max=min).
- **Инвариант (ir_validate/geometry_invariants):** `INV-CONSTRAINT-NORMAL` — `max_height is None or max_height ≥ min_height` для каждого узла перед эмитом.
- **Тест:** `test_input_height_32_40_47_no_inverted_constraints` — для frame_h ∈ {32,40,47}: emit не содержит `minHeight > maxHeight`; `BoxConstraints` нормализован.
- **Effort:** S. **Сделать как предусловие WP-R2.**

## ROB-08 — Логгер ошибок сам себя роняет  [P0, live, тривиально]

**Verified+острее:** `dart_error_log.py`: `payload["projectDir"] = session.project_dir` (line 147 — **Path-объект**),
`payload.update(extra)` (153), `json.dumps(payload, ensure_ascii=False)` (158) — **без `default=str`/санитизации**.
Если `project_dir` это `Path` (или `extra` несёт `Path`/exception) → `json.dumps` бросает `TypeError` →
**логгер падает при попытке залогировать ошибку**, теряя исходную диагностику. Бьёт **любой путь**.

**Фикс:**
- [ ] `json.dumps(payload, ensure_ascii=False, default=str)` + усечение длинных значений (напр. `analyzeOutput`/`errors` до N КБ).
- [ ] `projectDir = str(session.project_dir)` явно; `extra` прогонять через safe-coerce (Path/exception → str).
- [ ] Обернуть запись в `try/except` — сбой логирования не должен валить пайплайн.
- **Тест:** `test_error_log_survives_path_and_exception_in_payload` — `extra={"p": Path(...), "e": ValueError()}` → лог пишется, не падает.
- **Effort:** XS. **Чинить немедленно — пол-сессии про надёжность, а сам логгер хрупкий.**

## ROB-02 — `ValueKey` экранирует только `:` и `'`  [P1, live]

**Verified:** `figma_anchor.py:52`: `safe = node_id.replace(":", "_").replace("'", r"\'")`. Backslash `\`,
newline, прочий Dart-синтаксис **не экранируются** → `ValueKey('figma-...\')` может сломать/инжектнуть
строку. Для real Figma API id (`123:456`) безопасно, но **offline dump / fixture / грязный слой** — нет.

**Фикс:**
- [ ] Полная санитизация идентификатора: оставить `[A-Za-z0-9_-]`, всё прочее → `_` (или hex-escape);
  гарантировать валидный Dart string literal. Не точечный escape отдельных символов.
- **Инвариант:** `INV-IDENT-SAFE` — все эмитированные ключи/идентификаторы проходят whitelist.
- **Тест:** `test_value_key_sanitizes_backslash_newline_quote` — id с `\`, `\n`, `'`, leading digit → валидный Dart.
- **Effort:** S.

## ROB-07 — `replace_widget` вставляет raw replacement без ре-парса  [P1, live, sidecar]

**Статус:** plausible (Dart-сайдкар лично не читал). `ast_compiler.dart:replace_widget` подставляет
replacement и возвращает без повторного парса итогового Dart → возможна порча generated source
(не «исполнение кода», а corruption).

**Фикс:**
- [ ] После `replace_widget` (и `extract→wrap→replace`) **ре-парсить** результат; при невалидном Dart —
  откат к исходнику + warning (fail-safe, не silent corruption).
- **Тест:** `test_replace_widget_rejects_unparseable_result`.
- **Effort:** S (на стороне Dart-сайдкара → после правок `.\tools\build_sidecars.ps1`).

## ROB-05 — Z-защита отключается одним unpositioned-ребёнком  [P1, parse]

**Verified:** `stack_paint.py:69` (`sort_absolute_stack_children`): `if not children or not all(child.stack_placement is not None for child in children): return children`. Один непозиционированный ребёнок → весь Z-sort/ghost-демоут **выключается** → декор может оказаться поверх `TextField/Button` → input-lock.

**Фикс:**
- [ ] Применять Z-DAG/демоут к **подмножеству** позиционированных + смешанным (flow+absolute) стекам,
  не требовать `all(...)`. Для flow-детей использовать их layout-bounds.
- [ ] Обязательный `ghost_occlusion_violations`-gate для интерактивных siblings **включая** частичный placement.
- **Инвариант:** `INV-Z` (уже есть) — расширить на смешанные стеки.
- **Тест:** `test_zorder_with_one_unpositioned_child_keeps_interactive_on_top`.
- **Effort:** M.

## ROB-03 — Битый `relativeTransform` → silent identity  [P1, parse]

**Verified:** `affine2_from_figma_node` на отсутствующей/битой матрице возвращает `Affine2()` (identity).
Сложный повёрнутый layout сгенерится «успешно» с крупным дрейфом — **fail-silent опаснее краша**.

**Фикс:**
- [ ] На parse-boundary валидировать `relativeTransform`; malformed → `ParseError` с node id/path
  (в strict/generate). Identity-fallback допустим только для подтверждённо-отсутствующей матрицы (axis-aligned),
  не для битой.
- **Тест:** `test_malformed_relative_transform_raises_parse_error_with_node_id`.
- **Effort:** S.

## ROB-06 — AST codegen skip при >80KB  [P2, известно]

= SYS-CORE-016 / CORE-05 (см. systemic-core-audit). Не дублировать; решение — chunked codegen / split,
не silent skip. Здесь только фиксируем как live-legacy риск.

---

## Предложено аудитом, НЕ верифицировано мной (проверить до внедрения)

> Эти пункты из секции «хардкоринг» аудита я лично не подтверждал по коду — пометить как `needs-verify`.
- **ROB-09 (proposed):** дубликаты id в clean tree / IR / `stack_child_order` должны падать **до** merge,
  а не схлопываться `dict`-ом (`ir_tree.py`). → verify: где merge по id, теряются ли дубли молча.
- **ROB-10 (proposed):** санитизация Dart-идентификаторов после `to_pascal_case` — имя не должно начинаться
  с цифры, быть пустым или keyword → безопасный prefix. → verify: `to_pascal_case` + class-name эмит.
- **ROB-11 (proposed):** зафиксировать immutable-contract clean tree — сейчас comment расходится с
  mutation в parser passes. → verify: где parser мутирует по месту vs `model_copy`.

---

## Инварианты (добавить в validate)

| ID | Правило |
|----|---------|
| `INV-CONSTRAINT-NORMAL` | `max_height is None or max_height ≥ min_height` (и для width) перед эмитом |
| `INV-IDENT-SAFE` | эмитированные ключи/имена классов — whitelist `[A-Za-z0-9_-]`, не начинаются с цифры/keyword |
| `INV-TRANSFORM-VALID` | `relativeTransform` либо валиден, либо отсутствует; битый → ParseError (не identity) |
| `INV-Z` (расшир.) | Z-gate работает на смешанных стеках (частичный placement), не только all-positioned |
| `INV-LOG-SAFE` | сериализация лог-payload не падает на Path/exception (default=str + truncation) |

## Приоритет и порядок

1. **ROB-01** — предусловие **WP-R2** (флип планировщика); без него флип = краш на INPUT<48px.
2. **ROB-08** — немедленно (live, XS): логгер не должен падать при логировании.
3. **ROB-02, ROB-07** — path-independent robustness/инъекция (live).
4. **ROB-05, ROB-03** — planner/parse fail-fast (до/в составе WP-R2).
5. **ROB-09/10/11** — сначала verify, потом scope.
6. **ROB-06** — через SYS-CORE-016 (chunked AST), не отдельно.

**Связь с геометрией:** ROB-01/03/05 — на planner-пути → объединить с прогоном инвариантов в WP-R2;
ROB-02/07/08 — независимы, можно мержить раньше. ROB-04 = WP-R1 (не дублировать).

## Принцип

> **Generated Dart должен быть либо валиден, либо генерация падает с понятной ошибкой (node id/path) —
> никакого silent corruption, fail-silent identity, инвертированных constraints или само-краша логгера.**
> Fail-fast на parse/validate-границе; нормализация constraints и санитизация идентификаторов — инварианты,
> не точечные фиксы.
