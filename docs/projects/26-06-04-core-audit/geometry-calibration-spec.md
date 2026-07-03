# ТЗ: Калибровка геометрического движка (консолидированное)

> Объединяет: [geometry-calibration.md](geometry-calibration.md) (первичный разбор) + глубокое
> параллельное ревью (det/reflection, reconcile-skip, T2-misapply) + теорию T1–T5
> ([translation-theory.md](translation-theory.md)). Все корни verified по коду 2026-06-05.
> Режим: анализ + математическая коррекция. Без UI-кода, без `figmaId`-хаков.
> Симптомы (SignUp): векторы инвертированы/улетели; флексы/инпуты схлопнулись; презентация поверх
> интерактива. Это **смешение трёх систем координат**, не одна ошибка знака.

## 0. Карта функций: ТЗ ↔ репозиторий (verified)

| Имя в ТЗ | Реальность в репо |
|----------|-------------------|
| `apply_matrix_cascade` | `geometry_affine.compose_affine` + `geometry_planner._plan_node` (`world=parent·local`) + эмит `geometry_affine.matrix4_compose_expr` ← `layout_widget._apply_node_transform:514` |
| `extract_stack_placement` | `parser/layout.extract_stack_placement` (AABB из `absoluteBoundingBox`) + `parser/geometry_frames.hydrate_geometry_frame` (`layout_rect.x/y = local.tx/ty`) |
| `compute_flex_deltas` | **отсутствует**; ближайшее: `layout_widget._flex_input_content_padding`, `layout_flex_policy.resolve_flex_wrap`, `geometry_planner.FlexSolution` (пустой) |
| матрицы в `ir_emitter` | их там нет — делегирует в `render_node_body`; матрицы в `_apply_node_transform` |

Активация: `generation.use_geometry_planner: true` → `normalize_clean_tree` → `plan_geometry_tree` → emit с `layout_slot`/`residual_matrix`.

## 1. Реестр корневых причин (RC-1..RC-10, verified)

| RC | Симптом | Класс | Локализация (verified) |
|----|---------|-------|------------------------|
| **RC-1** | Оси инвертированы (зеркало/шир) | потеря det/shear | `parser/geometry.py:243-244` (`hypot`), `geometry_frames.py:64-71` (реконструкция `cos·sx…`, det>0 всегда) |
| **RC-2** | Улёт за viewport | двойной перенос | `geometry_affine.matrix4_compose_expr:80` `..translate(tx,ty)` + `Positioned`/flex уже ставит позицию |
| **RC-3** | Сдвиг при повороте | неверный pivot | `matrix4_compose_expr:78` `alignment: topLeft` (надо center); старый верный fallback `layout_widget:519-535` закорочен |
| **RC-4** | AABB ≠ transform | смешение `layout_rect`↔`world_aabb` | `geometry_frames.py:81-86` (`layout_rect.x=local.tx`), `geometry_planner._plan_node:132` (`expand_aabb` перезаписывает `world_aabb`) |
| **RC-5** | INPUT/flex ширина ≈ глиф | жёсткий bound из AABB | `geometry_planner._slot_rect:90-104` (`world_aabb` как ширина), `layout_widget._ensure_positioned_stack_bounds` (фикс `width` из bbox) |
| **RC-6** | Flex не растягивается | reconcile-skip + пустой FlexSolution | `layout_flex_reconcile.py:76-77` (`if layout_slot is not None: continue`), `geometry_planner:149` (`FlexSolution(main_axis=…)` без wrap) |
| **RC-7** | Ложные жёсткие ширины | T2 неверно применён к STACK | `geometry_invariants._check_t2_stack_conservation:61-82` суммирует `slot_rect.width` Positioned-детей как flex-span |
| **RC-8** | Презентация ест pointer events | Z не тотальный порядок | `overlap_sweep.demote_overlapping_occluders:165` (обмен соседей), `_apply_repaint_rle` (только RepaintBoundary, не Z) |
| **RC-9** | Bottom-pin сломан у boundary | принудительный `free_v=top` | `layout_widget._positioned_fields_from_pins` для `render_boundary` |
| **RC-10** | Регрессия прошла гейт | слепое пятно инварианта | `geometry_invariants._check_t1_reproject:42` валидирует **планировщик** (`expand_aabb(world)≈world_aabb`), не **эмит** |

## 2. Математические коррекции

### 2.1 `apply_matrix_cascade` — единый фикс RC-1+RC-2+RC-3 (эмит линейной части без потерь)

**Проблема:** двойная декомпозиция. `transform_context`/`affine2_from_figma_node` ужимают матрицу в
`rotation+hypot` (теряя det/shear), а `matrix4_compose_expr` ещё раз раскладывает в `rotateZ+scale`
и добавляет лишний `translate`.

**Правильно — хранить и эмитить СЫРУЮ линейную часть `[a,b,c,d]`:**
1. `affine2_from_figma_node`: класть **сырые** `a,b,c,d,tx,ty` из `relativeTransform` (НЕ
   реконструировать из rotation+hypot). `Affine2` уже несёт эти поля.
2. **Закон разделения каналов:** перенос принадлежит layout-слоту, линейная часть — `Transform`.
   - Слот: `Positioned(left,top)` из позиции (см. 2.2).
   - Эмит: Matrix4 из сырого 2×2 линейного блока, **без translate**, pivot центр:
```
Matrix4( a, b, 0, 0,   c, d, 0, 0,   0,0,1,0,   0,0,0,1 )   // column-major; tx=ty=0
Transform(alignment: Alignment.center, transform: <выше>, child: …)
```
   Это точно представляет поворот∘масштаб∘**шир∘отражение** (det любой), без полярной потери.
3. **Знак Y:** обе системы Y-вниз ⇒ Y-флип НЕ нужен; инверсия была от потери det (RC-1) и двойного
   переноса (RC-2), не от знака θ.
4. **Альтернатива при det<0 / сильном шире:** тиром в RASTER (экспорт ассета), не пытаться
   воспроизвести зеркало декларативно (см. T4-инвариант).

Эквивалент заданной формулы `M=T(dx,dy)·R(θ)·T(−origin)` при `dx=dy=0` (позиция у слота),
`origin=центр` ⇒ `alignment: center`, с заменой `R·S` на сырой линейный блок (точнее при reflection/shear).

### 2.2 `extract_stack_placement` / `hydrate_geometry_frame` — разнести RC-4

**Проблема:** `layout_rect.x/y = local.tx/ty` (позиция в системе Figma-родителя), а `world_aabb`
перезаписывается `expand_aabb` — два несогласованных источника позиции/размера.

**Разделить три величины:**
```
intrinsic_size   = (layout_w, layout_h)                  # неповёрнутый локальный бокс
placement_origin = compose(parent_world, local)·(0,0)    # позиция в координатах stack-родителя
placement_aabb   = absoluteBoundingBox − parent_bbox     # legacy, для axis-aligned быстрого пути
```
- `Positioned` использует `placement_origin` (для повёрнутых) **или** `placement_aabb.min`
  (axis-aligned), **никогда** `world_aabb.width/height` как `Positioned.width/height` повёрнутой ноды.
- `world_aabb` остаётся **производной** только для T1-проверки, не для позиционирования.

### 2.3 `compute_flex_deltas` (ввести) — RC-5+RC-6+RC-7

**Закон сохранения flex-семантики:** `slot_rect` — базис для дельт, не жёсткий бокс. Размер по режиму:
```
FILL  → Expanded (делёж свободного места родителя по layoutGrow)
HUG   → интринсик (min-intrinsic)
FIXED → SizedBox (единственный случай фикс-пикселя)
```
**Распределение (главная ось контейнера span `P`):**
```
free = P − Σ fixed_i − Σ gap − pad
Expanded-доли ∝ layoutGrow (по умолчанию поровну)
```
**`INPUT` (спец-контракт, RC-5):** вместо фикс-`SizedBox` — `minHeight` + `contentPadding` = дельта глиф↔фрейм:
```
H_frame = sizing.height ;  H_glyph = glyph_height ;  a = glyph_top_offset
L_f = leading_above_flutter(font_size, ratio)        # уже есть в planner
p_t = clamp(a − L_f, 0, H_frame − H_glyph)
p_b = H_frame − p_t − H_glyph
minHeight = max(H_frame, 48)                          # универсальный touch-минимум
width: FILL (Expanded под bounded-родителем), НИКОГДА = ширина глиф-bbox
contentPadding = LTRB(pad_l, p_t, pad_r, p_b)
```
Связь с T3: `delta_top` планировщика = `p_t`; **нельзя** одновременно `Padding(delta_top)` и
`contentPadding.top` — один канал (вычесть дубль).

**RC-6:** `layout_flex_reconcile` НЕ должен `continue` на `layout_slot`; либо wrap'ы (`EXPANDED`/
`FLEXIBLE_LOOSE`) кодируются в `layout_slot.wraps` планировщиком и эмитятся до финализации Positioned.
`FlexSolution` обязан нести wrap, а не только `main_axis`.

**RC-7:** `_check_t2_stack_conservation` применять **только** при `backend == FLEX`. Для `STACK` дети —
`Positioned` (не упакованы по ширине); там действуют T1 (pin-closure) и T5 (z), а не Σширин.

### 2.4 `overlap_sweep` — семантический тотальный Z-порядок (RC-8, RC-9)

```
band(n) = 0  presentational ∧ render_boundary (backdrop)
        = 1  static decor (VECTOR/IMAGE/CONTAINER без интеракции)
        = 2  interactive (INPUT/BUTTON/CHECKBOX/…)
        = 3  overlay/sheet
π = stable_sort(children, key=(band(n), figma_sibling_index))
Инвариант:  ∀ decor d, interactive i:  overlap(AABB(d),AABB(i)) ⇒ index_π(d) < index_π(i)
```
Нарушение ⇒ принудительно опустить `d` ниже `i` (не эвристика обмена соседей). Обобщает
`demote_overlapping_occluders` (частный случай). RC-9: `render_boundary` не должен слепо форсить
`free_v=top` — bottom-pin сохраняется отдельно от Z-бэнда.

## 3. Инварианты в `geometry_invariants` (закрыть слепое пятно RC-10)

| ID | Проверка |
|----|----------|
| **T1-placement** | `Positioned.origin = compose(parent,local)(0,0)` (или `placement_aabb.min` при axis-aligned), не `world_aabb.min` для повёрнутых |
| **T1-emit** | эмитированный `Transform` несёт `tx=ty=0` (перенос — у слота); прямой `..translate` локальной матрицы запрещён |
| **T2-flex** | conservation `|P−(Σslot_main+gap+pad)|≤0.5px` **только** для `backend==FLEX`; не для STACK |
| **T4-det** | `det(L)=a·d−b·c < 0 ⇒ backend RASTER/BOUNDARY`; запрет `scale(sx,sy)` из `hypot` |
| **T5-z** | `∀ decor,interactive: overlap ⇒ index(decor) < index(interactive)` |

Ключевой принцип: **гейт проверяет ЭМИТ, а не только план** — иначе математически верный план даёт
кривой Dart (как сейчас: `_check_t1_reproject` валидирует `expand_aabb(world)`, а двойной translate в
эмите проходит мимо).

## 4. Порядок калибровки (инженерный, без кода)

1. **`affine2_from_figma_node`** — сырые `a,b,c,d` + детект `det` (RC-1). База для всего.
2. **`matrix4_compose_expr`** — Matrix4 из линейного блока, **без translate**, pivot center (RC-2/3);
   добавить T1-emit инвариант.
3. **`hydrate`/placement** — разнести `intrinsic_size` / `placement_origin` / `world_aabb` (RC-4).
4. **`compute_flex_deltas` + reconcile** — FILL/HUG/FIXED семантика, INPUT contentPadding, снять
   `continue` на `layout_slot`, наполнить `FlexSolution.wraps` (RC-5/6).
5. **T2 only-FLEX** (RC-7).
6. **Semantic Z-bands** перед `sort_absolute_stack_children` (RC-8/9).
7. Прогон `tests/test_geometry_planner_emit.py` + мок-фикстуры (без SignUp-имён).

## 5. Тест-сценарии (абстрактные, без figmaId)

- `test_affine_preserves_determinant` — `relativeTransform` с отражением (det<0): emit не зеркалит ось
  (raw a,b,c,d) либо тир RASTER; reproject ≈ε.
- `test_transform_no_double_translate` — нода `tx≠0`: `Transform` без `..translate`, pivot center;
  `reproject(slot ⊕ L) ≈ε world_aabb`.
- `test_negative_inset_vector_stays_in_viewport` — `tx<0`: визуальный AABB в артборде.
- `test_input_fill_width_with_content_padding` — INPUT FILL: нет фикс-`SizedBox`;
  `contentPadding.vertical=(H_frame−glyph)/2`; `minHeight≥48`.
- `test_flex_child_fill_not_pinned_to_aabb` — FILL-ребёнок Row: `Expanded`, не фикс-ширина (reconcile
  не скипнул `layout_slot`).
- `test_t2_conservation_skips_stack` — STACK не триггерит extent-conservation.
- `test_presentational_renderboundary_below_interactive` — декор поверх INPUT: `z(d)<z(i)`.
- `test_t1_invariant_catches_emit_translate` — гейт ловит `..translate` в эмите (анти-регрессия).

## 6. Единый принцип

> **Сырая линейная часть (a,b,c,d) эмитится как есть** (det/shear/reflection сохранены) вокруг центра;
> **перенос — у layout-слота** (один канал позиции, не два); **размер — по режиму** (FILL/HUG/FIXED),
> не по пикселям AABB; **Z — семантический тотальный порядок** (презентация под интерактивом);
> **гейт `ir_validate` проверяет эмит, не только план.** Det<0/шир, не воспроизводимые декларативно,
> уходят в RASTER-тир, не в искажённый Matrix4.
