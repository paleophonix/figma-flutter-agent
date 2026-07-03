# Рефактор-чеклист от теории трансляции (операционализация T1–T5)

> Дата: 2026-06-05. Превращает [translation-theory.md](translation-theory.md) (T1–T5 + единый инвариант)
> в пошаговый структурный рефактор. Дополняет тактический [execution-plan.md](execution-plan.md)
> (FID-фиксы) архитектурным слоем: **сделать `ir_validate` хранителем геометрических законов, а
> Parse→Plan→Emit→AST — проверяемой сменой базиса.**
> Статусы — на 2026-06-05, verified по коду. Номера строк сверять по именам функций.

## Текущее состояние vs теория (verified)

| Теорема | Статус | Доказательство по коду |
|---------|--------|------------------------|
| **T4** единицы блюра | ✅ **done** | `generator/render_units.py` (`figma_blur_to_flutter_blur_radius≈0.87·B−0.87`, `figma_blur_to_image_sigma=B/2`), подключён `layout_style:149`, `layout_widget:530/1811/1824` |
| **T3** baseline/strut | 🟡 **partial** | `StrutStyle` эмитится (`layout_widget`, `emit_text_span`, `layout_style`); компенсирующий `Δ_top` из `glyph_top_offset` — проверить точность |
| schema min/max | ✅ field есть | `schemas.py:88-89` `min_width/max_width` (emit `ConstrainedBox` — проверить) |
| schema per-corner | ✅ field есть | `schemas.py:178` `border_radius_corners: CornerRadii` (emit value-source баг 52→28 — открыт) |
| **T1** аффинный каскад | ❌ **open** | `transform_context_from_figma_node` считает rot/sx/sy/tx/ty, но в дерево идёт **только скаляр rotation**; поля матрицы в схеме нет; pivot topLeft поверх AABB |
| **T2** сохранение протяжённости | ❌ **open** | `round_stack_placement` — независимое округление краёв; префикс-округления нет |
| **T5** разбиение отрисовки | ❌ **open** | RepaintBoundary только на скроллабельных; RLE static/dynamic нет |
| **ir_validate = theorem-checker** | ❌ **open** | геом-инвариантов (reproject/conservation/baseline) в `ir_validate` нет — только no-crash guards |

---

## Phase 0 — Краеугольный камень: инвариант-гейт + мировой IR

> Без этого T1/T2 нечем проверять; делать первым.

- [ ] **P0.1 — Расширить схему мировым контрактом.** В `CleanDesignTreeNode` (schemas.py) добавить
  `transform: TransformContext | None` (rot_rad, sx, sy, tx, ty) и `world_bounds` (абсолютный AABB),
  immutable. *(сейчас только скаляр `rotation`)*
- [ ] **P0.2 — Parse перестаёт выбрасывать аффинность.** В `parser/tree.py` класть результат
  `geometry.transform_context_from_figma_node` целиком в `node.transform` (не только
  `rotation_degrees_*`). Источник истины позиции — `(tx,ty)`, AABB — производная для проверки.
- [ ] **P0.3 — Каркас проверяльщика теорем.** В `ir_validate` ввести `validate_geometry_invariants(tree)`
  с хуками под T1/T2/T3/T5; нарушение → `GenerationError`/repair, не тихий проброс. Подключить в
  `validate_screen_ir` и в `normalize` (оба пути).
- [ ] **Тест:** `test_world_ir_roundtrip` — `transform`/`world_bounds` присутствуют после parse;
  `validate_geometry_invariants` зовётся на дефолтном пути.
- **Done when:** IR несёт полную аффинность + мировой AABB; есть единая точка проверки инвариантов.

## Phase 1 — T2: Закон сохранения протяжённости (наибольший универсальный payoff)

- [ ] **P1.1 — Префикс-округление.** В `parser/numeric_rounding` добавить
  `round_axis_prefix(raw_positions) -> rounded` (телескоп: `eᵢ=round(Σraw_{j<i})`, `cᵢ=e_{i+1}−eᵢ`).
  Заменить независимое округление краёв в `round_stack_placement` и во флекс-распределении.
- [ ] **P1.2 — ≤1 свободная координата на ось.** В `layout_widget._positioned_fields`: для каждой оси
  одна свободная координата, зависимая = `P − pos − size` (вычисляется, не округляется отдельно).
- [ ] **P1.3 — Инвариант T2 в ir_validate.** `∀ контейнер: |P − (Σcᵢ + Σgᵢ + pad)| ≤ 0.5px`.
- [ ] **Тест:** `test_extent_conservation` — синтетический контейнер N детей: `Σ = round(P)` точно,
  ошибка границы не копится на глубине; assert инвариант не падает.
- **Done when:** нет суб-пиксельных щелей/нахлёстов от округления на любой глубине.

## Phase 2 — T1: Аффинный каскад (rotation + scale + translate + pivot)

- [ ] **P2.1 — Каскад в Plan/normalize.** Вычислять `W(n) = ∏ M(предки)·M(n)` один раз; хранить на
  ноде (для extract-границ — переносить накопленный `W(parent)`).
- [ ] **P2.2 — Emit через Matrix4.** В `layout_widget._apply_node_transform`: позиция из `(tx,ty)`,
  `Transform(transform: compose(translate, R(θ), S(sx,sy)), alignment: Alignment.topLeft)` — не
  `Transform.rotate` поверх AABB-координат. Перестать терять scale/skew.
- [ ] **P2.3 — Инвариант T1 в ir_validate.** `‖ expand(W(n), w, h) − world_bounds(n) ‖∞ ≤ ε`.
- [ ] **P2.4 — Extract-граница.** При выносе поддерева в виджет домножать дочерний трансформ/opacity
  на `W(parent)` (закрывает потерю трансформов предков).
- [ ] **Тест:** `test_affine_cascade` — повёрнутый+масштабированный вектор во флексе и во вложенном
  стеке: reproject == Figma AABB в пределах ε; π-кейс не дублируется.
- **Done when:** scale/skew/translate не теряются; повёрнутые ноды совпадают по центру; extract
  сохраняет контекст предков.

## Phase 3 — T3: Точность базовой линии поверх существующего strut

- [ ] **P3.1 — Компенсирующий `Δ_top`.** Поверх уже эмитящегося `StrutStyle` считать
  `Δ_top = glyph_top_offset − leading_above_flutter(strut)`; эмитить компенсацию при `|Δ_top|>ε`.
  Использовать уже спарсенные `glyph_top_offset`/`glyph_height` (tree.py:154-159).
- [ ] **P3.2 — Инвариант T3 в ir_validate.** Прогноз первого baseline ≈ Figma baseline в пределах ε.
- [ ] **Тест:** `test_baseline_gravity` — мультистрочный TEXT (`lineHeightPx=24, fontSize=14`): дрейф
  baseline ≤ ε против эталонной метрики.
- **Done when:** baseline совпадает в пределах метрик шрифта (остаток — глиф-шейпинг, требует растра).

## Phase 4 — T5: Разбиение отрисовки (static/dynamic, сохранение Z)

- [ ] **P4.1 — RLE-разбиение.** Поверх z-порядка `overlap_sweep` свернуть максимальные z-непрерывные
  static-run'ы; обернуть каждый в `RepaintBoundary` (в Plan, на нормализованном дереве).
- [ ] **P4.2 — Инвариант T5.** `∀ S-run: ∄ D-элемент с z между min/max run'а`.
- [ ] **Тест:** `test_render_partition` — стек [static-bg, interactive, static-deco]: static-bg в
  отдельном RepaintBoundary, z-порядок сохранён, нет связанности repaint с динамикой.
- **Done when:** статика изолирована от динамики без изменения стэкинга.

## Cross-cutting — чистота стадий

- [ ] **CC.1 — AST без геометрии.** Аудит `tools/dart_ast_sidecar` + `dart_postprocess`: запретить
  любое пере-округление/сдвиг координат; AST только идемпотентный синтаксис.
- [ ] **CC.2 — Units единственный владелец.** Весь блюр/sigma — только через `render_units` (T4 done);
  grep-гейт против прямого `blurRadius:{raw}`.
- [ ] **CC.3 — Доводка schema-полей до emit.** `min/max` → `ConstrainedBox`; `border_radius_corners`
  → исправить value-source (баг 52→28, читать corners, не токен).

---

## Порядок и зависимости

```
P0 (мировой IR + инвариант-гейт)
 ├─► P1  T2 сохранение         (самостоятельный, наибольший payoff)
 ├─► P2  T1 аффинный каскад     (нужен transform-field из P0.1/0.2)
 ├─► P3  T3 baseline Δ          (поверх готового strut)
 └─► P4  T5 разбиение           (поверх overlap_sweep)
CC.1–CC.3 — параллельно/после.
```

## Приёмка рефактора (единый инвариант)

Рефактор завершён, когда `ir_validate` доказывает на любом дереве:
```
∀ n:  ‖reproject(emit n) − world_bounds(n)‖ ≤ ε      (T1+T2)
   ∧  baseline(emit n) ≈ε baseline_figma(n)           (T3)
   ∧  blur(emit n) = U(r)                              (T4 ✅)
   ∧  z/layers сохранены                               (T5)
```
То есть эмит — **смена базиса с ограниченной ненакапливающейся ошибкой**, а не локальные копии.
Pixel-perfect ⟺ ε→0 для формы/геометрии/эффектов; текст — до границы `strut+Δ` (остаток = растр глифов).

## Что уже сделано — НЕ переделывать

- **T4** (`render_units.py`) — единицы блюра; только закрыть grep-гейтом (CC.2).
- **T3 strut** — `StrutStyle` эмитится; остаётся только `Δ_top` (P3.1).
- schema `min/max`, `border_radius_corners` — поля есть; доводка emit в CC.3.
- FID-21/22/26/30/33 — внедрены (см. reviewer-backlog «Внедрено»).
