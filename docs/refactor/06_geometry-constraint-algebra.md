# 06 — Geometry algebra (constraint ≠ position)

## 1. Исследование

### Модули

| Область | Путь |
|---------|------|
| Parser geometry | `parser/geometry.py`, `parser/geometry_frames.py`, `parser/render_bounds.py`, `parser/viewport_inset.py` |
| Affine / planner | `generator/geometry/affine.py`, `planner.py`, `slots.py`, `flex.py`, `baseline.py` |
| Invariants | `generator/geometry/invariants/` |
| Absolute fields | `parser/interaction/absolute_fields.py` |
| Placement | `parser/layout/placement.py` |
| Figma anchor | `generator/figma_anchor/` |
| IR geometry pass | `generator/ir/passes/geometry.py`, `unpin.py` |
| Normalize geometry | `generator/normalize.py` — `use_geometry_planner` |
| Validation metrics | `validation/geometry_metrics.py` |

### Тесты

- `tests/test_geometry_invariants.py`, `tests/test_geometry_planner_emit.py`
- `tests/test_placement_conservation.py`, `tests/test_elastic_bounds.py`

---

## 2. Анализ

### Что проанализировать

- Разделение **constraint** (resize operator) vs **static position** (absolute offset).
- Когда absolute → flow flatten создаёт phantom gaps / overlap.
- Viewport / anchor: кто владеет inset, кто — child offset.
- Bell centered, bottom-pinned bar — constraint routing bugs.

### Вопросы

- Одна модель в `geometry/planner` и `parser/geometry` или две несовместимые?
- Где `preserve_placement` маскирует потерю layout intent?
- Responsive: uniform scale vs breakpoint — что в scope MVP?

### Гипотезы

- Consolidated affine + constraint algebra снимет класс «wrong pin / wrong center».
- `replan_geometry_after_layout_passes` — симптом двойной правды.

### Сомнения

- Полный constraint solver как в CSS — overkill; partial solver на bands/zones достаточен.

---

## 3. Рефакторинг

### Целевое состояние

- Один документ `refactor/contracts/geometry_algebra.md`: types, operators, legal transforms.
- Parser emits constraint facts; planner resolves to Flutter slots; emitter не гадает.
- Viewport-owned regions явно помечены в clean tree / IR.
- Absolute→flow только через named transform с provenance.

### Критерии готовности

- Top-3 geometry families из corpus закрыты law + test.
- `geometry/invariants` и placement tests зелёные на transaction + home + food testbed.
- Нет новых magic padding/coordinate patches в emitter.
