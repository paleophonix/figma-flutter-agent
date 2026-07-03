# 04 — Extraction & dedup as bijection (acyclic graph)

## 1. Исследование

### Модули

| Область | Путь |
|---------|------|
| Cluster signatures | `parser/dedup/signatures.py`, `clusters.py`, `prune.py`, `hydrate.py`, `instances.py`, `hints.py` |
| Widget extraction | `generator/widget_extractor.py`, `generator/widget_extraction/` — `collect.py`, `eligibility.py`, `gates.py`, `scorer.py`, `shape.py` |
| Planner subtree | `generator/planner/cluster_subtree.py` — `plan_subtree_widgets`, `apply_true_subtree_pruning` |
| Delegate repair | `generator/planned/reconcile/delegate_repair.py` |
| Prune policy | `generator/widget_extraction/policy.py` |
| Tree walk (cycles) | `parser/tree_walk.py` — `CleanTreeCycleError` |
| Assets on pruned nodes | `parser/boundaries/assets.py` — `resolve_pruned_cluster_instance_assets` |
| Normalize asset index | `generator/normalize.py` |

### Тесты

- `tests/test_cluster_dedup_ref.py`
- `tests/test_pruned_cluster_assets.py`
- `tests/test_plan_asset_resolution.py`

### Debug

- `plan.dart`, `widget_enrich.json`, empty widget bodies в `screen.dart`
- Hang: silence после `Subtree widgets rendered` (см. `generator/planner/plan.py`, `timing.py`)

---

## 2. Анализ

### Что проанализировать

- Cluster = equivalence class под **structural signature** — что входит в signature?
- Extraction = bijection call-site ↔ definition — где нарушается (empty body, self-recursion, split)?
- Acyclicity: delegate graph, cluster representative lookup, prune closure.
- Complexity: O(nodes × assets) hotspots (post H1 fix — где ещё full scan?).

### Вопросы

- Почему status bar кластеризуется с tab bar?
- Когда pruned leaf должен сохранять per-instance asset vs family asset?
- `materialize_missing_cluster_delegate_files` — все входы терминальны?

### Гипотезы

- Signature слишком грубый → wrong merge; слишком тонкий → explosion.
- Cycle + missing visited-set = hang, не «мистический Flutter».

### Сомнения

- Полная bijection proof на всём extractor — дорого; начать с cluster delegate path.

---

## 3. Рефакторинг

### Целевое состояние

- Formal cluster signature spec в `refactor/contracts/cluster_signature.md`.
- Extraction graph: DAG by construction; cycle → `CleanTreeCycleError` на всех walks.
- Bijection test: каждый `Cluster*Widget` в plan имеет ровно one body source.
- Closure audit: extracted node ids ⊆ clean tree ids (conservation link с программой 02).

### Критерии готовности

- Нет hang на plan normalize при N nodes, M assets (budget test).
- Regression: empty cluster body, self-recursion, two-widget split — closed.
- `food_add_new_items` + `9_a_home_bottom_navigation` проходят plan stage < 30s (smoke).
