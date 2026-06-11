# IR layout passes

## Purpose

Deterministic middle-end transforms that optimize screen IR and clean-tree graphs before Dart emission (geometry-based unstacking, height unpinning, macro scroll host injection).

## Usage Example

```python
from figma_flutter_agent.generator.ir.passes import apply_ir_layout_passes
from figma_flutter_agent.generator.ir.tree import default_screen_ir

screen_ir = default_screen_ir(clean_tree)
screen_ir, clean_tree = apply_ir_layout_passes(
    screen_ir,
    clean_tree,
    macro_height_threshold_px=900,
    inject_root_scroll_host=True,
)
```

Planner hook (`generator/ir/passes/planner.py` → `generator/planner/plan.py`) always passes `inject_root_scroll_host=True` for primary and destination trees.

## Passes

| Pass | Module | Behavior |
| --- | --- | --- |
| Unstack | `unstack.py` | STACK with monotonic horizontal children (≤1px height spread) → ROW or WRAP; clears child `stack_placement` |
| Unpin | `unpin.py` | FIXED-height COLUMN hosts with text/input descendants → HUG + min height |
| Scroll host | `scroll_host.py` | COLUMN or STACK root taller than `macro_height_threshold_px` → `scroll_axis: vertical`, IR `NAV_SCROLL_HOST` |

Unstack skips interaction stacks (back-nav, skip control, `stack_interaction_kind`). ROW vs WRAP uses Σ(child width) + gaps vs parent width.

STACK scroll hosts keep `sizing.height` for layout emit; COLUMN hosts clear fixed height.

## LLM Context

Passes run after `normalize_clean_tree` and before `render_layout_file` (and again idempotently inside `materialize_screen_code_from_ir`). Every pass mutates **both** `WidgetIrNode` and `CleanDesignTreeNode` for the same `figmaId` so legacy `render_node_body` reads updated geometry.
