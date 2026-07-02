# 02 — Conservation framework (executable laws)

## 1. Исследование

### Модули

| Область | Путь |
|---------|------|
| Geometry conservation | `generator/geometry/invariants/` — `conservation.py`, `validate.py`, `checks.py`, `models.py`, `reporting.py` |
| IR graph validate | `generator/ir/validate/graph.py` |
| Layout pass conservation tests | `tests/test_conservation_harness.py`, `tests/support/conservation.py` |
| Extent / placement | `tests/test_extent_conservation.py`, `tests/test_placement_conservation.py`, `tests/test_layout_pass_conservation.py` |
| Bounded slots | `tests/test_bounded_slot_conservation.py` |
| Z-order / unstack | `tests/test_z_order_unstack_precondition.py` |
| Contract laws (зачатки) | `generator/ir/contracts/laws.py`, `emit_recipes.py` |
| Dedup conservation | `tests/test_cluster_dedup_ref.py` |
| Normalize invariants | `tests/test_conservation_invariants.py` |
| Emitter invariants | `generator/geometry/emit_invariants.py` |

### Связанные emitter laws (примеры)

- `generator/ir/validate/root_kind.py` — `ScreenRootControlKindVetoLaw`
- `tests/test_home_bottom_navigation_emit_laws.py` и аналоги

---

## 2. Анализ

### Категории laws (что формализовать)

**Graph:** node multiset, parent validity, single implementation per extract ref.

**Geometry:** substrate vs glyph bounds, scroll cuts, overlay outside scroll coords.

**Flutter:** `Positioned`→`Stack`, `Expanded`→`Flex`, finite cross-axis in scroll.

**Semantic:** screen root ≠ control; vector ≠ checkbox without evidence.

**Paint:** sibling z-order, stroke once, full-cover → background not flow child.

### Вопросы

- Где conservation уже проверяется, но размазано по тестам без единого runner?
- Какие laws должны **block** generate, какие — report-only?
- Как связать `geometry/invariants` и `ir/validate` без дублирования?

### Гипотезы

- Executable enforcer на границах стадий снимет 30%+ compensator reconcile.
- `zip(strict)` crashes = отсутствие bijection law между parallel lists.

### Сомнения

- Слишком жёсткий enforcer заблокирует легитимные lossy transforms (prune, cluster).
- Нужен явный `OmissionReason` enum для намеренных потерь.

---

## 3. Рефакторинг

### Целевое состояние

- Единый реестр `ConservationLaw` (id, stage, check_fn, severity: block | warn).
- Runner после каждой стадии: `parse`, `normalize`, `plan`, `pre_emit`, `post_emit`.
- Каталог в `refactor/laws/` синхронизирован с `generator/ir/contracts/laws.py`.
- Compensator metric: count archetype predicates / flex branches ↓ при добавлении laws.

### Критерии готовности

- ≥10 laws в реестре с тестами.
- Один CI target: `pytest tests/test_conservation_*.py` + enforcer smoke на fixture corpus.
- Desync family (child_widgets vs sorted_children) закрыта bijection law + test.
