# Буквальный execution-чеклист: что делать (по шагам)

> **Superseded (2026-06-05):** см. [planner-rollout-tz.md](planner-rollout-tz.md) и [systemic-core-audit.md](../../systemic-core-audit.md).

> Дата: 2026-06-05. Это «руки на клавиатуре» план: открыть файл → изменить → добавить тест → проверить.
> Контракты и обоснования — в [refactor-checklist.md](refactor-checklist.md) и [reviewer-backlog.md](reviewer-backlog.md).
> Номера строк — на 2026-06-04/05; если разъехались — искать по **имени функции**.
> Команды проверки: `poetry run pytest -q -m "not live_figma"`, после правок сайдкара — `.\tools\build_sidecars.ps1`.

## Порядок (сверху вниз, не перепрыгивать)

0. STEP 0 — разблокировать сборку (она падает на дефолте).
1. STEP 1 — FID-21 bottom-dock + viewport (самый большой blast radius).
2. STEP 2 — FID-06 frosted blur (дёшево, видно везде).
3. STEP 3 — FID-15/27 иконки (SVG вместо Material).
4. STEP 4 — FID-01 чинить ЗНАЧЕНИЯ per-corner (сейчас 52→28).
5. STEP 5 — FID-24 inline-шрифты → слот темы.
6. STEP 6 — FID-23 INPUT value/ trailing icon.
7. STEP 7 — FID-22 responsive reflow.
8. STEP 8 — FID-26 один CI-гейт (счётчик потерянных контрактов).

---

## STEP 0 — Разблокировать дефолтный `plan`  [Tier-0, Critical, S]

**Почему:** `planner.py` импортит несуществующий `generator/render_safety.py`, а `apply_render_safety_guards` дефолт `True` → `ModuleNotFoundError` на каждом дефолтном `generate`.
**Evidence:** `planner.py:268-272` импорт; `config.py:254` default True; `render_safety.py` отсутствует; функционал уже есть в `normalize.normalize_clean_tree`.

- [ ] `config.py` (~443): `unified_canonicalizer` → `default=True`.
- [ ] `generator/planner.py` (~268-287): **удалить** блок `if generation_cfg.apply_render_safety_guards:` (вместе с импортом `render_safety`). Блок normalize (252-267) уже делает reconcile + guards.
- [ ] `generator/normalize.py`: добавить чистую `validate_render_safety(tree) -> None`, которая строит `default_screen_ir(tree)` и зовёт `validate_screen_ir(screen_ir, tree, apply_guards=False)` (он внутри гоняет `_validate_stack_ghost_occlusion`, fail-closed).
- [ ] `generator/planner.py`: после normalize, если `generation_cfg.validate_render_safety`, вызвать `normalize.validate_render_safety(context.clean_tree)` (и по destination-деревьям).
- [ ] `config.py` (~254): удалить поле `apply_render_safety_guards` (логику забрал normalize); `validate_render_safety` оставить.
- [ ] `config.py` (~268-276): удалить мёртвый `deterministic_pixel_refine[_max_attempts|_threshold]` (0 использований, golden вне скоупа).
- [ ] **Тест:** `tests/test_planner_render_safety.py` — прогнать `plan` на фикстуре с дефолт-конфигом → нет ImportError; touch/scroll-гварды и ghost-validate отработали.
- [ ] **Проверка:** `poetry run pytest -q tests/test_planner_render_safety.py` + офлайн `generate` из фикстуры не падает.
- **Done when:** дефолтный `generate` доходит до write без ImportError; один путь нормализации (не два).
- **Хотфикс на 5 минут (если нужен зелёный билд прямо сейчас):** создать `render_safety.py` тонкой обёрткой, ре-экспортящей `normalize_clean_tree`/`validate_render_safety`. Но это временно — цель шага выше (консолидация), иначе вернётся дивергенция путей (CORE-02).

## STEP 1 — FID-21: bottom-dock + не фикс-высота  [P0, High blast, M]

**Почему:** нижний chrome пинится абсолютным `top`, корень — фикс `SizedBox(844)` → на устройстве ≠844 бар плавает, контент letterbox.
**Evidence:** `_buildBottomnavbar` → `Positioned(left:0, top:738.0, width:390, height:106)`; корень `SizedBox(width:390, height:844)`. Figma-нода: `vertical: BOTTOM, top:738, height:106` (без `bottom`).

**1A — bottom-anchor (дёшево, делать первым):**
- [ ] `generator/normalize.py` (в `reconcile_layout_tree` или новый проход): для ребёнка STACK с `stack_placement.vertical == "BOTTOM"` и `bottom is None`, при известной высоте родителя `H`: вычислить `bottom = round(H - top - height)`, выставить `bottom`, обнулить `top` (оставить `vertical: BOTTOM`).
- [ ] `generator/layout_widget._positioned_fields` (~1153): проверить, что ветка `vertical == "BOTTOM"` теперь получает `placement.bottom` и эмитит `bottom:` (а не падает в default `top`).
- [ ] **Тест:** synthetic 390×844 STACK + child `vertical:BOTTOM, top:738, height:106` → assert emit содержит `bottom: 0.0`, НЕ содержит `top: 738`.

**1B — viewport-fill (крупнее, вторым этапом):**
- [ ] `generator/layout_widget._wrap_root_stack_viewport` (~1332): не форсить `SizedBox(height: H)`; высоту отдать вьюпорту (Scaffold body / `LayoutBuilder` + `ConstrainedBox(minHeight: constraints.maxHeight)`), ширину можно оставить (артборд-ширина).
- [ ] **Тест:** root STACK → assert корень НЕ `SizedBox(height: 844)`; bottom-ребёнок остаётся прижат к низу при изменении высоты.
- **Done when:** на synthetic высоте 844 и 932 нижний бар прижат к низу (по `bottom:`), не плавает.

## STEP 2 — FID-06: frosted/backdrop blur  [P1, High, M]

**Почему:** `layer_blur` парсится, но `BackdropFilter`/`ImageFilter` нигде не эмитятся → стеклянные шапки/навбары плоские.
**Evidence:** ноды `layerBlur:24` (шапка) и `layerBlur:20` (навбар); grep `BackdropFilter|ImageFilter` в `background_plan.dart` = 0.

**Status (2026-06-05):** Done in `layout_widget.py` + calibrated sigma via `render_units.figma_blur_to_image_sigma` (B=24 → sigma 12.0, not raw 24). See `rendering-reconciliation.md` + `scripts/render_spike.py --json`.

- [x] `generator/layout_widget`: frosted hosts → `BackdropFilter` + `ImageFilter.blur(sigmaX/Y: B/2)`; content blur → `ImageFiltered`.
- [x] `dart:ui` `ImageFilter` import in layout header when blur present.
- [x] **Тест:** `layer_blur:24` → assert `BackdropFilter(` and `ImageFilter.blur(sigmaX: 12`.
- **Done when:** frosted-поверхность эмитит BackdropFilter; идемпотентно.

## STEP 3 — FID-15/27: кастомные иконки → SVG, не Material  [P1, High, M]

**Почему:** stroke-вектор подменяется `Icon(Icons.chevron_left, size:12)` → бледный generic-глиф.
**Evidence:** back-nav → `Icon(Icons.chevron_left, color: 0xFF52525C, size: 12.0)`; есть `_render_stroke_glyph_fallback` (1599-1620).

- [ ] `assets/exporter` + `parser/render_boundary.resolve_render_boundary_asset_keys`: гарантировать запрос SVG-экспорта для нетривиальных VECTOR (stroke-иконки); цель — `vector_asset_key` заполнен на emit (FID-27).
- [ ] `generator/layout_widget._render_stroke_glyph_fallback` (1599): вернуть `None`, если `node.vector_asset_key` задан (пусть выигрывает SVG-путь `_render_svg_picture`); Material-Icon — только когда ассета нет И экспорт невозможен.
- [ ] При Material-fallback размер брать из tap-target/визуальных bounds, не из внутренних 5×10 (сейчас size:12).
- [ ] `vector_asset_key is None` на emit для кастомного глифа → fail-loud (лог/счётчик), не тихий даунгрейд.
- [ ] **Тест:** stroke-VECTOR с `vector_asset_key` → emit `SvgPicture.asset`, НЕ `Icon(`.
- **Done when:** иконки с экспортом идут SVG; нет тихого Material-даунгрейда.

## STEP 4 — FID-01: чинить ЗНАЧЕНИЯ per-corner (сейчас 52→28)  [active FID, High, S]

**Почему:** `.only` эмитится, но значение неверное — берётся не из `borderRadiusCorners`.
**Evidence:** Figma `borderRadiusCorners.topLeft=52`, emit `BorderRadius.only(topLeft: Radius.circular(28.0))` (28 = чужой токен `radius3`/радиус карточки).

- [ ] `generator/layout_style.box_decoration_expr` / `border_radius_expr`: найти, откуда берётся значение для `BorderRadius.only` — убедиться, что читается `style.borderRadiusCorners` (per-corner map), а не scalar `border_radius`/токен.
- [ ] Сверить парс: `parser/styles` пишет `borderRadiusCorners` корректно (52/52/0/0) — проверить, что эмиттер не перетирает его scalar-радиусом.
- [ ] **Тест:** нода `borderRadiusCorners {topLeft:52, topRight:52}` → emit `topLeft: Radius.circular(52`, `topRight: Radius.circular(52`.
- **Done when:** per-corner значения == Figma; не подменяются токеном.

## STEP 5 — FID-24: inline-шрифты → слот темы  [P1, High, M]

**Почему:** `textTheme.<slot>.copyWith(fontSize, fontWeight)` инлайном → theme drift; противоречит «no inline fonts».
**Evidence:** `titleMedium.copyWith(fontSize:14, fontWeight: w600,…)`; токен `heading1=w800`, инстанс `w700` (слот декоративный).

- [ ] `generator/layout_style._text_style_delta_fields` (~289): если `font_size`/`font_weight` ноды совпадают со слотом (в пределах токена) — НЕ добавлять их в `copyWith`.
- [ ] `generator/theme_typography.resolve_text_theme_slot`: если значения не совпадают ни с одним слотом — это ошибка маппинга, чинить выбор слота, а не маскировать инлайном.
- [ ] **Тест:** нода, совпадающая со слотом → assert НЕТ inline `fontSize`/`fontWeight` в emit; остаётся только `color` при необходимости.
- **Done when:** совпадающие со слотом ноды эмитят чистый `textTheme.<slot>` (без font-инлайна).

## STEP 6 — FID-23: INPUT value и trailing icon  [P1, High, M]

**Почему:** значение склеивается из TEXT-листьев → дата-спинеры/сегменты и trailing-иконка теряют структуру.
**Evidence:** дата `[14][.][06][.][1995]` + calendar `Button menu` → склейка через `input_flex_value_text`.

- [ ] `parser/interaction.input_flex_value_text`: распознавать многосегментное значение (несколько numeric TEXT + разделители) как структурное, не склеивать слепо.
- [ ] `parser/interaction.input_trailing_chrome_nodes` / `layout_form` INPUT-ветка: trailing-иконка → `suffixIcon` у `TextField`/`InputDecoration`, не часть value-строки.
- [ ] Для дата-сегментов — корректный виджет (date field / segmented) вместо одного TextField со склеенной строкой.
- [ ] **Тест:** INPUT с 3 numeric TEXT + разделители + trailing icon → assert `suffixIcon` присутствует; value не «14.06.1995»-склейка.
- **Done when:** trailing-иконка выживает как suffix; сегментное значение не мангрится.

## STEP 7 — FID-22: responsive reflow по смыслу, не по счёту  [P1, Med, M]

**Почему:** колонка 2–4 детей рефлоится в `Row(Expanded…)` на wide → секции встают в колонки на планшете; на mobile-артборде мёртвый `LayoutBuilder`.
**Evidence:** `should_responsive_reflow` решает по `len(child_widgets) in 2..4`.

- [ ] `generator/layout_responsive.should_responsive_reflow`: рефлоу только для структурно-однородных peer'ов (близкие размеры / общий `cluster_id` / grid-дети), не по числу.
- [ ] Для артборда `<= _MOBILE_ONLY_ARTBOARD_MAX_WIDTH (480)` — не эмитить wide-бранч (`LayoutBuilder`/`Row`) вовсе.
- [ ] **Тест:** root COLUMN `[header, form, footer]` (разные размеры) → assert НЕТ `Row(Expanded` и НЕТ `LayoutBuilder`.
- **Done when:** вертикальные секции не реформируются в горизонталь; нет мёртвого бранча на мобильных.

## STEP 8 — FID-26: один CI-гейт (dropped-contracts counter)  [P1, Infra, M]

**Почему:** 4 фикстуры, 0 с `layerBlur`/`BOTTOM` → проблемные паттерны без регрессии; нужен screen-name-agnostic гейт.

- [ ] Новый модуль/чек (рядом с `design_coverage`/`bulk_ir_validate`): по дереву+emit считать нарушения:
  `layer_blur≠None ∧ 'BackdropFilter' ∉ emit`; `vertical=='BOTTOM' ∧ 'bottom:' ∉ Positioned`; `opacity<1 ∧ 'Opacity(' ∉ emit`; `vector_asset_key is None ∧ кастомный глиф`.
- [ ] Подключить в `demo-signoff --signoff-gates`: падать при счётчике > 0.
- [ ] Добавить 1–2 фикстуры с грязными паттернами (frosted bar, bottom-dock) в `tests/fixtures/layouts/`.
- [ ] **Тест:** счётчик на дереве `background` > 0; на чистой фикстуре == 0.
- **Done when:** гейт ловит класс fidelity-дропов без привязки к именам экранов.

---

## Латентное (попутно отметить, низкий приоритет)

- [ ] `layout_style.filled_button_label_text_color` форсит белый лейбл на filled-кнопке, **игнорируя** Figma `textColor` (на сейв-кнопке Figma говорил `0xFF000000`, emit дал белый). Здесь совпало; на тёмном лейбле поверх светлой filled-кнопки даст неверный цвет. → перевести на реальный контраст, не хардкод-белый.
- [ ] Независимое округление краёв (`round_stack_placement`) — суб-пиксельные щели (FID-17 в checklist).

## Verify-петля после КАЖДОГО шага

1. `poetry run pytest -q -m "not live_figma"` (+ новый тест шага зелёный).
2. После правок `tools/dart_ast_sidecar/`: `.\tools\build_sidecars.ps1`.
3. Регенерация профиля `background` из дампа (офлайн) → глазами свериться со скрином.
4. На каждый шаг — мок-фикстура в стиле `test_emit_fidelity_contracts.py` (не имя экрана).
5. Перед merge в `main`: `.\scripts\signoff.ps1`.
