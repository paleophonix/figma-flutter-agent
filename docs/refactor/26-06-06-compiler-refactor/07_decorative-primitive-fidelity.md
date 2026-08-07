# 07 — Decorative primitive fidelity (plate ⊕ glyph)

**Статус:** исследование завершено 2026-07-03; реализация не начата.

## 1. Исследование

### Проверенные модули

| Область | Путь | Что уже есть |
|---------|------|--------------|
| Composite icon discovery/export | `assets/composite_icons.py` | Эвристика малых vector-групп, экспорт parent целиком, skip descendant exports |
| Vector / checkbox semantics | `parser/interaction/forms.py` | Отделение интерактивного checkbox от декоративного checkmark/pictogram |
| Stack role predicates | `generator/layout/flex_policy/stack.py` | Локальные facts для icon badge, overlays, chrome и compact controls |
| Widget emit | `generator/layout/widgets/emit/`, `generator/layout/widgets/svg.py` | Отдельные ветки SVG, raster, blur, badge и delegate emit |
| Asset boundary | `parser/boundaries/assets.py`, `stages/assets.py` | Vector discovery, raster fallback, structural asset propagation |
| Extracted paint recovery | `generator/ir/extracted_paint.py`, `generator/ir/extracted.py` | Проверки dropped/stretched badge glyph и rematerialization cached widget |
| Fidelity tiers | `generator/ir/fidelity/router.py`, `text_policy.py`, `styled_emit.py` | Маршруты native / styled / geometric / baked asset |
| Background / effects | `generator/background/`, `parser/effects.py` | Ambient/background и effect-specific разбор вне icon model |
| Navigation substrate | `generator/layout/navigation/` | Active substrate width/height и stateful nav helpers |

### Проверенные тестовые семьи

- `tests/test_home_bottom_navigation_emit_laws.py`
  - декоративный checkmark не превращается в `Checkbox`;
  - active nav substrate сохраняет собственный extent;
  - icon badge получает конечные bounds;
  - hairline stroke не удваивается.
- `tests/test_gist_add_expenses_emit_laws.py`, `tests/test_transaction_income_emit_laws.py`
  - локальные icon badge / selection glyph / substrate правила.
- `tests/test_structural_image_assets.py`, `tests/test_svg_filter_raster_fallback.py`
  - structural asset и filter/raster fallback.
- `tests/test_fidelity_regressions.py`
  - opacity, corner radii, effects и отдельные paint-регрессии.

### Текущий фактический pipeline

```text
Figma vector/group
  → asset heuristics
  → whole-group SVG | descendant assets | raster fallback
  → parser semantic predicates
  → stack/icon/navigation special cases
  → extracted-widget paint recovery
  → Dart emit
```

### Подтверждённые находки

1. **Модель `plate ⊕ glyph` уже существует неявно**, но размазана между asset discovery, checkbox predicates, stack facts, navigation helpers и extracted-widget repair.
2. `assets/composite_icons.py` умеет экспортировать небольшую vector-группу одним SVG и пропускать descendants. Это сохраняет пиксели, но одновременно **схлопывает semantic roles** без отдельного flatten contract.
3. `layout_fact_icon_badge_stack` фактически выполняет роль скрытого classifier: по нему принимаются решения о whole-group export, glyph sizing и rematerialization.
4. `generator/ir/extracted_paint.py` уже различает plate bounds и intrinsic glyph bounds, но только для icon badge и через анализ готового Dart-кода.
5. Stroke, blur, fill, `BoxFit`, substrate и glyph sizing сейчас проверяются разными ветками; общей модели primitive roles нет.
6. Fidelity router выбирает emit tier, но не объясняет decorative downgrade через единый provenance record в `design_coverage.json`.
7. Значительная часть покрытия — screen-family laws. Они полезны как regression corpus, но пока не доказывают общий decorative contract.

### Главный архитектурный разрыв

Сейчас один и тот же объект может последовательно рассматриваться как:

```text
vector group
→ composite SVG
→ checkbox candidate
→ icon badge stack
→ navigation substrate
→ extracted widget decoration
```

У стадий нет общего typed-факта, описывающего роли частей. Поэтому локальный fix на одной стадии может незаметно отменить решение другой.

---

## 2. Анализ

### Целевая модель

```text
DecorativePrimitive
  substrate: optional painted plate/background
  glyph: required or optional visual mark
  stroke: optional independent paint layer
  badge: optional overlay
  local_placement: bounds/alignment/fit per role
  flatten_policy: preserve_roles | source_flattened | baked_fallback
```

### Нормативные различия

- **Substrate** определяет plate color, shape и outer bounds; это не screen background.
- **Glyph** сохраняет intrinsic bounds и alignment внутри substrate.
- **Stroke** не должен теряться или дублироваться при SVG/raster/native переходе.
- **Badge** остаётся отдельным overlay, если source явно не flattened.
- **Baked asset** допустим как fidelity downgrade, но требует причины и provenance.

### Приоритет исследования → реализация

| Приоритет | Задача | Причина |
|-----------|--------|---------|
| P0 | Ввести read-only `DecorativePrimitiveFacts` и shadow inventory | Сначала измерить существующие plate/glyph decisions без изменения output |
| P0 | Сопоставить current special cases с ролями substrate/glyph/stroke/badge | Убрать терминологическую неоднозначность |
| P1 | Contract для flatten / baked downgrade | Whole-group SVG не должен автоматически считаться semantic success |
| P1 | Общий bounds/fit law | Заменить локальные проверки stretched glyph |
| P1 | Provenance в fidelity/design coverage | Сделать downgrade объяснимым |
| P2 | Миграция navigation/forms/icon-badge special cases | Только после shadow parity |

### Вопросы, оставшиеся открытыми

- Какие composite SVG действительно являются source-flattened, а какие скрывают plate/glyph structure?
- Где authoritative источник intrinsic glyph bounds: clean tree, SVG viewBox или exported asset metadata?
- Как отделить декоративный glyph от semantic control без повторного classifier слоя?
- Какие effects можно воспроизвести native, а какие требуют baked asset?

### Границы

- True text rasterization не входит в decorative icon contract.
- Visual refine и hierarchical visual search относятся к Program 09 и остаются в backlog.
- В Program 07 не добавлять screen/figmaId-specific fixes.

---

## 3. Рефакторинг

### Целевое состояние

- `DecorativePrimitiveContract`: roles (substrate, glyph, stroke, badge), bounds rules и flatten policy.
- Emitter не схлопывает plate+glyph без explicit source flatten fact или named fidelity downgrade.
- Fidelity router записывает tier downgrade и причину в provenance / `design_coverage.json`.
- Existing navigation/forms/icon-badge laws становятся consumers общего контракта, а не независимыми classifiers.

### Критерии готовности

- Laws R6/R8-class обобщены в contract, не размазаны по navigation/forms only.
- ≥5 general tests: plate preserved, glyph centered, stroke survives once, fit mode, color not bg-merged.
- ≥2 real corpus families проходят через один contract без screen-specific веток.
- Shadow inventory показывает все flatten/downgrade decisions с node id, source и причиной.
- Corpus icons family frequency снижается после migration, а не после golden-specific patching.
