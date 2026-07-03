# EPIC 1 — Pass Manager и законы сохранения

**Source:** [semantic-core.md](semantic-core.md) (lines 43–56)  
**Architecture:** Variant C — `generator/ir/passes/` (PassManager, 3 IR passes) + `geometry/invariants/` (conservation checkpoints)

## Wave checklist

### Wave 1a — Pass skeleton

- [x] `protocol.py`, `manager.py`, `registry.py` under `generator/ir/passes/`
- [x] `apply_ir_layout_passes` delegates to `PassManager` (plan + materialize call sites)
- [x] Unit: manager runs unstack → unpin → scroll_host in order

### Wave 1b — Conservation

- [x] Promote `tests/support/conservation.py` → `geometry/invariants/conservation.py`
- [x] `checkpoints.py` + CP0 pre-dedup capture in `parser/tree.py`
- [x] Four hard codes in `models.py`: `inv_node_multiset`, `inv_stack_paint_order`, `inv_style_truth`, `inv_graph_sync`
- [x] Wire CP1 (`normalize.py`), CP2 (`materialize` / PassManager), CP3 (existing emit geometry)
- [x] Tests: multiset blind-spot, stack order, graph sync, plan→materialize idempotency

### Wave 1c — Provenance + lint

- [x] `debug/provenance.py` — `.debug/provenance/<feature>.json`
- [x] PassManager + dedup CP0 + accessibility `auto_fix` mutations
- [x] `decisions: []` schema + `record_decision` stub (E2)
- [x] Grandfather lint: `node.children =` outside `ir/passes/` + allowlist

### Wave 1d — Docs + signoff

- [x] This file + `semantic-core.md` path fixes
- [x] `poetry run pytest -q -m "not live_figma"` (conservation + pass manager tests)

## Architecture notes

| Layer | Role |
|-------|------|
| **PassManager** (`ir/passes/`) | Executes **only** unstack, unpin, scroll_host |
| **Parser transforms** | `prune_generation_layout_tree`, `render_bounds_expand` — validated at CP0/CP1, **not** in PassManager |
| **Conservation** (`geometry/invariants/`) | Per-checkpoint baseline snapshots; hard fail on multiset / paint order / style / graph sync |

### Checkpoints

| ID | When | Baseline |
|----|------|----------|
| CP0_parse | Before first `prune_generation_layout_tree` in `tree.py` | `pre_dedup_tree` deep copy |
| CP0b_reprune | Before reprune in stages/planner | tree immediately before call |
| CP1_normalize | Before `reconcile_layout_tree` | post-parse tree copy |
| CP2_ir_passes | Before `PassManager.run` in materialize | clean_tree + screen_ir |
| CP3_emit | After layout emit | existing `validate_geometry_invariants` |

### Multiset baseline (E0.1 core)

`conservation_node_multiset(tree)` counts `node.id` over the walk. Ref-stubs with `children=[]` after cluster dedup **remain** one entry. `flatten_figma_node_ids` is metadata, not extra ids. `screen_ir.omit_figma_ids` subtracted when IR is in scope.

## Open risks

| Item | Status |
|------|--------|
| `fail_duplicate_clusters` gate (K layout refs) | **OPEN** — unit test exists; manual `task_management` signoff pending (E0.1) |
| 14 `reconcile_*` in `normalize.py` | Grandfather lint `unmanaged`; burn-down in E5 |

## Verification

```bash
poetry run pytest tests/test_pass_manager.py tests/test_conservation_invariants.py tests/test_conservation_harness.py tests/test_tree_mutation_lint.py -q
poetry run pytest -q -m "not live_figma"
```
