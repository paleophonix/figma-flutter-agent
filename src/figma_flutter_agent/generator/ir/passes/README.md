# IR layout passes

## Purpose

Runs dual-graph layout transforms (unstack, unpin, scroll host) through a single `PassManager` with CP2 conservation checks. `PassManager` calls `sync_screen_ir_graph_to_clean_tree` before passes (reparent, stub missing clean children such as button labels, stack order) so cached LLM IR stays aligned after planner normalize/reconcile. Activation criteria live in `layout_criteria.py`; passes record field-level provenance.

## Usage Example

```python
from figma_flutter_agent.generator.ir.passes import apply_ir_layout_passes
from figma_flutter_agent.generator.ir.passes.policy import resolve_layout_pass_policy

threshold, inject_scroll = resolve_layout_pass_policy(settings.agent)
updated_ir, updated_clean = apply_ir_layout_passes(
    screen_ir,
    clean_tree,
    macro_height_threshold_px=threshold,
    inject_root_scroll_host=inject_scroll,
)
```

## LLM Context

Pass output is pre-emit layout truth; pair with `screen_ir` dumps under `.figma_debug/ir/`. Provenance mutations for passes live in `.figma_debug/provenance/<feature>.json`.
