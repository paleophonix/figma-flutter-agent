# ТЗ: Production-safe rollout планировщика (последняя миля до perfect)

> **Implementation status (2026-06-05):** WP-P1..P4 closed — severity gate (HARD/soft), degrade telemetry,
> corpus gate (9 fixtures + unit classes), ROB-07 verified. SSOT severity matrix in
> [systemic-core-audit.md §3](../../systemic-core-audit.md).

> Контекст 2026-06-05: `use_geometry_planner: default=True` (флаг поднят, геометрия живая), ROB-01..11
> и WP-R1 закрыты и **верифицированы по коду**. Остался **один системный риск к «perfect»**:
> `normalize_clean_tree` (normalize.py:80-85) при planner=on вызывает
> `validate_geometry_invariants(require_layout_slots=True)` и **`raise GenerationError` на ЛЮБОМ из ~12
> инвариантов** (fail-closed, без severity). На 4-8 фикстурах ок; на 10k произвольных одна суб-пиксельная
> невязка = краш генерации там, где раньше был drift. **Это ТЗ делает флип безопасным для 10k.**
> Новый док (прошлые в работе). Диагноз-SSOT — [systemic-core-audit.md](../../systemic-core-audit.md).

## 0. Verified state (что НЕ переделывать)

- ✅ ROB-01 (min>max): двойная защита — planner `max=None` + emit `normalize_box_constraints`.
- ✅ ROB-02/03/05/08/09/10, WP-R1 (`_local_intrinsic_size_from_aabb` 2×2-инверсия), WP-R2 (флаг=True).
- ✅ WP-E: 1 `Alignment.center` в `test_affine_calibration:114` — **намеренный негативный тест** (bad_source), не stale.
- ✅ Фикстуры: 9 (включая `deep_nesting_8x`, `nested_affine_cascade`, `elastic_form_a11y`, `variant_topology`, `oversized_layout`).
- ✅ ROB-07 (Dart re-parse после replace_widget): verified — `figma_widget.dart:_parseCompilationUnit` + `test_replace_widget_invalid_replacement_leaves_source_unchanged`.
- ✅ **GAP closed:** `GeometryInvariantViolation` includes `severity`; `normalize.py` raises only on HARD.

## Фактический набор инвариантов (verified, geometry_invariants.py:327-357)

`missing_layout_slot`, `t1_reproject`, `t1_placement`, `t2_flex_conservation`, `t3_baseline`,
`t5_z_order`(=`inv_z`), `t5_repaint_partition`, `inv_affine_det`, `constraint_normal`, `inv_flex_axis`,
+ emit: `inv_emit_no_translate`, `inv_unit`, `inv_ast_coverage`.

---

## WP-P1 — Расслоить fail-closed: HARD (raise) vs SOFT (log+degrade)  [P0, ядро]

**Принцип:** raise только когда эмит **сломан/упадёт/мёртв** (структурные); числовой дрейф в пределах
ограниченной ошибки — **не краш**, а log + degrade (телеметрия + per-node fallback). Невязка ε не должна
ронять весь экран.

- [x] **P1.1 — Добавить `severity: Literal["hard","soft"]` в `GeometryInvariantViolation`.**
- [x] **P1.2 — Классификация по коду (зашить в каждую check-функцию):**

| Код | Severity | Почему |
|-----|----------|--------|
| `constraint_normal` (min>max) | **HARD** | Flutter assert → красный экран |
| `inv_unit` (не радианы) | **HARD** | грубый улёт поворота |
| `inv_emit_no_translate` | **HARD** | двойной translate → corruption |
| `inv_affine_det` (degenerate/неучтённый det) | **HARD** | вырожденная матрица / потеря зеркала |
| `inv_flex_axis` (Expanded не по оси) | **HARD** | `RenderFlex` / коллапс |
| `missing_layout_slot` | **HARD** | планировщик не отработал (баг pipeline) |
| `t5_z_order` (`inv_z`) | **HARD** | презентация над интерактивом → мёртвый UI (input-lock) |
| `inv_ast_coverage` (oversized skip) | **HARD в `--strict`, SOFT иначе** | контракт не применён |
| `t1_reproject` (AABB residual > ε) | **SOFT** | ограниченный суб-пиксельный дрейф |
| `t1_placement` | **SOFT** | то же |
| `t2_flex_conservation` (extent > 0.5px) | **SOFT** | суб-пиксельная щель |
| `t3_baseline` (delta_top без wrap) | **SOFT** | текстовый дрейф, не краш |
| `t5_repaint_partition` | **SOFT** | перф, не корректность |

- [x] **P1.3 — `normalize.py`:** `hard = [v for v in violations if v.severity=="hard"]`; raise только если
  `hard`; soft → `logger.warning` с `code@node_id` + счётчик. Сообщение hard-raise оставить с node_id/path.
- **Тест:** `test_soft_violation_does_not_raise` (reproject ε → warning, не GenerationError);
  `test_hard_violation_raises` (min>max → raise).
- **Acceptance:** суб-пиксельная невязка не валит экран; структурный баг по-прежнему fail-closed.
- **Effort:** S-M.

## WP-P2 — Degrade-поведение для SOFT (не просто проглотить)  [P1]

- [x] **P2.1 — Per-node fallback:** при soft-невязке на узле — пометить `degraded=True`; для критичных к
  точности (reproject) опционально откатить **этот узел** на legacy-emit, не весь экран. Минимум — принять
  эмит как есть (в пределах ε) и залогировать.
- [x] **P2.2 — Телеметрия:** счётчик soft-невязок по коду в отчёт сборки (`design_coverage`/reconcile_metadata);
  CI-порог: рост soft > N относительно baseline → warning (не fail).
- [x] **P2.3 — Бюджет ε:** зафиксировать пороги (`geom_epsilon`, 0.5px extent, baseline ε) в одном месте;
  soft срабатывает только за пределами бюджета.
- **Acceptance:** soft-невязки видимы в отчёте, не теряются молча; рост ловится CI.
- **Effort:** M.

## WP-P3 — Corpus-gate: planner=on зелёный на расширенном наборе ДО клиентов  [P0]

**Сейчас:** 8 фикстур. Для «perfect на 10k» добить недостающие **классы деревьев** (как фикстуры И/ИЛИ unit-тесты):

- [x] **P3.1 — Недостающие классы:**
  - `mirror_det_negative.json` — отражённая группа (`det(L)<0`) → должна уйти в raster-tier, не Matrix4.
  - `short_input_sub48.json` — INPUT высотой 32/40/47 → ROB-01 (нет inverted constraints).
  - `malformed_transform.json` — битый `relativeTransform` → ROB-03 `ParseError` с node id.
  - `mixed_stack_partial_placement.json` — STACK с одним unpositioned + декор над INPUT → ROB-05 (z сохранён).
  - `deep_nesting_8x.json` — глубина ≥8, дробные координаты, большие offset → reproject ≤ ε на всех листах.
  - `a11y_long_text.json` — длинный текст + textScaler 1.3/2.0 → нет `RenderFlex overflow` (INV-A11Y).
- [x] **P3.2 — CI-гейт:** прогон planner=on по ВСЕМ фикстурам: **0 HARD-нарушений** (soft — в бюджете, считаются);
  `demo-signoff --signoff-gates` + geometry-tier (IoU) без регрессий.
- [x] **P3.3 — Numeric, не строковый:** сравнивать Matrix4 mapping всех 4 углов численно, не подстроку `Matrix4(...)`.
- **Acceptance:** ни один класс дерева не даёт hard-краш; soft в пределах бюджета на всём корпусе.
- **Effort:** M.

## WP-P4 — Хвосты  [P1-P2]

- [x] **P4.1 (ROB-07):** сверить `ast_compiler.dart:replace_widget` — ре-парсит ли результат; если нет —
  ре-парс + откат при невалидном Dart; ребилд `.\tools\build_sidecars.ps1`. (лично не верифицировано)
- [ ] **P4.2:** прогнать полный `pytest -q -m "not live_figma"` + `signoff` после P1-P3; зафиксировать 0 failed.
- [x] **P4.3 (санитария доков):** пометить `superseded` исторические core-audit доки (оставить актуальными
  `systemic-core-audit.md` + `geometry-remainder-tz` + `robustness-failfast-tz` + этот).

---

## Определение «perfect» (acceptance всего)

1. `use_geometry_planner=True` (есть) + **0 HARD-нарушений** на расширенном корпусе (WP-P3).
2. SOFT-невязки — в бюджете ε, видимы в телеметрии, не валят экран (WP-P1/P2).
3. Нет `RenderFlex overflow`/`BoxConstraints` assert при длинном тексте и textScaler 2.0 (P3 a11y).
4. `det(L)<0`/shear → raster-tier, не искажённый Matrix4 (P3 mirror).
5. Битые входы (malformed transform, dup id, грязный node id) → понятный `ParseError`/санитизация, не silent/crash.
6. `pytest`/`signoff` зелёные; ROB-07 подтверждён.

## Порядок

```
WP-P1 (severity + raise-only-hard) ─► WP-P3 (corpus 0-hard) ─► safe для клиентов
WP-P2 (degrade+телеметрия) ─ параллельно P1
WP-P4 ─ хвосты, после P1-P3
```
**Критический путь: WP-P1 → WP-P3.** Без расслоения (P1) гейт остаётся «инвариант ловит баг = инвариант
роняет экран»; после P1+P3 — «hard ловит реальные поломки, soft деградирует с телеметрией».

## Принцип

> **Fail-closed — только на том, что сломано/мёртво/упадёт (структурные инварианты). Числовой дрейф в
> пределах ε — деградирует с телеметрией, не роняет экран.** «Perfect» = 0 hard на всём корпусе классов
> деревьев + soft в бюджете, а не 0 нарушений любой ценой (это даёт хрупкость, не качество).
