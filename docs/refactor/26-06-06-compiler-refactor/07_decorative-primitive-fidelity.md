# 07 — Decorative primitive fidelity (plate ⊕ glyph)

## 1. Исследование

### Модули

| Область | Путь |
|---------|------|
| Vector / checkbox laws | `parser/interaction/forms.py` |
| Stack emit | `generator/layout/flex_policy/stack.py`, `generator/layout/widgets/emit/` |
| Icon / vector assets | `parser/boundaries/assets.py` |
| Raster fallback | `tests/test_asset_raster_fallback.py` |
| Fidelity tiers | `generator/ir/fidelity/` — `router.py`, `text_policy.py`, `styled_emit.py` |
| Background / ambient | `generator/background/` |
| Effects | `parser/effects.py` |
| Stroke / paint | `generator/ir/extracted_paint.py` |
| Nav substrate | `generator/layout/navigation/` — active substrate laws |

### Тесты

- `tests/test_home_bottom_navigation_emit_laws.py`
- `tests/test_structural_image_assets.py`
- `tests/test_fidelity_regressions.py`

---

## 2. Анализ

### Модель

```text
composite icon = substrate ⊕ glyph ⊕ local placement
```

Отдельно: stroke survival, `BoxFit`, plate color vs bg, glyph intrinsic size.

### Вопросы

- Где plate dropped или merged в glyph?
- Stroke lost on export — parser или asset stage?
- T1 vector vs T2 raster — decision boundary по spec §25.

### Гипотезы

- Один DecorativePrimitive law family закроет хвост polish без per-screen hacks.
- Checkbox/nav/bell — частные случаи plate⊕glyph.

### Сомнения

- True text 1:1 требует raster — не смешивать с icon law.

---

## 3. Рефакторинг

### Целевое состояние

- `DecorativePrimitiveContract`: roles (substrate, glyph, stroke, badge), bounds rules.
- Emitter never collapses plate+glyph without explicit flatten fact from source.
- Fidelity router: tier downgrade с provenance в `design_coverage.json`.

### Критерии готовности

- Laws R6/R8-class обобщены в contract, не размазаны по navigation/forms only.
- ≥5 tests: plate preserved, glyph centered, stroke, fit mode, color not bg-merged.
- Corpus icons family frequency ↓ после refactor.
