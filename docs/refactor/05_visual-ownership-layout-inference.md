# 05 — Visual ownership & layout inference

## 1. Исследование

### Модули

| Область | Путь |
|---------|------|
| Layout reconcile | `parser/layout/` — `reconcile_registry.py`, `reconcilers_align.py`, `reconcilers_media.py`, `reconcilers_grid.py`, `placement.py`, `sizing.py` |
| Overlap / sweep | `parser/overlap_sweep.py`, `parser/z_dag.py`, `parser/z_bands.py` |
| IR layout passes | `generator/ir/passes/sectionize.py`, `scroll_host.py`, `unstack.py`, `unpin.py`, `layout_criteria.py` |
| Flex policy | `generator/layout/flex_policy/` — `row.py`, `column.py`, `stack.py`, `extents.py`, `wrap.py` |
| Widget emit dispatch | `generator/layout/widgets/emit/` |
| Stack chrome | `generator/layout/stack_chrome.py` |
| Navigation layout | `generator/layout/navigation/` |
| Boundaries / grouping | `parser/boundaries/collapse.py`, `boundaries/heuristics.py` |
| Sectionize tests | `tests/test_sectionize_root_pass.py` |

### Тесты

- `tests/test_layout_*.py` (широкий корпус)
- `tests/test_flex_extents.py`, `tests/test_ir_layout_passes.py`

---

## 2. Анализ

### Модель (целевая теория)

Layout ≠ copy coordinates. Это выбор гипотезы:

```text
Candidate A: Stack
Candidate B: Column
Candidate C: Row of groups
Candidate D: scroll body + fixed overlay
```

Score: geometric error, exceptional offsets, complexity, Flutter validity, repetition.

**Visual ownership graph** (отдельно от Figma parent):

- surface owns content;
- icon plate owns glyph;
- card owns dividers;
- navbar owns substrate + destinations.

### Вопросы

- Где reconcile passes конфликтуют (product hero, bottom nav, grid)?
- Сколько layout решений принимается в parser vs IR vs emitter?
- MDL / scoring — есть ли зачатки в `layout_criteria.py`?

### Гипотезы

- 461 flex if/elif — следствие отсутствия scored hypotheses.
- Card surface + content as siblings — ownership failure, не emitter typo.

### Сомнения

- Full search по гипотезам дорог на больших деревьях — нужен beam / tiered search.

---

## 3. Рефакторинг

### Целевое состояние

- Ownership pass: строит `visual_ownership` edges до layout commit.
- Layout chooser: ≥2 candidates на неоднозначный subtree, winner по scorecard.
- Reconcile registry: каждый pass declare conflicts + priority.
- Удаление screen-specific reconcile в пользу ownership laws.

### Критерии готовности

- 5 ownership laws с тестами (card, icon, navbar, field host, scroll chrome).
- Benchmark: exceptional offset count ↓ на corpus sample без golden update.
- Документирован scorecard в `refactor/contracts/layout_hypothesis.md`.
