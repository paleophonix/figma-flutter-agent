# ТЗ: Стабилизация ядра Figma → Flutter компилятора (Core Hardening)

> **Superseded (2026-06-05):** см. [systemic-core-audit.md](../../systemic-core-audit.md),
> [robustness-failfast-tz.md](robustness-failfast-tz.md), [planner-rollout-tz.md](planner-rollout-tz.md).

> Статус: черновик к согласованию · Версия реестра: v1 · Дата: 2026-06-04 · Владелец: главный инженер
> Скоуп: ядро компиляции (`parser/`, `generator/`, `tools/ast_sidecar`, `pipeline/`), без UI обвязки CLI.
> Сопровождение: номера строк в §4 — точка во времени (2026-06-04). При дрейфе кода сверять по
> **именам функций/констант** (стабильнее строк; ср. риск для `layout_widget.py:466`). Разделы §3
> (корректировки) и §4 (реестр) пересматривать после каждого слияния правок ядра в `main`.

## 0. Контекст и источники

Документ консолидирует три независимых аудита ядра (внутренний `A` + два параллельных `B`, `C`)
в единый план исправлений. Цель — вывести компилятор на плато стабильности для
произвольного дерева Figma (10k+ разнородных экранов), устранив «петлю локальной отладки»,
дивергенцию путей рендеринга и нарушения математических инвариантов вёрстки.

Все находки переномерованы в единый реестр `CORE-NN`. Маппинг на исходные ID аудитов —
в колонке «Источник»; легенда меток `A`/`B`/`C` и происхождение отчётов — в **Приложении A**.
Перед составлением ТЗ спорные находки были перепроверены по коду; фактические ошибки
исходных отчётов зафиксированы в разделе 3.

### 0.1. Глоссарий

| Термин | Значение |
|--------|----------|
| **Clean tree** | Нормализованное дерево `CleanDesignTreeNode` после `build_clean_tree` (parse). |
| **Canonicalizer** | `normalize_clean_tree` — единая immutable-стадия: reconcile, render-safety, z-order (WP-A). |
| **Deterministic path** | `use_deterministic_screen: true` → `render_layout_file` / `layout_widget.py` (без LLM Dart в screen). |
| **IR path** | `use_screen_ir: true` → LLM `screenIr` → `ir_emitter.materialize_*` (после канонизатора). |
| **Fail-loud** | Пропуск контракта (AST, asset) → `GenerationError` или явный warning в отчёте, не тихий no-op. |
| **Processed dump** | `.debug/processed/<feature>_layout.json` — кэш parse; может устареть (CORE-21). |
| **Codegen AST contract** | unscale, flex-wrap, delimiter balance, text-scaler — через `ast_sidecar`, не regex. |
| **Structural heuristic** | Правило по типу+bbox+детям без имён экрана, marketing-текста и figmaId (допустимо до WP-F). |

## 1. Цели (SMART)

- **Г1.** Один и тот же Figma-дамп даёт идентичную геометрию через детерминированный и IR-путь.
  **Критерий сравнения (фиксируем явно):** нормализованное множество геометрических литералов
  (`left/top/width/height`, паддинги, `SizedBox`), извлечённых из эмитированного Dart, с допуском
  округления (`round_geometry`). НЕ сырая строка Dart и НЕ pixel-golden. Расхождение = 0 на корпусе
  мок-фикстур.
- **Г2.** Контракты render-safety (touch target, keyboard scroll, nested scroll, viewport clamp,
  z-order, ghost occlusion) применяются на **обоих** путях, включая default deterministic.
- **Г3.** Ни одного экранно-/архетип-/текст-/figmaId-специфичного ветвления в `src/`.
- **Г4.** AST-контракт применяется к каждому UI-файлу Dart независимо от размера и пути,
  либо генерация падает явной ошибкой (никаких тихих `ok: true` на пропуске).
- **Г5.** Все пороги вёрстки относительны (доля родителя/вьюпорта) или структурны; ни одной
  абсолютной пиксельной константы **вьюпорта** (Y-пороги экрана, размер канваса). Допустимы и НЕ
  подпадают под запрет: размеры touch-target (44px), bbox иконок, design-system spacing, лимиты в
  байтах (80_000) — точный allowlist в INV-3.
- **Г6.** Валидация чистая (только `raise`); нормализация возвращает новое immutable-дерево.

## 2. Глобальные инварианты (Definition of Done всего проекта)

| ID | Инвариант | Как проверяем |
|----|-----------|---------------|
| INV-1 | Единый источник геометрии: оба эмиттера получают уже нормализованное дерево | `test_ir_and_deterministic_emit_identical_geometry` |
| INV-2 | Валидация не мутирует вход; нормализация возвращает новый объект | `test_validation_is_side_effect_free`, `hash` до/после |
| INV-3 | Нет абсолютных констант **вьюпорта** (Y-пороги экрана, размер канваса) в эвристиках. **Allowlist (разрешено):** touch-target px (44), bbox иконок, spacing-токены, file-size bytes (80_000) | grep-гейт с allowlist + `test_*_scale_invariant` |
| INV-4 | Нет ветвлений по имени экрана/архетипу/тексту/figmaId и нет **хардкода контента/палитр/текста**. Структурные геометрия-эвристики (типы+bbox, без имён/текста) допустимы переходно — см. WP-F | grep-гейт + ревью |
| INV-5 | AST-контракт покрывает все UI-Dart файлы либо fail-loud | `test_*_over_80kb_still_contracted`, `test_layout_file_gets_ast` |
| INV-6 | Нет regex-мутаций Dart вне `ast_sidecar` | grep-гейт + `test_no_regex_dart_mutation` |
| INV-7 | Трансформации/прозрачность предков сохраняются на границах декомпозиции | `test_extracted_widget_inherits_ancestor_transform` |
| INV-8 | Все проходы идемпотентны | `test_*_idempotent` (повторный прогон = identity) |

## 3. Корректировки исходных отчётов (важно)

Перед планированием находки перепроверены по коду. Следующие утверждения параллельных
аудитов **неверны** и в ТЗ исправлены — план опирается на фактическое поведение:

1. **Pivot ротации.** Утверждалось, что эмиттер использует `Alignment.center`.
   Факт: `generator/layout_widget.py:466` использует `Alignment.topLeft`. Реальная проблема —
   поворот применяется поверх AABB-координат Figma (`absoluteBoundingBox` уже повёрнутой ноды),
   а не вокруг неверной точки. См. CORE-08.
2. **SVG `BoxFit` фона.** Утверждалось, что `ambient_background.py` использует `BoxFit.fill`.
   Факт: ambient везде применяет `BoxFit.cover`/`BoxFit.contain`. Реальный риск искажения
   пропорций — в `generator/layout_widget.py` (`_svg_fit_mode` возвращает `BoxFit.fill`
   для залитых векторов с обеими размерностями). См. CORE-14.
3. **«`top` молча дропается».** Факт: `parser/layout.py:extract_stack_placement` всегда
   вычисляет `top` из bounds (`node.y - parent.y`); реальная хрупкость — в каскаде fallback'ов
   и edge-инференции (`reconcile_stack_placement_top_from_edges`), а не в дропе. Понижено до части CORE-08/CORE-04.
4. **«AST skip теряет инъекцию бизнес-логики».** `codegen_pass` не инжектит бизнес-логику;
   реально теряются нормализация строк/импортов, unscale, flex-wrap, баланс скобок,
   llm-syntax-repairs, text-scaler. См. CORE-05/CORE-06.

## 4. Консолидированный реестр дефектов

Класс первопричины: **IM** — Impedance Mismatch, **LA** — Leaky Abstraction,
**SM** — State Mutation, **TE** — Transform Error, **DE** — Divergent Evolution.

| ID | Класс | Severity | Кратко | Локализация (файл:строки) | Источник |
|----|-------|----------|--------|---------------------------|----------|
| CORE-01 | DE/SM | Critical | Render-safety guards только на IR-пути; default deterministic без них; `min_touch_target` читается, но не выставляется | `ir_validate.py:1092-1166`; `layout_widget.py` (читает `min_touch_target`) | B-001, A-002 |
| CORE-02 | DE | Critical | Дивергенция путей: reconcilers + `design_artboard_width` + wallpaper + декомпозиция только в deterministic; guards только в IR | `layout_renderer.py:202-227`; `ir_emitter.py:77-88` | A-002, B-matrix |
| CORE-03 | LA | Critical | Анти-паттернинг: архетип-эвристики + хардкод `numeral="15"`, палитры play/pause | `layout_widget.py:855-1122`; `parser/layout.py` (9 reconcilers); `render_boundary.py`, `interaction.py` | A-001 |
| CORE-04 | IM | Critical | Viewport-абсолютные пороги z-order (`top>=680`, `>=760`, `width>=320`); общий для путей | `parser/stack_paint.py:13-56` | A-003, B-002 |
| CORE-05 | LA | Critical | Size gate 80KB: тихий no-op `ok:true` с неизменённым исходником | `tools/ast_sidecar.py:45-73,218-225` | A-004, B-5.5 |
| CORE-06 | LA/DE | Critical | By-policy AST-исключения: `lib/generated/*_layout.dart`, `lib/theme/`, `lib/widgets/`, layout-delegate screens вне codegen AST и flex-reconcile | `planned_dart.py:467-510`; `writer.py:284-295` | B-004, B-007 |
| CORE-07 | SM | Critical | In-place мутация общего clean-tree (guards/dedup/render_boundary/stack_paint); схемы не `frozen`; валидация с сайд-эффектами; двойная валидация | `ir_validate.py:1110-1165`; `render_boundary.py:377-382`; `schemas.py:184` | A-005, B-008 |
| CORE-08 | TE | Critical | Неполная модель трансформаций: только scalar `rotation`; `relativeTransform`/scale/skew игнор; pivot поверх AABB; потеря transform/opacity на границе extract | `parser/tree.py` (rotation); `layout_widget.py:458-468`; `ir_emitter.py:91-107` | A-007/008, B-003 |
| CORE-09 | LA/SM | High | Render-boundary всегда пинит reserved asset key; на deterministic нет asset-гейта → missing SVG/`SizedBox.shrink` в рантайме | `render_boundary.py:85-123,370-382` | B-005 |
| CORE-10 | LA | High | Regex-постпроцессинг в проде вопреки запрету; мёртвый no-op | `dart_postprocess.py:93-116,442-494,352-353` | A-006, B-010 |
| CORE-11 | LA | High | Классификация по имени (англо-локк), в т.ч. false-positive BOTTOM_NAV по camelCase `BottomNavBar`; dedup-фон по `"background"/"group"`; canvas-fallback `414×896` | `components.py:10-61,151-177`; `dedup.py:237,247` | A-011, B-006/009 |
| CORE-12 | IM | High | Корневой `Stack(clipBehavior: Clip.none)` + отрицательные координаты → overflow на широком вьюпорте | `layout_widget.py:_wrap_root_stack_viewport`, `:100-114` | C-004 |
| CORE-13 | LA | High | Декомпозиция в приватные методы не уменьшает размер файла → не обходит size gate | `layout_renderer.py:69-114` | A-010 |
| CORE-14 | IM | High | `_svg_fit_mode` → `BoxFit.fill` для залитых векторов → искажение при aspect bounds ≠ viewBox | `layout_widget.py:241-251` | C-003 (исправлено) |
| CORE-15 | SM | Medium | `reconcile_stack_placements_in_tree` применяется дважды (parse + render) | `parser/tree.py:382`; `layout_renderer.py:202` | A-009 |
| CORE-16 | SM | Medium | Гидрация виджетов с диска без сверки tree-hash → stale тело + новая геометрия | `planned_dart.py:615-657` | B-011 |
| CORE-17 | SM | Medium | Тихий snapping цвета/шрифта к ближайшему токену без warning | `ir_validate.py:903-950` | A-M1 |
| CORE-18 | LA | Medium | `skipped:"oversized"` нигде не всплывает оператору/в отчёт | `ast_sidecar.py:62-73`; потребители | A-M2, B-013 |
| CORE-19 | IM | Medium | `SizedBox.shrink()` маскирует структурно пустые flex/scroll-узлы | `layout_scroll.py`, `layout_widget.py` (многие) | B-012 |
| CORE-20 | Process | Medium | Тесты фиксируют архетипы (golden по имени экрана) вместо комбинаторики примитивов | `tests/test_*_golden.py`, `test_play_pause_codegen.py` и т.п. | A-012, B-tests |
| CORE-21 | SM | Medium | Кэш `processed/` с устаревшим `NodeType` переживает обновление парсера при `--from-dump` (нет инвалидации по semver схемы/парсера; кейс: `BOTTOM_NAV` в старом JSON) | `pipeline/dump.py`, `pipeline/incremental.py`, `sync/snapshot.py` | новое (review) |

## 5. Фазы и зависимости

```
P0 (фундамент, разблокирует остальное)
  WP-B  freeze schemas + split validate/normalize     ──┐
  WP-A  единый normalize_clean_tree (канонизатор)      ──┴─▶ нужен для WP-C, WP-D, WP-F, WP-G
  WP-E  overhaul AST-пайплайна (chunked, fail-loud)    ──── независим, но критичен

P1 (универсализация геометрии и контрактов)
  WP-C  viewport-relative z-order/placement   (после WP-A)
  WP-D  affine transform context               (после WP-A)
  WP-G  render boundary как compiled asset      (после WP-A, WP-E)
  WP-H  убрать regex → AST-правила              (после WP-E)
  WP-I  структурная классификация              (после WP-B)

P2 (де-архетипизация и устойчивость)
  WP-F  declarative component registry          (после WP-A; самый крупный)
  WP-J  hash-gating гидрации                    (после WP-B)
  WP-K  fail-loud диагностика                   (после WP-E)
  WP-L  комбинаторная тест-матрица              (сквозной, стартует параллельно P0)
```

Критический путь: **WP-B → WP-A → WP-C/WP-D/WP-G → WP-F**. WP-E параллелен и обязателен до релиза.

---

## 6. Рабочие пакеты

Формат: **Resolves / Проблема / Корень / Файлы / Дизайн (универсальный принцип) /
Задачи / Acceptance (DoD) / Тесты / Effort / Зависимости / Риски и откат.**

### WP-A. Единый immutable-канонизатор дерева

- **Resolves:** CORE-01, CORE-02, CORE-07 (частично), CORE-15.
- **Проблема:** трансформации дерева размазаны по `parse`, `render_layout_file` и `apply_ir_guards`;
  наборы не пересекаются между путями.
- **Корень:** нет единой стадии нормализации между парсером и эмиттерами.
- **Файлы:** новый `generator/normalize.py` (или `parser/canonicalize.py`); правки
  `layout_renderer.py:202-227`, `ir_emitter.py`, `ir_validate.py`, `pipeline/__init__.py`, `stages/plan.py`.
- **Дизайн:** ввести чистую функцию
  `normalize_clean_tree(tree, *, viewport, tokens, project_dir) -> CleanDesignTreeNode`,
  которая последовательно применяет ВСЕ структурно-геометрические преобразования и render-safety
  гварды, возвращая новое immutable-дерево. Оба эмиттера получают уже нормализованный вход и
  становятся чистыми `tree → dart`. Преобразования, ныне зашитые в `render_layout_file`
  (reconcilers, wallpaper-partition) и в `apply_ir_guards` (touch/keyboard/nested-scroll/clamp),
  переносятся сюда и применяются один раз, безусловно, для обоих путей.
  **Точка входа (без споров):** единственный вызов `normalize_clean_tree(...)` в
  `stages/plan.py` сразу после parse и **до** `render_layout_file` /
  `materialize_screen_code_from_ir`. Текущий вызов `apply_ir_guards` в plan-стадии заменяется этим
  вызовом и работает одинаково при `use_screen_ir: true|false`.
- **Задачи:**
  1. Спроектировать порядок проходов (parse-нормализация → archetype-агностик reconcile →
     render-safety guards → z-order) и зафиксировать его как контракт.
  2. Перенести render-safety гварды из `apply_ir_guards` в канонизатор; переписать на возврат
     нового дерева (`model_copy`), без `clean.attr = ...`.
  3. Вынести `design_artboard_width` и wallpaper-партицию в нормализованные поля дерева, чтобы
     оба эмиттера их видели одинаково.
  4. Удалить повторный вызов `reconcile_stack_placements_in_tree` в рендере (CORE-15).
  5. `validate_screen_ir` оставить только проверки (raise), без `apply_guards`.
- **Acceptance:** INV-1, INV-2; оба пути дают идентичную геометрию на корпусе фикстур;
  `min_touch_target`/`scroll_axis`/clamp присутствуют в deterministic-выводе.
- **Тесты:** `test_ir_and_deterministic_emit_identical_geometry`,
  `test_deterministic_path_applies_touch_target_and_keyboard_scroll_without_screen_ir`,
  `test_canonicalize_idempotent`.
- **Effort:** L.
- **Зависимости:** WP-B (immutable модели).
- **Риски:** меняет геометрию обоих путей → обязателен golden-rebaseline через
  `scripts/generate_fixture_goldens.py`; за флагом `runtime.unified_canonicalizer` на период миграции.

### WP-B. Freeze schemas + разделение validate/normalize

- **Resolves:** CORE-07.
- **Проблема:** модели мутабельны, валидация пишет по месту, мутации текут между стадиями.
- **Корень:** `ConfigDict(extra="forbid")` без `frozen=True`; смешение проверки и правки.
- **Файлы:** `schemas.py` (все модели дерева/IR); `ir_validate.py`; вызовы `model_copy` в
  `dedup.py`, `stack_paint.py`, `render_boundary.py`.
- **Дизайн:** включить `frozen=True` на `CleanDesignTreeNode`, `StackPlacement`, `Sizing`,
  `NodeStyle`, `WidgetIrNode`, `ScreenIr`. Все мутации заменить на `model_copy`. Любой проход,
  меняющий дерево, обязан вернуть новый корень. CI ловит скрытые мутации (FrozenInstanceError).
- **Задачи:**
  1. Включить `frozen=True`, прогнать тесты, заменить все прямые присваивания на `model_copy`.
  2. Переписать `apply_ir_guards`/`render_boundary._collapse_node`/`dedup` на возврат нового дерева.
  3. Разнести `ir_validate` на `validate_*` (raise) и `normalize_*` (возврат дерева).
- **Acceptance:** INV-2; `hash_clean_tree` идентичен до/после `validate_screen_ir`.
- **Тесты:** `test_apply_ir_guards_does_not_mutate_original_clean_tree`,
  `test_validation_is_side_effect_free`.
- **Effort:** M.
- **Зависимости:** нет (фундамент).
- **Риски:** широкий diff; делать атомарно, до WP-A.

### WP-C. Viewport-относительный z-order и клиппинг

- **Resolves:** CORE-04, CORE-12.
- **Проблема:** абсолютные Y-пороги (680/760) и ширина 320 ломают z-order на не-iPhone;
  корневой `Clip.none` + отрицательные координаты текут за вьюпорт.
- **Корень:** магические пиксельные константы привязаны к канвасу ~390×844.
- **Файлы:** `parser/stack_paint.py:13-56`; `layout_widget.py` (`_wrap_root_stack_viewport`,
  `_compose_decomposed_root_widget`); `parser/overlap_sweep.py`.
- **Дизайн:** «нижняя зона/боттом-хром» определять как долю высоты артборда (например, последние
  ~12%) + структурные признаки (BOTTOM-constraint, ширина ≈ ширине артборда), а не абсолютным `top`.
  Z-order строить через `overlap_sweep` (накопленный контекст), без magic-Y. Для корневого экрана
  применять `Clip.hardEdge` (viewport), сохраняя `Clip.none` только для внутренних стеков, где это
  осознанно нужно.
- **Задачи:**
  1. Параметризовать пороги через долю `canvas_height/width`.
  2. Заменить детект боттом-хрома на относительный + структурный.
  3. Корневой Stack экрана → `clipBehavior: Clip.hardEdge`.
  4. Удалить абсолютные константы; добавить grep-гейт (INV-3).
- **Acceptance:** INV-3; одинаковый порядок слоёв на 640/812/1024/1366.
- **Тесты:** `test_bottom_nav_paint_order_scales_with_artboard_height_1200px`,
  `test_viewport_boundary_clipping_enforcement`.
- **Effort:** M.
- **Зависимости:** WP-A (единая точка применения paint-order).
- **Риски:** возможна смена порядка на эталонных экранах → golden-rebaseline.

### WP-D. Каскадный аффинный контекст трансформаций

- **Resolves:** CORE-08.
- **Проблема:** хранится только скалярная `rotation`; scale/skew из `relativeTransform`
  игнорируются; поворот применяется поверх AABB; transform/opacity предков теряются при extract.
- **Корень:** нет накопленного 2D-affine контекста в дереве.
- **Файлы:** `parser/geometry.py`, `parser/tree.py` (парсинг `relativeTransform`); `schemas.py`
  (новое поле `transform`/`TransformContext`); `layout_widget.py:458-468`; `ir_emitter.py:91-107`.
- **Дизайн:** парсить `relativeTransform` Figma в `TransformContext`
  (translation+rotation+scale[+skew]); хранить на ноде. Эмиттер применяет `Transform` с явной
  `Matrix4` и pivot, согласованным с системой координат `Positioned`. На границе извлечения
  виджета компенсировать накопленный transform/opacity предков на узел-ссылку (обернуть
  `Opacity`/`Transform` при необходимости) либо переносить контекст внутрь извлечённого виджета.
- **Задачи:**
  1. Расширить схему: `TransformContext` (immutable).
  2. Парсинг `relativeTransform` → разложение на rotation/scale/skew/translation.
  3. Эмиттер: матричное применение с корректным pivot; покрыть π-кейс (`_skip_redundant_pi_vector_rotation`) тестом.
  4. На extract-границе восстановить opacity/transform предков.
- **Acceptance:** INV-7; повёрнутый/масштабированный узел совпадает с Figma-центром (допуск ≤1px).
- **Тесты:** `test_rotated_vector_inside_row_emits_compensated_position`,
  `test_extracted_widget_inherits_ancestor_opacity_rotation`,
  `test_transform_accumulation_across_two_nested_rotated_frames`.
- **Effort:** L.
- **Зависимости:** WP-A, WP-B.
- **Риски:** математически тонко; делать на изолированных мок-фикстурах (INV-8), без правок на live-экранах.

### WP-E. Overhaul AST-пайплайна: chunked + fail-loud

- **Resolves:** CORE-05, CORE-06, CORE-13, CORE-18.
- **Проблема:** при >80KB сайдкар тихо возвращает `ok:true` с неизменённым исходником;
  `lib/generated/*_layout.dart`/`lib/theme/`/`lib/widgets/` исключены из codegen AST и
  flex-reconcile by policy; декомпозиция не уменьшает размер файла.
- **Корень:** full-file парсинг как единственный режим + «доверие» к рендереру.
- **Файлы:** `tools/ast_sidecar.py:45-73,218-225`; `tools/dart_ast_sidecar/*` (per-range команды);
  `generator/planned_dart.py:467-510,2360-2435`; `generator/writer.py:284-295`;
  `generator/dart_postprocess.py:62`; `layout_renderer.py:69-114` (file-split).
- **Дизайн:** перейти на **поузловые AST-проходы**.
  - **EXISTS:** примитивы `extract_widget`/`replace_widget` по `figmaId`
    (`tools/ast_sidecar.py:390-403` + команды в нативном сайдкаре).
  - **ВАЖНЫЙ нюанс:** эти примитивы сами проходят через тот же 80KB-гейт на ВЕСЬ исходник —
    `extract` возвращает `snippet=None` на oversize (`_invoke_sidecar_json` → passthrough).
    Поэтому наивный chunking «поверх» большого файла не сработает.
  - **TO BUILD:** (1) оркестрация чанков (разрез по верхнеуровневым виджет-узлам, прогон правил по
    фрагментам, склейка); (2) снятие/обход size-gate для уже ограниченных фрагментов; (3) разрез
    предпочтительно делать на emit-time, до того как файл вырастет.
  Codegen-контракт (unscale, flex-wrap, баланс скобок, llm-syntax-repairs, text-scaler)
  обязателен для **любого UI-файла**, включая `lib/generated/*_layout.dart`. Превышение лимита на
  отдельном фрагменте → принудительный file-split поддерева в отдельный `*_part.dart`, повтор
  прохода; если и фрагмент не помещается — `GenerationError`, а не тихий `ok`. `skipped:"oversized"`
  пробрасывается в отчёт сборки.
- **Задачи:**
  1. Реализовать chunked-режим: разрезать файл по верхнеуровневым виджет-узлам, прогонять AST
     по частям, склеивать.
  2. Снять by-policy исключение для `lib/generated/*_layout.dart` (минимум — flex-wrap, unscale,
     delimiter-balance обязательны).
  3. Декомпозицию `_plan_layout_methods` дополнить file-split fallback при превышении порога.
  4. Убрать `_oversized_sidecar_passthrough` как успех: либо chunk, либо `GenerationError`.
  5. Пробросить статус пропуска в лог/отчёт (связка с WP-K).
- **Acceptance:** INV-5; файл >80KB получает flex-wrap/unscale/delimiter-balance либо падает явно.
- **Тесты:** `test_layout_file_over_80kb_still_gets_flex_wrap_and_unscale_rules`,
  `test_oversized_dart_does_not_silently_skip_contracts`,
  `test_layout_delegate_screen_still_has_flex_wrapped_children_in_layout_file`.
- **Effort:** L→XL (примитивы есть, но оркестрация чанков + снятие size-gate на фрагментах +
  правки нативного Dart-сайдкара; уточнить после спайка по chunking).
- **Зависимости:** нет (можно параллельно P0); но обязателен до релиза. **Блокируется Q2** (см. §10).
- **Риски:** производительность chunked-режима; склейка фрагментов. Мерить на крупных дампах.
  Альтернатива (запасная) — поднять лимит за счёт оптимизации парсера, но это не убирает
  принципиальную проблему full-file и поэтому не приоритет.

### WP-F. Де-архетипизация: декларативный реестр компонентов

- **Resolves:** CORE-03, частично CORE-11.
- **Проблема:** компилятор распознаёт архетипы (play/pause, skip-15, weekday-chip, consent-row,
  auth-pill, бренд-вордмарк) и чинит их ветвями кода с хардкодом контента/палитр.
- **Корень:** специфика вынесена в код, а не в данные/инварианты.
- **Файлы:** `parser/layout.py` (9 reconcilers), `layout_widget.py:855-1122`,
  `parser/interaction.py` (`looks_like_*`), `render_boundary.py`; целевой — декларативная таблица
  компонентов + `llm/prompts.py:SYSTEMIC_BUG_RULES`.
- **Дизайн:** заменить распознавание архетипов на:
  (а) параметрические слой-агностик инварианты (центрирование по `textAlign`, baseline-выравнивание,
  bounded-констрейнты) — общие для всех нод;
  (б) семантику компонентов из Figma Components/Variants API (декларативно), а не угадывание по
  геометрии;
  (в) для остаточных LLM-дефектов — правила в `SYSTEMIC_BUG_RULES` + детерминированный санитайзер.
  Удалить хардкод `numeral="15"` и фиксированные палитры. Каждое удаляемое ветвление заменяется
  тестом на синтетической фикстуре (не на имени экрана).
- **Граница допустимого (для исполнителя, снимает споры):**
  - **РАЗРЕШЕНЫ переходно** (до реестра компонентов): структурные эвристики *без хардкода
    контента/палитр/текста* — напр. `looks_like_bottom_docked_sheet`,
    `looks_like_input_trailing_icon_button` (геометрия + типы детей). Ветка не знает *какой* это
    экран и *какой* текст/цвет.
  - **ЗАПРЕЩЕНЫ немедленно:** архетипы с хардкодом контента/палитр/текста — play/pause `numeral="15"`,
    фикс-цвета `0xFF3F414E`/`0xFFB6B8BE`, skip-15, разбор `MM:SS`-таймстампов плеера.
  - **Критерий теста на нарушение:** если убрать ветку, ломается только конкретный архетип
    (а не общий инвариант вёрстки) — это анти-паттерн, в WP-F.
- **Задачи (итеративно, по одному архетипу):**
  1. Инвентаризация всех архетип-ветвлений (grep `looks_like_`, `_try_render_`, `reconcile_*`).
  2. Для каждого: вывести универсальный инвариант, заменить ветку, добавить generic-тест,
     удалить хардкод.
  3. Перенос компонентной семантики в Components/Variants-путь.
  4. Включить CI grep-гейт INV-4.
- **Acceptance:** INV-4; generic-фикстура «STACK 80×80 с двумя тёмными кругами, не плеер» не
  подменяется синтетическим play/pause; на корпусе случайных деревьев нет архетип-ветвлений.
- **Тесты:** `test_no_archetype_branch_changes_generic_stack`,
  `test_generic_centering_invariant_without_archetype`.
- **Effort:** L (самый крупный, итеративный).
- **Зависимости:** WP-A.
- **Риски:** временная просадка пиксель-точности на «любимых» демо-экранах — компенсируется
  универсальными инвариантами и golden-rebaseline; делать поэтапно за флагом.

### WP-G. Render boundary как compiled asset node (fail-closed)

- **Resolves:** CORE-09, CORE-14.
- **Проблема:** коллапс всегда пинит reserved asset-путь; на deterministic нет проверки наличия
  ассета → битый `SvgPicture`/`Image`/`SizedBox.shrink`. Плюс `BoxFit.fill` искажает пропорции.
- **Корень:** boundary как «обещание» ассета без гейта; fit без сверки с `viewBox`.
- **Файлы:** `parser/render_boundary.py:85-123,370-382`; `generator/layout_widget.py:241-251`;
  `ir_validate._validate_asset_paths` (поднять на оба пути).
- **Дизайн:** render-boundary — это «скомпилированный asset-узел» с сохранёнными bounds и
  (опц.) hit-test полигоном. Asset-гейт (`resolve_render_boundary_asset_keys` → unresolved)
  применять на **обоих** путях: при неразрешённом ассете — `GenerationError` (fail-closed) или
  явный плейсхолдер с предупреждением, но не тихий shrink. Fit выбирать по соотношению bounds vs
  `viewBox` ассета: при несовпадении — `BoxFit.contain` с детерминированным выравниванием, а не `fill`.
- **Задачи:**
  1. Поднять asset-валидацию на deterministic-путь (в канонизатор/plan).
  2. Неразрешённый boundary → fail-loud или явный warning-плейсхолдер.
  3. `_svg_fit_mode`: читать `viewBox` экспортированного SVG; `fill` только при совпадении aspect.
- **Acceptance:** битый/отсутствующий ассет не проходит как `SizedBox.shrink`; пропорции SVG
  сохранены при aspect-несовпадении.
- **Тесты:** `test_render_boundary_unresolved_asset_fails_generation_not_sizedbox_shrink`,
  `test_ambient_background_svg_aspect_ratio_enforcement` (на `_svg_fit_mode`).
- **Effort:** M.
- **Зависимости:** WP-A, WP-E.
- **Риски:** fail-closed может ужесточить пайплайн на неполных дампах → дать config-режим
  `strict_assets` (по умолчанию warning, в `--strict` — error).

### WP-H. Удаление regex-постпроцессинга в пользу AST-правил

- **Resolves:** CORE-10.
- **Проблема:** `dart_postprocess.py` содержит ~12 regex-трансформаций вопреки прямому запрету
  спеки; есть мёртвый no-op.
- **Корень:** исторические быстрые фиксы мимо сайдкара.
- **Файлы:** `dart_postprocess.py:93-116,442-494,352-353`; целевые правила — `tools/dart_ast_sidecar`.
- **Дизайн:** перенести `fix_text_style_height_as_ratio`, `repair_obsolete_dart_default_colons`,
  `sanitize_named_only_widget_calls`, `ensure_text_style_leading_distribution` в AST-правила.
  Удалить мёртвый `fix_misplaced_text_style_parameters`. `height`-as-ratio — лучше в parse-time
  нормализацию токенов типографики, чем в postprocess.
- **Задачи:**
  1. Реализовать соответствующие AST-правила в сайдкаре.
  2. Заменить вызовы; удалить regex-ветки и no-op.
  3. CI grep-гейт INV-6.
- **Acceptance:** INV-6; типографика и фиксы идут через AST.
- **Тесты:** `test_text_style_height_ratio_via_ast_not_regex`,
  `test_no_regex_dart_mutation_outside_sidecar`.
- **Effort:** M.
- **Зависимости:** WP-E (chunked AST, чтобы покрыть крупные файлы).
- **Риски:** граничные случаи строковых литералов — покрыть тестами.

### WP-I. Структурная классификация нод (locale-agnostic)

- **Resolves:** CORE-11.
- **Проблема:** fallback-классификация по англоязычным подстрокам имени (`btn`, `button`,
  `checkbox`); dedup-фон по `"background"/"group"`; canvas-fallback `414×896`.
- **Корень:** имя слоя как первичный сигнал.
- **Файлы:** `parser/components.py:10-61,180-226`; `parser/dedup.py:237,247`;
  `parser/tree.py` (порядок сигналов).
- **Дизайн:** приоритет — Components/Variants API + структурная геометрия (bbox, типы детей,
  `layoutMode`, prototype reactions). Имя — только как tie-breaker с обязательной геометрической
  валидацией (`validate_semantic_type_for_node`). Фон детектить чисто по доле площади к корню,
  без имени. Canvas-fallback заменить на реальные bounds корня или явную ошибку при их отсутствии.
- **Задачи:**
  1. Перевести `match_semantic_type_from_name_fallback` в строго tie-breaker роль.
  2. `_is_large_background_container` — убрать имя, оставить геометрию.
  3. Убрать `414×896` fallback (брать bounds корня; иначе fail-loud).
  4. Расширить уже существующий `validate_semantic_type_for_node` (`components.py:151-177`,
     `_raw_looks_like_bottom_cta_footer`) — он частично прикрывает false-positive BOTTOM_NAV по
     camelCase `BottomNavBar`; довести до полного structural-гейта (CTA-footer vs tab-bar по числу
     tab-peers и геометрии, а не по имени). Это база для всего WP-I.
- **Acceptance:** классификация не зависит от локали имён; фрейм с именем `input`, но без
  интерактивной структуры, не становится INPUT.
- **Тесты:** `test_frame_named_input_with_only_vectors_not_classified_as_input`,
  `test_small_group_named_background_not_pruned_as_backdrop`,
  `test_semantic_classification_locale_independent`.
- **Effort:** M.
- **Зависимости:** WP-B.
- **Риски:** возможны регрессии распознавания на «удобно названных» дампах — покрыть фикстурами.

### WP-J. Hash-gating гидрации + инвалидация кэша `processed/`

- **Resolves:** CORE-16, CORE-21.
- **Проблема:** (а) `hydrate_planned_widget_files_from_project` подмешивает тела с диска без сверки
  с tree-hash → stale тело + новая геометрия; (б) при `--from-dump` кэш `processed/` с устаревшим
  `NodeType` (напр. старый `BOTTOM_NAV` в JSON) переживает обновление парсера — нет инвалидации по
  semver схемы/парсера.
- **Корень:** гидрация решает по «валидно/не shrink», а не по соответствию дереву; дамп не несёт
  версию парсера/схемы, по которой его можно инвалидировать.
- **Файлы:** `planned_dart.py:615-657`; снапшот-хэши `sync/`; `pipeline/dump.py`,
  `pipeline/incremental.py`, `sync/snapshot.py` (semver-штамп).
- **Дизайн:** (а) гидрировать тело с диска только если его region/cluster-hash совпадает с текущим;
  иначе stale → регенерация; не сливать AST-непрошедшие stale-тела. (б) штамповать в `processed/`
  и в снапшот версию парсера/схемы (`PARSER_SCHEMA_VERSION`); при несовпадении версии —
  принудительный re-parse из raw, игнорируя `processed/`.
- **Задачи:**
  1. Прокинуть per-widget hash в снапшот и сверять при гидрации.
  2. Несовпадение hash → пропуск гидрации, регенерация.
  3. Ввести `PARSER_SCHEMA_VERSION`; писать в дамп/снапшот; сверять при `--from-dump`.
  4. Несовпадение версии → re-parse из raw, инвалидация `processed/`.
- **Acceptance:** при изменённой геометрии stale-тело с диска не используется; обновление парсера
  инвалидирует устаревший `processed/` (старый `NodeType` не переживает).
- **Тесты:** `test_hydrate_rejects_disk_widget_when_tree_hash_changed`,
  `test_from_dump_reparses_when_parser_schema_version_changed`.
- **Effort:** M.
- **Зависимости:** WP-B; согласование с `pipeline/incremental.py`.
- **Риски:** инвалидация чаще → больше регенераций; приемлемо ради корректности.

### WP-K. Fail-loud диагностика

- **Resolves:** CORE-17, CORE-18, CORE-19.
- **Проблема:** тихие деградации: snapping цветов, oversize-skip, пустые `SizedBox.shrink`.
- **Корень:** отсутствие наблюдаемости на «безопасных» путях.
- **Файлы:** `ir_validate.py:903-950` (snap), `ast_sidecar.py` (skipped), `layout_scroll.py`/
  `layout_widget.py` (пустые узлы); агрегатор отчёта сборки.
- **Дизайн:** логировать snapping цвета/шрифта с дельтой (warning); пробрасывать
  `skipped:"oversized"` в `RefineAttemptSummary`/отчёт; при структурно неожиданном нулевом числе
  детей у flex/scroll эмитить `GenerationWarning`, а не молчаливый shrink.
- **Задачи:**
  1. Warning при snap c величиной отклонения; понизить порог дельты.
  2. Проброс oversize-статуса в отчёт.
  3. Маркер/ассерт на неожиданно пустые flex/scroll.
- **Acceptance:** все три деградации видимы в логах/отчёте.
- **Тесты:** `test_color_snap_emits_warning_with_delta`,
  `test_empty_row_after_prune_emits_warning_not_silent_shrink`,
  `test_oversized_skip_surfaced_in_report`.
- **Effort:** S.
- **Зависимости:** WP-E (для oversize-проброса).
- **Риски:** шум в логах — уровни `warning`/`debug` развести аккуратно.

### WP-L. Комбинаторная тест-матрица примитивов

- **Resolves:** CORE-20 + страховка всех WP.
- **Проблема:** тесты сильны на fixture-экранах, слабы на комбинациях примитивов; golden по
  именам экранов противоречат правилу «pure mock fixtures».
- **Корень:** отладка велась на конкретных экранах.
- **Файлы:** `tests/fixtures/layouts/*.json` (новые синтетические), новые `tests/test_layout_combinatorics_*.py`.
- **Дизайн:** ввести матрицу синтетических деревьев, покрывающую пограничные комбинации
  примитивов; сделать их первичным гейтом, screen-golden — вторичным.
- **Минимальный набор кейсов:**
  - повёрнутый VECTOR внутри ROW с `width=FILL`;
  - отрицательный `itemSpacing` / перекрывающиеся absolute-дети;
  - deterministic-путь: touch target < 44px без IR;
  - layout-файл >80KB (AST-контракт);
  - render boundary без SVG на диске;
  - инкрементальный sync: изменён только внутренний cluster;
  - аккумуляция transform через 2+ вложенных повёрнутых фрейма;
  - nested scroll без IR; ghost occlusion; центрирование `textAlign` без архетипа.
- **Задачи:** сгенерировать фикстуры; написать тесты; завести как обязательный CI-гейт.
- **Acceptance:** все кейсы зелёные; screen-golden понижены до вторичного гейта.
- **Effort:** M.
- **Зависимости:** стартует параллельно P0, дополняется по мере WP.
- **Риски:** нет; чистый плюс.

---

## 7. Сводная таблица планирования

| WP | Resolves | Severity макс | Effort | Фаза | Зависит от |
|----|----------|---------------|--------|------|-----------|
| WP-B | CORE-07 | Critical | M | P0 | — |
| WP-A | CORE-01/02/07/15 | Critical | L | P0 | WP-B |
| WP-E | CORE-05/06/13/18 | Critical | L | P0 | — |
| WP-C | CORE-04/12 | Critical | M | P1 | WP-A |
| WP-D | CORE-08 | Critical | L | P1 | WP-A, WP-B |
| WP-G | CORE-09/14 | High | M | P1 | WP-A, WP-E |
| WP-H | CORE-10 | High | M | P1 | WP-E |
| WP-I | CORE-11 | High | M | P1 | WP-B |
| WP-F | CORE-03 | Critical | L | P2 | WP-A |
| WP-J | CORE-16/21 | Medium | M | P2 | WP-B |
| WP-K | CORE-17/18/19 | Medium | S | P2 | WP-E |
| WP-L | CORE-20 | Medium | M | P0→P2 | сквозной |

## 8. Drift vs project rules (что закрываем)

| Правило (AGENTS.md / universal-codegen.mdc) | Текущий факт | WP-закрытие |
|---|---|---|
| Universal algorithms only (no screen/archetype branches) | архетип-ветвления в 4 модулях | WP-F |
| No name-based classification | name-fallback + dedup name-gate | WP-I |
| No regex postprocess for layout | ~12 regex в `dart_postprocess` | WP-H |
| AST sidecar required when enabled | тихий skip >80KB + by-policy исключения | WP-E |
| IR validate before emit (для всех путей) | guards только на IR | WP-A |
| Idempotency & no side effects | мутации по месту | WP-A, WP-B |
| Universal (no viewport coupling) | `top>=680/760` в z-order | WP-C |

## 9. Протокол верификации и rollout

1. **Изоляция фикстурами.** Каждое исправление воспроизводится на синтетической фикстуре
   (`tests/fixtures/layouts/*.json`), не на `sign_in`/`music`.
2. **Сборка сайдкара.** После правок `tools/dart_ast_sidecar/` — `.\tools\build_sidecars.ps1`.
3. **Гейты.** `poetry run pytest -q -m "not live_figma"`; новые grep-гейты INV-3/4/6 в CI.
4. **Golden-rebaseline.** Только через `scripts/generate_fixture_goldens.py`; PNG руками не править.
5. **Флаги миграции.** WP-A (`runtime.unified_canonicalizer`) и WP-F (поэтапно) — за фиче-флагами,
   чтобы сравнивать старый/новый вывод на корпусе.
6. **Signoff.** `.\scripts\signoff.ps1` + `demo-signoff --strict --signoff-gates` перед merge в `main`.

## 10. Открытые вопросы (к продакту/команде)

> **Q2 и Q4 — блокирующие для распараллеливания команд.** Без ответа на них параллельные
> исполнители могут разъехаться (поднять лимит vs chunked; начать с фундамента vs с де-архетипа).
> Зафиксировать ДО старта WP-E и WP-F.

- **Q1.** `strict_assets`: при неразрешённом render-boundary ассете — падать (fail-closed) или
  ставить warning-плейсхолдер по умолчанию? (Предложение: warning по умолчанию, error в `--strict`.)
- **Q2.** **[BLOCKING для старта WP-E]** Целимся в chunked-AST (правильно, но дороже) или временно
  поднимаем лимит оптимизацией парсера? (Предложение: chunked; лимит — запасной вариант.)
- **Q3.** WP-F: какой объём пиксель-точности на демо-экранах допустимо временно потерять ради
  универсализации? Нужен порог приёмки по IoU/pixel-diff на период миграции.
- **Q4.** **[BLOCKING для распараллеливания]** Приоритет: сначала корректность default deterministic
  (WP-A/C/E) или сначала де-архетипизация (WP-F)? (Предложение: сначала фундамент P0, затем F.)

---

## Приложение A. Исходные аудиты

Колонка «Источник» в §4 ссылается на метки ниже. Все три аудита — статический read-only анализ
ядра, выполнены в окне 2026-06-03…06-04. Сетевых PR/тикетов нет (анализ агентов в чат-сессиях),
поэтому первоисточники следует положить в `docs/projects/core-audit/sources/` для исполнителей
без контекста (см. `sources/README.md`).

| Метка | Происхождение | Фокус | Особенности |
|-------|---------------|-------|-------------|
| `A` | Внутренний аудит (эта сессия, агент-инженер) | Анти-паттернинг, дивергенция путей, size gate, мутации, трансформации | Воспроизведён в git-истории отчётом предыдущего шага; найден хардкод `numeral="15"` |
| `B` | Параллельный агент-аудит #1 | Асимметрия guard'ов (default без `apply_ir_guards`), by-policy AST-исключения, render-boundary, гидрация | Самый детальный по контрактам; матрица IR vs deterministic; SYS-BUG-001..012 |
| `C` | Параллельный агент-аудит #2 («Технический синопсис») | Геометрия, трансформации, SVG-фит, кэш | Содержал 3 фактические ошибки — исправлены в §3 (pivot `topLeft`, ambient `BoxFit.cover`, `top` не дропается) |

**Маппинг меток на исходные ID** (для трассировки): `A-0NN` — пункты внутреннего отчёта;
`B-0NN` / `B-matrix` / `B-tests` — пункты и таблицы аудита B; `C-0NN` — пункты аудита C.
Где находка пришла из нескольких отчётов, указаны все (напр. `A-003, B-002`).

> **Действие:** положить дословные тексты A/B/C в `sources/` (markdown-копии) — это сделает
> колонку «Источник» полностью прозрачной. Шаблон и инструкция — в `sources/README.md`.
