# IR Graph Optimization Passes: Row-Collapse & Macro-Scroll

## Purpose

Eliminate false `STACK` containers that encode horizontal chip/button rows and force scroll wrapping on artboards taller than the standard phone viewport threshold.

## Source of truth

Implementation lives in [`src/figma_flutter_agent/generator/ir/passes/`](../../src/figma_flutter_agent/generator/ir/passes/) (not a separate `ir_optimize.py` module).

## Success criteria

- Horizontally aligned same-height stack children collapse to `ROW` or `WRAP` with computed spacing.
- Root artboards with height **> `macro_height_threshold_px`** (default **900**) lose fixed height and gain vertical scroll.
- No screen-specific conditionals; synthetic + `cash_change` integration tests pass.
- `pytest -q -m "not live_figma"` green; 896px fixtures unchanged.

---

## S5 — Implementation checklist (completed)

### Config

- [x] `macro_height_threshold_px: int = 900` in `ResponsiveConfig` (`config/models.py`)
- [x] Documented in `.ai-figma-flutter.yml.example` under `responsive:`

### Core (`generator/ir/passes/`)

- [x] Geometry tolerances in `geometry.py` (`1.0px` height, `0.5px` overlap)
- [x] `unstack.py` — geometry-only STACK → ROW/WRAP; interaction archetype guards
- [x] `scroll_host.py` — COLUMN and STACK roots; STACK retains `sizing.height`
- [x] `unpin.py` — cascaded column height unpin
- [x] `apply_ir_layout_passes` orchestrator in `__init__.py`

### Integration

- [x] `apply_layout_passes_to_context` in `planner.py`, called from `generator/planner/plan.py`
- [x] Primary + `destination_trees` / `destination_generations` covered
- [x] `inject_root_scroll_host=True` from planner helper

### IR kind mapping

- [x] `ir_kind_for_clean_node` maps `WRAP` → `WidgetIrKind.WRAP`
- [x] Dual-graph sync in each pass (`sync.py` helpers)

### Fixtures & tests

- [x] `tests/fixtures/layouts/cash_change_layout.json` + `screens.yaml` entry
- [x] `tests/test_ir_layout_passes.py` — row, wrap overflow, scroll, idempotent, destinations
- [x] `tests/test_cash_change_layout.py` — quick-sum flex row + tall root scroll

### Verification

- [x] `pytest tests/test_ir_layout_passes.py tests/test_cash_change_layout.py`
- [x] `scripts/signoff.ps1`

---

## S6–S10

Epic hardened in place; track regressions via the tests above.
