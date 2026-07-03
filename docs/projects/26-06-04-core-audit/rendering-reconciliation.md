# Rendering-engine reconciliation: последняя миля до pixel-perfect (FID-39..47)

> Дата: 2026-06-05. Глубокое исследование слоя, который мы ещё не копали: **одни и те же параметры
> Figma и Flutter (Skia/Impeller) растеризуют в РАЗНЫЕ пиксели**. Это не «что переносим» (FID-01..38),
> а «как тот же параметр рисуют два движка». Всё проверено по коду; где нужен эмпирический замер —
> помечено `[EMPIRICAL]`, где механика документирована — `[DOC]`.
> Golden как fix-loop вне скоупа; спайки ниже — **разовые замеры констант**, не CI-петля.

## 0. Три модели, которые расходятся

| Подсистема | Модель Figma | Модель Flutter | Где ломается |
|---|---|---|---|
| **Бокс ноды** | `absoluteBoundingBox` (геометрия) + `absoluteRenderBounds` (налитые пиксели вкл. stroke/shadow/blur) | один RenderBox; декорации рисуются вокруг box | FID-39 |
| **Размытие** | «radius» эффекта ≈ CSS-блюр (stdDeviation) | `BoxShadow.blurRadius` → sigma через `convertRadiusToSigma`; `ImageFilter.blur(sigma)` | FID-40/41 |
| **Текстовый бокс** | line box = `lineHeightPx`; глиф внутри по `renderBounds` (ascent/descent от шрифта) | line box = `fontSize × height`, leading распределяется `leadingDistribution`; метрики от шрифта | FID-42 |

Главный рычаг: у нас **уже есть ground-truth** (`renderBounds`, `glyph_top_offset`, `glyph_height`,
`lineHeightPx`), но эмиттер не пиннит по нему пиксели — отдаёт приблизительные множители.

---

## FID-39 — Geometry по `boundingBox`, а пиксели по `renderBounds` (для не-текста)  [P1, High]

**Текущее поведение (verified):**
- Геометрия/плейсмент берётся из `absoluteBoundingBox`: `parser/layout.py:93,188,237` (`extract_sizing`,
  `extract_stack_placement`), `tree.py`.
- `absoluteRenderBounds` используется **только** для TEXT-глифов (`tree.py:154-159`) и как fallback
  bbox в `components.py:66`. Для shape с OUTSIDE-stroke / drop-shadow / layer-blur **renderBounds
  игнорируется**.
- Частичная компенсация только для stroke-only векторов: `_effective_svg_dimensions`
  (`layout_widget.py:147-166`) раздувает ~0-высоту штриха.

**Расхождение движков:** Figma рисует OUTSIDE-обводку и тень **за пределами** boundingBox
(`renderBounds` шире). Flutter `Container` с `Border`/`boxShadow` тоже рисует за пределами box —
**но позиция/размер box заданы по boundingBox**, поэтому для absolute-стеков визуальный центр
смещён на пол-толщины обводки / на радиус тени, а при `Clip.hardEdge` край обрезается.

**Контракт:** для absolute-нод со stroke `OUTSIDE`/`CENTER`, drop-shadow или layer-blur — учитывать
expand: либо позиционировать по `renderBounds`, либо явно добавлять `Positioned` overflow margin
(stroke/2, shadow extent) и не клиппить. INSIDE-stroke не расширяет — оставить по boundingBox.

**Спайк:** по фикстурам посчитать `% нод, где |renderBounds − boundingBox| > 0.5px` и распределение
по типам (stroke align, shadow, blur). Отдельно проверить, теряется ли край при root `Clip.hardEdge`.

---

## FID-40 — Drop-shadow: `blurRadius` передаётся как радиус Figma (единицы не совпадают)  [P1, High, дёшево]

**Текущее (verified):** `layout_style._shadow_expr` (`:145`): `blurRadius: {effect.blur}`,
`spreadRadius: {effect.spread}` — радиус Figma уходит **напрямую**.

**Расхождение [DOC + EMPIRICAL]:** Flutter внутри конвертит `blurRadius → sigma`:
`convertRadiusToSigma(r) = r * 0.57735 + 0.5` (`flutter/painting/box_shadow.dart`). Гауссиан рисуется
по `sigma`. Figma-тень визуально соответствует CSS `box-shadow`, где размытие задаётся
stdDeviation ≈ `blur/2` (SVG feGaussianBlur). Значит:
- нужно Flutter `sigma ≈ figma_blur/2` → `blurRadius ≈ (figma_blur/2 − 0.5)/0.57735 ≈ 0.87·figma_blur − 0.87`.
- сейчас `blurRadius = figma_blur` → тень **визуально мягче/шире** примерно в ~1.5–2× по sigma.

Точный множитель зависит от модели Figma (B/2 vs B как stdDev) — **`[EMPIRICAL]` пин обязателен**.

**Контракт:** ввести `figma_blur_to_flutter_blur_radius(b)` (один источник истины), применять в
`_shadow_expr` и везде, где блюр→Flutter. Spread Figma→Flutter spreadRadius проверить отдельно
(модели спреда тоже разнятся).

**Спайк (½ дня):** одна нода, drop-shadow blur=24 spread=0. Рендер Flutter при candidate
`blurRadius ∈ {24, 20.9, 13.8, 12}`; экспорт Figma @3x; пиксель-оверлей; выбрать минимальный diff →
зафиксировать коэффициент. Ожидаемо ≈ `0.87·B` (если Figma stdDev=B/2) либо `B/2/0.577` ветка.

---

## FID-41 — Layer/background blur рисуется ФЕЙКОВЫМ `BoxShadow`, не `ImageFilter` (углубляет FID-06)  [P0, High]

**Текущее (verified):** `_render_native_blur_vector` (`layout_widget.py:486-525`) для `layer_blur`
рисует `Container(decoration: BoxDecoration(color.withOpacity(0.55), boxShadow: [BoxShadow(blurRadius:
layer_blur, spreadRadius: layer_blur*0.25)]))` — то есть **цветное пятно-glow вместо размытия
контента/фона**. На COLUMN/STACK (frosted-шапка) блюр вообще дропается (FID-06).

**Расхождение:** layer blur Figma размывает **сам контент** ноды; background blur — **то, что под
ней** (стекло). Ни то ни другое не моделируется `BoxShadow`. Flutter: контент-блюр =
`ImageFiltered(imageFilter: ImageFilter.blur(sigmaX,sigmaY))`; стекло = `BackdropFilter`. Sigma
для `ImageFilter.blur` = stdDeviation; Figma layer-blur radius → sigma ≈ `radius` (или `radius/2`,
**`[EMPIRICAL]`**).

**Контракт:** различать в схеме `LAYER_BLUR` (→ `ImageFiltered` на самой ноде) и `BACKGROUND_BLUR`
(→ `BackdropFilter` под полупрозрачным фоном). Удалить `BoxShadow`-фейк. Sigma через общий
конвертер (см. FID-40). `BACKGROUND_BLUR` сейчас не парсится (FID-06) — добавить.

**Спайк:** нода с `layerBlur:24` и фон-полупрозрачный → сравнить `ImageFiltered` vs текущий
`BoxShadow`-фейк vs Figma @3x. Подобрать sigma-коэффициент.

---

## FID-42 — Текстовый бокс: есть ground-truth (`glyph_*`), но нет `StrutStyle`  [P0, Очень высокий — текст это ~60% diff]

**Текущее (verified):**
- Парсер добывает точную метрику: `tree.py:154-159` →
  `glyph_top_offset = renderBounds.y − bbox.y` (leading сверху), `glyph_height = renderBounds.height`
  (реальная высота глифов).
- Эмит `Text(...)`: `style: …copyWith(height: ratio, leadingDistribution: TextLeadingDistribution.proportional)`,
  `textScaler`, `textAlign` — **`StrutStyle` отсутствует** (grep StrutStyle = 0), `glyph_top_offset`/
  `glyph_height` в сам `Text` не идут (используются лишь для input-паддинга и центрирования икон).

**Расхождение движков:** Figma кладёт текст в бокс высотой `lineHeightPx`, глиф внутри по реальным
ascent/descent (что и даёт `glyph_top_offset`). Flutter раскладывает по `fontSize × height` с
распределением leading по `leadingDistribution` — **первый/последний baseline и вертикальный центр
строки не совпадают** с Figma, особенно при `height ≠ 1.0` и нестандартных шрифтах. `proportional`
делит leading пропорционально метрикам шрифта — это приближение, а не пин.

**Контракт (глубокий рычаг):** на терминальных `Text` эмитить
`strutStyle: StrutStyle(fontSize: …, height: lineHeightPx/fontSize, forceStrutHeight: true,
leading: <из glyph_top_offset>)` — это жёстко фиксирует line box под Figma `lineHeightPx` независимо
от шрифта. Вертикальное выравнивание глифа внутри — доверять `glyph_top_offset`/`glyph_height`
(они уже посчитаны), а не `proportional`. Это потолок текста **до** растеризации глифов.

**Спайк:** мульти-строчный TEXT (`lineHeightPx=24, fontSize=14`) → сравнить (a) текущее `height+proportional`,
(b) `StrutStyle.forceStrutHeight`, (c) `+ leading из glyph_top_offset` против Figma @3x; померить дрейф
baseline в px. Зафиксировать, даёт ли strut совпадение line-box.

---

## FID-43 — Min/max sizing constraints Figma не парсятся  [P2, Medium]

**Текущее (verified):** парсятся FILL/FIXED/HUG + `layoutGrow` (`layout.py:191`); поля Figma
`minWidth/maxWidth/minHeight/maxHeight` (Auto-Layout min/max) — grep = 0, не читаются.

**Расхождение:** адаптивные компоненты с min/max во Flutter требуют `ConstrainedBox(BoxConstraints(
minWidth,maxWidth,…))`; без них элемент схлопывается/разъезжается на отличной ширине.

**Контракт:** расширить схему `Sizing` полями min/max; эмитить `ConstrainedBox`. Спайк: % фикстур/
дампов с заданными min/max.

---

## FID-44 — Цветовое пространство и интерполяция градиентов  [P2, Medium]

**Текущее (verified):** `tokens.rgba_to_argb_hex` (`:118-124`) — sRGB 0-1 → 8-бит ARGB; `colorSpace`/
P3 grep = 0; градиент-стопы как есть, интерполяция отдаётся Flutter (sRGB по умолчанию).

**Расхождение:** (1) если макет в Display-P3, прямое 8-бит-усечение сдвигает насыщенные цвета;
(2) Figma может интерполировать градиент в non-sRGB пространстве — Flutter `LinearGradient`
интерполирует в sRGB → **видимый сдвиг середины градиента** даже при совпадающих стопах.

**Контракт:** проверить, отдаёт ли REST `gradientColorSpace`/P3; при необходимости пересэмплировать
стопы (добавить промежуточные) под sRGB-интерполяцию Flutter. `[EMPIRICAL]` — насколько заметно.

**Спайк:** двухстоповый градиент контрастных цветов → Figma @3x vs Flutter; померить дельту в
середине; решить, нужен ли ресэмпл стопов.

---

## FID-45 — DPR / суб-пиксель / hairlines  [P2, Medium]

**Текущее (verified):** округление до 0.1px (`numeric_rounding.GEOMETRY_DECIMALS=1`), независимое по
краям (`round_stack_placement`); снэппинга к физическому пикселю нет; целевой DPR нигде не зафиксирован.

**Расхождение:** при DPR 2/3 дробная логическая координата/толщина (1px бордер, 0.5px позиция)
анти-алиасится по-разному у движков; 1px-hairline на DPR 3 = 3 физ.пикселя и зависит от снэпа.

**Контракт:** зафиксировать целевой DPR сравнения; для бордеров/разделителей рассмотреть
device-pixel snapping (или `BorderSide(width: 1/dpr)` для true-hairline по требованию). Согласовать
с FID-39 (расширение бокса).

---

## FID-46 — `flutter_svg` ≠ растеризатор Figma  [P2, Medium]

**Текущее (verified):** иконки/вектора → `SvgPicture.asset` (`_render_svg_picture`,
`layout_widget.py:471-483`), fit из `_svg_fit_mode` (`BoxFit.fill`/`contain`).

**Расхождение:** `flutter_svg` не 100% совпадает с рендером Figma: miter/caps/joins, `fill-rule`
(evenodd vs nonzero), SVG-фильтры/градиенты в самом SVG, гиннтинг. Для пиксель-точных сложных
векторов надёжнее **растр @3x из Figma Images API** (как уже делается для blur/filter через
`_vector_needs_baked_raster`).

**Контракт:** классификатор «сложность вектора» (фильтры, множественные пути, boolean) → растр @device-DPR;
простые штрихи/однопутёвые → SVG. По структурным сигналам, не по имени.

**Спайк:** набор иконок (стрелка, чек, логотип-мультипуть) → SVG vs PNG@3x vs Figma; найти порог
сложности, за которым SVG расходится.

---

## FID-47 — Порядок композиции внутри ноды (fill → stroke → children → effects)  [P2, Medium]

**Текущее (verified):** `box_decoration_expr` собирает `BoxDecoration(gradient/color, borderRadius,
border, boxShadow)`. Flutter рисует `decoration` ПОД ребёнком: shadow → color/gradient → image →
border, затем child; `foregroundDecoration` — поверх ребёнка.

**Расхождение:** Figma порядок краски ноды: fills → strokes → (children сверху) → effects; INSIDE-stroke
рисуется поверх fill, но под детьми — у Flutter `Border` в `decoration` тоже под детьми ✓. НО:
тень-эффект Figma считается от **renderBounds** (вкл. stroke), а Flutter `boxShadow` — от box; +
OUTSIDE-stroke поверх детей у Figma не воспроизводится `Border` (он под детьми).

**Контракт:** для OUTSIDE-stroke, который в Figma визуально поверх контента, использовать
`foregroundDecoration`/наложенный `Border`; сверить, что shadow считается от расширенного бокса (FID-39).

**Спайк:** нода fill + INSIDE-stroke + child, затем fill + OUTSIDE-stroke + child → сравнить с Figma.

---

## Приоритеты (дёшево × видно везде)

| Ранг | FID | Почему первым | Эффект |
|------|-----|---------------|--------|
| 1 | **FID-40** drop-shadow blur unit | один коэффициент, спайк ½ дня | каждая тень на каждом экране |
| 2 | **FID-42** StrutStyle | данные уже есть (`glyph_*`), точечный эмит | ~60% «текстового» diff |
| 3 | **FID-41** layer/backdrop blur primitive | убирает фейковый BoxShadow (углубляет FID-06) | каждая frosted-поверхность |
| 4 | **FID-39** renderBounds для shape | фундамент, но дороже разобрать | stroked/shadow ноды в стеках |
| 5 | FID-44/45/46/47/43 | P2, нужен спайк/замер | точечные классы |

## Единый вывод

Мы прошли «что переносим» (FID-01..38). Этот слой — **«как тот же параметр рендерят два движка»**:
- тени/блюр в **неверных единицах** (Flutter `convertRadiusToSigma`, fake-BoxShadow вместо `ImageFilter`);
- текст без **`StrutStyle`**, хотя точная метрика (`glyph_top_offset`/`glyph_height`/`lineHeightPx`) уже
  спарсена;
- геометрия по `boundingBox`, а краска по `renderBounds`.

Это **последняя миля** пиксель-перфекта; единственный непробиваемый предел за ней — глиф-шейпинг
(только растеризация TEXT). Большинство пунктов чинится одним общим конвертером единиц + точечными
эмит-правилами, по структурным сигналам, без screen-specific.

## Status (implementation snapshot)

Core reconciliation is in **`generator/render_units.py`** (calibration table), **`parser/render_bounds.py`**
(FID-39 expand + fallback), **`generator/layout_widget.py`** (BackdropFilter / ImageFiltered / soft root clip),
**`generator/layout_style.py`** (StrutStyle, calibrated shadows, foregroundDecoration). Lock-in constants:
`poetry run python scripts/render_spike.py --json`. FID-45 DPR snap is opt-in via `layout.snap_device_pixels`.

## Спайк-инфраструктура (разовая, не CI)

Минимальный harness для замера констант (FID-40/41/42/44/46): одна нода-фикстура → рендер Flutter
в нужном кандидат-параметре при фикс. DPR + загруженном шрифте → экспорт Figma @same-scale →
пиксель-оверлей (`validation/pixeldiff` уже умеет diff) → выбрать параметр с минимальным diff.
Это **измерение констант**, а не fix-loop: запускается раз, результат вшивается в конвертеры.
