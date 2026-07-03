# ТЗ рефакторинга геометрического ядра (консолидированное, исполняемое)

> **Superseded by [geometry-remainder-tz.md](geometry-remainder-tz.md)** for execution (2026-06-05). Retained for history.
> Сводит: [systemic-core-audit.md](../../systemic-core-audit.md) (SYS-CORE-001..020, INV-матрица, P0-P4)
> + два параллельных ревью (MTX/FLX/TXT/Z/VAR/AST) + прошлые доки core-audit
> ([geometry-calibration-spec.md](geometry-calibration-spec.md), [translation-theory.md](translation-theory.md),
> [reviewer-backlog.md](reviewer-backlog.md)).
> Это **исполняемый слой** (work-packages: файл → правка → инвариант → тест → приёмка); диагностика —
> в systemic-core-audit.md. Все находки verified по коду 2026-06-05. Номера строк сверять по именам функций.

## 0. Новые P0-баги, не покрытые systemic-core-audit (verified сегодня)

### NEW-MTX-01 — единицы поворота: degrees vs radians (катастрофа на дефолтном пути)
- **Evidence:** `parser/tree.py:184-188 _extract_rotation_degrees` → `node.rotation` в **градусах**
  (`rotation_degrees_from_figma_node` = `math.degrees(...)` / Figma `rotation`-поле). Legacy emit
  `layout_widget.py:534-538`: `angle = format_micro_style_literal(node.rotation)` →
  `Transform.rotate(angle: {angle})`. Flutter `Transform.rotate(angle:)` принимает **радианы**.
- **Эффект:** 45° → `Transform.rotate(angle: 45.0)` = 45 рад ≈ 2578° → улёт/мусор. Стреляет при
  `use_geometry_planner: false` (DEFAULT) на любой повёрнутой ноде, не ушедшей в SVG/π-skip.
- **Fix:** хранить в схеме `rotation_rad` (радианы); degrees — только raw-метаданные. Legacy-путь
  эмитит `Transform.rotate(angle: rotation_rad)`. Matrix4-путь уже радианный (`atan2`) — оставить.
- **Инвариант:** `INV-UNIT` — `Transform.rotate.angle` всегда радианы, `|angle| ≤ 2π+ε` для одиночного поворота.

### NEW-FLX-01 — INPUT width=FILL → Expanded в Column (ось перепутана)
- **Evidence:** `generator/geometry_flex.py:85-88`: `if child.type == INPUT: if parent COLUMN and width_mode==FILL or parent ROW and width_mode==FILL: wraps.append(EXPANDED)`.
- **Эффект:** в `Column` `Expanded` управляет **главной осью = высотой**; FILL-по-ширине инпут жадно
  ест вертикаль → коллапс соседей / неверная высота. В `Row` (главная ось = ширина) — корректно.
- **Fix:** wrap зависит от оси: `Column + width FILL → cross-stretch` (`SizedBox(width: double.infinity)`
  / `crossAxisAlignment.stretch`), НЕ `Expanded`. `Column + height FILL → Expanded`. `Row` зеркально.
- **Инвариант:** `INV-FLEX-AXIS` — `Expanded` только когда FILL по **главной** оси контейнера.

## 1. Карта дефект → work-package (merge всех источников)

| WP | Фаза | Поглощает | Направление |
|----|------|-----------|-------------|
| WP-0 | P0 | NEW-MTX-01, NEW-FLX-01 | быстрые unit/axis фиксы |
| WP-1 | P0 | SYS-CORE-001..005,017; geometry-calibration RC-1..4,10; MTX-02/03 | единый каскад + emit-инварианты |
| WP-2 | P1 | SYS-CORE-006..009,018; RC-5/6; FLX-01; TXT-01 | эластичные констрейнты |
| WP-3 | P2 | SYS-CORE-010..012,019; VAR-01 | варианты как конфиг |
| WP-4 | P3 | SYS-CORE-013..016,020; AST-01 | size gates → chunked |
| WP-5 | сквозной | INV-T4/E1/A11Y/V1/Z + UNIT/FLEX-AXIS | ir_validate = проверяльщик законов |
| WP-6 | P4 | SYS-CORE diagnosis #4; Z-01 | closed-loop + единый Z-DAG |

---

## 2. Work-packages

### WP-0 — Быстрые P0 (unit + axis)  [Effort: S, blast: высокий]
- [ ] **WP-0.1 (NEW-MTX-01):** в схеме завести `rotation_rad`; `parser/tree.py` писать радианы;
  `layout_widget._apply_node_transform:538` эмитить `Transform.rotate(angle: rotation_rad)`. Degrees
  оставить только как diagnostic-метаданные.
  - Тест: `test_legacy_rotation_emits_radians` — нода 45° → emit `angle:` ≈ 0.7854, не 45.0.
- [ ] **WP-0.2 (NEW-FLX-01):** `geometry_flex.compute_flex_deltas:85-88` — для INPUT: `Column+width FILL`
  → cross-stretch wrap; `Expanded` только при FILL по главной оси. Убрать precedence-кашу `A and B or C and D`.
  - Тест: `test_input_fill_width_in_column_is_stretch_not_expanded`.
- **Приёмка:** повёрнутые ноды на дефолте не улетают; FILL-инпут в Column не ест высоту.

### WP-1 — Единый каскад + emit-инварианты  [Effort: L, P0]
*Поглощает SYS-CORE-001..005, 017; RC-1..4, 10.*
- [ ] **WP-1.1 (SYS-CORE-001):** ввести единый `CascadeContext` на ноду в parse (`world`, `local`,
  `placement_channel`, `pivot`); планировщик — единственный мутатор `layout_slot`; legacy-путь →
  deprecated-adapter до default-on.
- [ ] **WP-1.2 (SYS-CORE-002 / RC-1):** `affine2_from_figma_node` — сырые `a,b,c,d` (без `hypot`-реконструкции);
  `det(L)<0` или сильный shear → `LayoutBackend.BOUNDARY/RASTER` (`_is_unsafe_shear` уже есть — расширить на det).
- [ ] **WP-1.3 (SYS-CORE-003 / RC-2,3 / MTX-02):** pivot-инвариант. `matrix4_linear_expr` уже без
  translate; зафиксировать **один канал позиции**: если `Positioned(left,top)` задан → линейный
  Matrix4 строго без переноса, pivot `Alignment.center` **только** если позиция = центр AABB; иначе
  компенсировать `s = t + (L−I)·c` (формула ревью) ровно один раз. Не AABB-translate И matrix-translate.
- [ ] **WP-1.4 (SYS-CORE-017 / RC-4):** `hydrate_geometry_frame` — `layout_rect.origin` = угол
  axis-aligned **placement**-бокса (`placement_aabb` или `expand_aabb(local, intrinsic)`), не сырые `tx,ty`.
  Разделить `localSize` (неповёрнутый) и `worldAabb = bbox(M, localRect)`.
- [ ] **WP-1.5 (SYS-CORE-004,005):** T2 (`extent_conservation`) только при `backend==FLEX` и без
  `stack_placement`; STACK — только pin-closure (T1).
- **Инварианты:** `INV-AFFINE-DET`, `INV-EMIT-NOTRANSLATE`, `INV-REPROJECT` (проверка ЭМИТА).
- **Тесты:** `test_affine_preserves_determinant`, `test_transform_no_double_translate`,
  `test_t1_invariant_catches_emit_translate`, `test_t2_conservation_skips_stack`.
- **Приёмка:** `reproject(slot.origin ⊕ emit.L) ≈ε world_aabb` на nested-фикстурах (depth ≥ 3).

### WP-2 — Эластичные констрейнты  [Effort: L, P1]
*Поглощает SYS-CORE-006..009, 018; RC-5/6; FLX-01; TXT-01.*
- [ ] **WP-2.1 (SYS-CORE-006):** `layout_flex_reconcile.apply_flex_guards_from_tree` — скипать **только**
  когда родитель STACK (`layout_slot.backend==STACK`), не просто при наличии `stack_placement` у ребёнка.
- [ ] **WP-2.2 (SYS-CORE-007):** планировщик — авторитетный источник `layout_slot.wraps`; reconcile
  **проверяет** эмит, а не слепо скипает AST; AST-правила → идемпотентные валидаторы.
- [ ] **WP-2.3 (SYS-CORE-008 / эластичность):** ввести IR-поля `minHeight/maxHeight/heightFit:
  fixed|min|intrinsic` из глифовых метрик + число строк; для TEXT/INPUT в scroll/flex эмитить
  `BoxConstraints`, не фикс-`SizedBox(height)`.
- [ ] **WP-2.4 (SYS-CORE-018):** всегда прикреплять `TextMetricsFrame` для INPUT на parse; паддинг из
  метрик на **обоих** путях; `contentPadding.vertical = (H_frame − glyph_height)/2`, `minHeight = max(H_frame, 48)`.
- [ ] **WP-2.5 (TXT-01):** baseline-оракул: `paddingTop = figmaBaseline − flutterBaseline(fontKey)`,
  `fontKey = family/weight/size/platform`; убрать суррогат `font_size*0.72` из критического пути
  (оставить как fallback с warning).
- **Инварианты:** `INV-E1` (elastic headroom), `INV-A11Y` (нет overflow при textScaler 1.3/2.0),
  `INV-FLEX-AXIS`, `INV-E2` (stretch ⇒ bounded cross).
- **Тесты:** `test_input_fill_width_with_content_padding`, `test_elastic_bounds_a11y`,
  `test_flex_child_fill_not_pinned_to_aabb`, `test_flex_reconcile_respects_parent_type`.
- **Приёмка:** длинный API-текст и textScaler=2.0 не дают `RenderFlex overflow` на dense-формах.

### WP-3 — Варианты как конфигурация  [Effort: L, P2]
*Поглощает SYS-CORE-010..012, 019; VAR-01.*
- [ ] **WP-3.1 (SYS-CORE-010):** структурная сигнатура на инстанс варианта
  `sig(v)=multiset(NodeType, depth, childCount)`; `Jaccard(sig(v1),sig(v2)) < θ (≈0.85)` → отдельная
  ветка/slot-builder, не один merged-subtree.
- [ ] **WP-3.2 (SYS-CORE-011):** `ComponentConfig{clusterId, props, visibility: Set<FigmaId>, slots}`;
  overrides → декларативный конфиг, не дублированные деревья; `apply_adaptive_rules` умеет hide/show
  поддеревья, не только merge `WidgetIrOverrides`.
- [ ] **WP-3.3 (SYS-CORE-012):** стейт-шаблоны (`state_*.j2`) → immutable `freezed`-конфиг по схеме
  свойств компонента; публичные ctor-параметры **заморожены** между синками.
- [ ] **WP-3.4 (SYS-CORE-019):** `reconcile_cluster_variant_args` — при смене схемы параметров кластера
  **fail validation** (не тихий strip); миграция явная в `// <custom-code>`.
- **Инварианты:** `INV-V1` (Δtopology>θ ⇒ нет merged subtree), `INV-SIGNATURE-STABLE`.
- **Тесты:** `test_variant_topology_split` (Text→Spinner), `test_widget_signature_backward_compatible`.
- **Приёмка:** добавление варианта в Figma не ломает handwritten BLoC/Riverpod-вызовы.

### WP-4 — Size gates → chunked  [Effort: L, P3]
*Поглощает SYS-CORE-013..016, 020; AST-01.*
- [ ] **WP-4.1 (plan-split):** `planned_dart` режет на `*_shell.dart` + `*_body_*.dart` по бюджету <80KB/файл.
- [ ] **WP-4.2 (chunked codegen):** `apply_codegen_ast_rules` — per-chunk `codegen_pass` (не на 500KB
  единым unit'ом); снять silent-skip; превышение → fail-loud.
- [ ] **WP-4.3:** chunked flex (`apply_flex_guards_from_tree` через `extract_widget` по figma-id) и
  text-scaler; запретить regex-only при `use_ast_sidecar: true`.
- [ ] **WP-4.4:** лимит поэтапно 80→200→500KB с perf-бюджетом p95 на Windows CI; телеметрия
  `regex_fallback_used` → CI fail без waiver.
- **Инвариант:** `INV-AST-COVERAGE` — каждый structural-rule имеет backend `full_ast|chunk_ast`;
  `skipped` запрещён для codegen/layout-safety.
- **Тесты:** `test_oversized_layout_chunked_codegen`, `test_no_regex_fallback_when_sidecar_enabled`.

### WP-5 — `ir_validate` как проверяльщик законов (сквозной)  [Effort: M]
Перенести T1–T5 из текстовых grep-проверок в численные corner/baseline/flex/DAG, **на границе эмита**:
- [ ] подключать `validate_geometry_invariants` всегда при наличии `layout_slot`;
- [ ] добавить `INV-T4` (emit без translate — статический анализ эмит-сниппета через sidecar);
- [ ] добавить `INV-E1`/`INV-A11Y`/`INV-V1` как IR-schema-констрейнты;
- [ ] `INV-UNIT`/`INV-FLEX-AXIS` (из WP-0).
- **Приёмка:** математически верный план, дающий кривой Dart, **падает на гейте** (анти-регрессия NEW-MTX-01).

### WP-6 — Closed-loop + единый Z-DAG  [Effort: M, P4]
- [ ] **Z-01:** единый DAG paint/hit-test: `overlap(d,i) ⇒ edge decor→interactive`; topo-sort стабилен,
  иначе исходный порядок. Заменить три рассинхронных подсистемы (overlap_sweep / stack_paint /
  ghost-occlusion) одним проходом перед эмитом.
- [ ] deterministic CI: geometry-tier gate (`geometry_metrics`) на фикстурах; опциональный
  layout-only pixel-refine (развязан с LLM).
- **Инвариант:** `INV-Z` — единый тотальный порядок, согласованный с overlap + interaction class.

---

## 3. Матрица инвариантов `ir_validate` (консолидированная)

| ID | Закон | Предикат перед эмитом | Источник |
|----|-------|------------------------|----------|
| **INV-UNIT** | единицы поворота | `Transform.rotate.angle` в радианах; `|angle| ≤ 2π+ε` | NEW-MTX-01 |
| **INV-FLEX-AXIS** | ось Expanded | `Expanded` ⟺ FILL по главной оси контейнера | NEW-FLX-01 |
| **INV-AFFINE-DET** | сохранение det | `det(L)` от parse до emit; `det<0` ⇒ RASTER | SYS-CORE-002 |
| **INV-EMIT-NOTRANSLATE** | один канал позиции | `Positioned` задан ⇒ `residual_matrix.t = 0` | SYS-CORE-004 / INV-T4 |
| **INV-REPROJECT** | замыкание AABB | `‖expand(slot.origin ⊕ emit.L) − world_aabb‖ ≤ ε` (ЭМИТ) | SYS-CORE-001/017 |
| **INV-T2-FLEX** | сохранение протяжённости | `|P−(Σchild+gap+pad)| ≤ 0.5px` только FLEX | SYS-CORE-005 |
| **INV-E1** | эластичный запас | `minHeight ≤ figmaH ≤ maxHeight`, slack ≥ f(lineHeight, a11y) | SYS-CORE-008 |
| **INV-A11Y** | масштаб текста | нет overflow при `textScaler ∈ {1.3, 2.0}` | SYS-CORE-009 |
| **INV-BASELINE** | один учёт leading | `Δ_top` через StrutStyle XOR contentPadding | SYS-CORE-003/018 |
| **INV-V1** | топология вариантов | `Δtopology>θ ⇒ нет merged subtree` | SYS-CORE-010 |
| **INV-SIGNATURE** | стабильность ctor | новый вариант не меняет публичную сигнатуру | SYS-CORE-019 |
| **INV-Z** | Z-DAG | единый тотальный порядок, decor < interactive при overlap | Z-01 |
| **INV-AST-COVERAGE** | покрытие AST | каждый rule: `full_ast|chunk_ast`, не `skipped` | SYS-CORE-016 |

## 4. Порядок и зависимости

```
WP-0 (unit/axis, часы)  ─┐
WP-1 (каскад) ───────────┼─► WP-5 (гейт проверяет эмит) ─► default-on use_geometry_planner
WP-2 (эластичность) ─────┘
WP-3 (варианты)  ── параллельно после WP-1
WP-4 (size gates) ─ параллельно (независим)
WP-6 (Z-DAG + loop) ─ после WP-1/WP-5
```
Критический путь: **WP-0 → WP-1 → WP-5**. Без WP-5 (проверка эмита) любой геом-фикс остаётся
недоказуемым — именно так прошёл NEW-MTX-01 и двойной translate.

## 5. Протокол приёмки

1. `poetry run pytest -q -m "not live_figma"` + новые тесты каждого WP зелёные.
2. После правок `tools/dart_ast_sidecar/`: `.\tools\build_sidecars.ps1`.
3. Фикстуры (без screen-имён): `nested_affine_cascade.json` (depth≥3, поворот+scale+mirror),
   `elastic_form_a11y.json` (FILL-инпуты + длинный текст), `variant_topology.json` (Text↔Spinner),
   `oversized_layout.json` (>80KB).
4. Перед merge в `main`: `.\scripts\signoff.ps1`.

## 6. Единый принцип (закрепить в systemic-core-audit)

> **Одна система координат на границе эмита, проверяемая гейтом.** Углы — радианы; позиция — один
> канал (слот), линейная часть — `Matrix4` без translate; размер — по режиму (FILL/HUG/FIXED по
> правильной оси) с эластичным запасом; варианты — конфиг, не дубли деревьев; AST — chunked, не
> silent-skip. `ir_validate` доказывает ЭМИТ (reproject/unit/axis/det), а не только план.
