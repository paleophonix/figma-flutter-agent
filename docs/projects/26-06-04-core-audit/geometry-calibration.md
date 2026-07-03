# Калибровка геометрического движка: разбор регрессии каскада матриц

> **Superseded (2026-06-05):** см. [systemic-core-audit.md](../../systemic-core-audit.md),
> [geometry-remainder-tz.md](geometry-remainder-tz.md), [planner-rollout-tz.md](planner-rollout-tz.md).

> Режим: только анализ + математическая коррекция ядра. Без UI-кода, без `figmaId`-хаков.
> Дата: 2026-06-05. Регрессия после внедрения T1 (Matrix4-каскад) + T2 (жёсткие bounds).
> Всё verified по коду: `geometry_affine.py`, `geometry_planner.py`, `geometry_invariants.py`,
> `layout_widget._apply_node_transform`, `overlap_sweep.py`.

## Сводка: 3 симптома → 3 корня (+ слепое пятно гейта)

| Симптом | Корень | Локализация |
|---------|--------|-------------|
| Векторы инвертировались и улетели за вьюпорт | **Двойная трансляция**: `Transform` несёт `..translate(tx,ty)` локальной матрицы, а позицию **уже** ставит `Positioned`/flex; pivot `topLeft` вместо центра | `geometry_affine.matrix4_compose_expr:76-84`, `layout_widget._apply_node_transform:514` |
| Флексы/инпуты схлопнулись, текст заперт в `SizedBox` | Жёсткий `slot_rect = world_aabb` навязан как фикс-ширина FILL/INPUT-нодам вместо сохранения flex-семантики | `geometry_planner._slot_rect:90-104`, `compute_flex_deltas`/flex policy |
| Презентационные слои перекрыли интерактив | Z не семантический тотальный порядок; RLE только вешает RepaintBoundary, не топит декор; demote — лишь обмен соседей | `geometry_planner._apply_repaint_rle`, `overlap_sweep.demote_overlapping_occluders:165` |
| (почему прошло) | **Слепое пятно:** T1-инвариант проверяет планировщик (`expand_aabb(world)≈world_aabb`), а НЕ эмит | `geometry_invariants._check_t1_reproject:42` |

---

## 1. `apply_matrix_cascade` (= `matrix4_compose_expr` + `_apply_node_transform`)

### Диагноз (verified)
`residual_matrix = local` (планировщик `:155`) — это **полная** локальная аффинная матрица Figma
`relativeTransform`, включающая перенос `(tx,ty)` = **позицию ноды относительно родителя**.
`matrix4_compose_expr` эмитит:
```
Transform(alignment: topLeft, transform: I ..translate(tx,ty) ..rotateZ(θ) ..scale(sx,sy))
```
Но позицию **уже** применяет layout-слот (`Positioned(left,top)` из boundingBox / flex). ⇒
**перенос дублируется**. Для фоновых векторов с большими/отрицательными `tx,ty` это удваивает
смещение → улёт за вьюпорт и видимая «инверсия» (особенно при отрицательных инсетах). Старый
fallback (`:519-535`) делал верно — поворот вокруг **центра** без лишнего translate — но Matrix4-путь
его закоротил.

### Математическая коррекция
Разложить локальную аффинную матрицу на **перенос** и **линейную часть**:
```
M_local = T(tx,ty) · L,     L = | a  c |   (поворот ∘ масштаб ∘ сдвиг)
                                | b  d |
```
**Закон разделения (T1):** перенос принадлежит layout-слоту, линейная часть — виджету `Transform`.
- **Слот** ставит позицию по boundingBox (AABB повёрнутой ноды): `Positioned(left=X, top=Y)`.
- **Transform** применяет только `L` вокруг **центра** (центр AABB = центр повёрнутого слоя):
```
θ  = atan2(b, a)
sx = hypot(a, b)
sy = hypot(c, d)
Transform( alignment: Alignment.center,
           transform: I ..rotateZ(θ) ..scale(sx, sy, 1.0) )   // БЕЗ ..translate
```
Это в точности заданная формула `M = T(dx,dy)·R(θ)·T(−origin)` при `dx=dy=0` (позицию даёт слот) и
`origin = центр` (⇒ `alignment: center`).

**Знак:** Figma и Flutter обе Y-вниз ⇒ знак `θ = atan2(b,a)` совпадает, Y-флип НЕ нужен. (Если
где-то добавлен флип Y «как в WebGL Y-вверх» — это и есть инверсия; убрать. Текущая инверсия —
от двойного переноса, не от знака.)

**Инвариант (закрыть слепое пятно):** проверять не только планировщик, но и **эмит**:
> эмитированный `Transform` обязан содержать `‖translate‖ = 0`; позиция воспроизводится слотом.
> `reproject(slot.position ⊕ emit.L, w, h) ≈ε world_aabb`. Прямой `..translate` локальной матрицы — запрещён.

---

## 2. `extract_stack_placement` + `compute_flex_deltas` (конфликт bounds ↔ нативные констрейнты)

### Диагноз (verified)
`_slot_rect` (`:90-104`) отдаёт `world_aabb` как `slot_rect`. `world_aabb` — это AABB **после** линейной
части (с раздуванием от поворота/масштаба). Навязывание его как **жёсткой ширины** FILL/flex-ноде
убивает её flex-поведение (она должна растягиваться, а не пиниться на устаревшую AABB-ширину) →
горизонтальный коллапс; для `INPUT` фикс-`SizedBox` без `minHeight`/`contentPadding` запирает текст.

### Математическая коррекция
**Закон сохранения flex-семантики:** `slot_rect` — только *базис для расчёта дельт*, не жёсткий бокс.
Размер на оси определяется режимом ноды, не пикселями AABB:
```
ось = FILL  → Expanded (растяжение по свободному пространству родителя)
ось = HUG   → интринсик (min-intrinsic ребёнка)
ось = FIXED → фикс-пиксель (единственный случай SizedBox)
```
**Распределение свободного пространства (T2, compute_flex_deltas):** для главной оси контейнера с
внутренней протяжённостью `P`:
```
free = P − Σ fixed_i − Σ gap_i − pad
Expanded-доли делят free пропорционально layoutGrow (по умолчанию поровну)
```
Жёсткий `SizedBox` ставится **только** на `FIXED`-листы; на `FILL`/flex/`INPUT` — никогда.

**`INPUT` (спец-контракт):** вместо фикс-`SizedBox` — `minHeight` + динамический `contentPadding` как
**дельта глиф↔фрейм**:
```
H_frame = sizing.height                       // высота фрейма инпута (Figma)
H_glyph = text_metrics.glyph_height           // реальная высота глифа (renderBounds)
contentPadding.vertical   = max(0, (H_frame − H_glyph) / 2)
contentPadding.horizontal = frame_inset_left / right   // из padding ноды
minHeight = H_frame
cross-axis = FILL                             // ширина тянется, не пиннится
```
Это центрирует текст по вертикали ровно как Figma и сохраняет адаптивную ширину.

**Инвариант (T2):** `|P − (Σ slot_main_extent + Σ gap + pad)| ≤ 0.5px` (уже есть
`_check_t2_stack_conservation`, но он меряет `slot_rect.width` — после фикса мерить **разрешённую**
протяжённость, не сырой AABB).

---

## 3. `overlap_sweep` (семантическая Z-валидация)

### Диагноз (verified)
`demote_overlapping_occluders` (`:165`) лишь меняет местами соседние пары (декор↔интерактив) и НЕ
гарантирует, что презентационный `renderBoundary`-вектор уходит **на дно**. Новый
`_apply_repaint_rle`/`_check_t5_repaint_z` управляют только RepaintBoundary, не Z-порядком. Итог:
презентационный слой может перекрыть Pointer Events интерактива.

### Математическая коррекция
**Z как семантический тотальный порядок (стабильная сортировка по бэндам):**
```
band(n) = 0  если presentational ∧ renderBoundary (backdrop)
        = 1  если static decor (VECTOR/IMAGE/CONTAINER без интеракции)
        = 2  если interactive (INPUT/BUTTON/CHECKBOX/…)
        = 3  если overlay/sheet
порядок = stable_sort(children, key = (band(n), figma_sibling_index))
```
Внутри бэнда — исходный порядок Figma. **Жёсткий инвариант:**
```
∀ интерактив i, ∀ презентационный p:  overlap(p, i) ⇒ z(p) < z(i)
```
Нарушение ⇒ принудительно опустить `p` ниже `i` (band 0/1), либо обернуть верхний презентационный
слой в безударный для событий контейнер (но приоритет — Z-понижение, не маскировка). Это поглощает
текущий `demote_overlapping_occluders` (частный случай обмена соседей) обобщением до тотального
порядка. T5-инвариант дополнить проверкой Z-бэндов (сейчас проверяет только RepaintBoundary-партицию).

---

## Порядок исправления

1. **`matrix_cascade` (раздел 1)** — первым: это причина «улёта» (катастрофа №1), один точечный фикс
   `matrix4_compose_expr` (убрать translate, pivot center) + расширить T1-инвариант на эмит.
2. **`compute_flex_deltas` / INPUT (раздел 2)** — снять жёсткий `slot_rect`-бокс, вернуть FILL/HUG,
   ввести `contentPadding`-дельту для INPUT.
3. **`overlap_sweep` Z-бэнды (раздел 3)** — обобщить demote до тотального порядка + T5-инвариант.

## Единый принцип калибровки

> **Layout-слот владеет переносом (T), `Transform` — только линейной частью (L) вокруг центра;
> размер на оси задаётся режимом (FILL/HUG/FIXED), а не пикселями AABB; Z — семантический тотальный
> порядок, где презентация под интерактивом.** Гейт `ir_validate` обязан проверять **эмит**, а не
> только план — иначе математически верный план даёт неверный Dart (как сейчас).

## Тест-сценарии (абстрактные, без figmaId)

- `test_transform_no_double_translate` — повёрнутая нода с `relativeTransform.tx≠0`: emit `Transform`
  без `..translate`, pivot center; reproject(slot ⊕ L) ≈ε world_aabb.
- `test_negative_inset_vector_stays_in_viewport` — вектор с `tx<0`: визуальный AABB в пределах артборда.
- `test_input_fill_width_with_content_padding` — INPUT FILL: нет фикс-`SizedBox` по ширине;
  `contentPadding.vertical = (H_frame−H_glyph)/2`; `minHeight=H_frame`.
- `test_flex_child_fill_not_pinned_to_aabb` — FILL-ребёнок Row: `Expanded`, не фикс-ширина.
- `test_presentational_renderboundary_below_interactive` — презентационный вектор, геометрически
  поверх INPUT: `z(p) < z(input)`.
- `test_t1_invariant_catches_emit_translate` — гейт ловит `..translate` в эмите (анти-регрессия).
