# IR layout passes

## Purpose

Runs dual-graph layout transforms (`sectionize`, `unstack`, `unpin`, `scroll_host`) through a single `PassManager` with CP2 conservation checks. `sectionize` converts absolute root `STACK` screens into responsive `COLUMN` section hosts when Y-bands are recoverable. `PassManager` calls `sync_screen_ir_graph_to_clean_tree` before passes so cached LLM IR stays aligned after planner normalize/reconcile. Activation criteria live in `layout_criteria.py` and `sectionize.py`; passes record field-level provenance.

## Usage Example

```python
from figma_flutter_agent.generator.ir.passes import apply_ir_layout_passes
from figma_flutter_agent.generator.ir.passes.policy import resolve_layout_pass_policy

threshold, inject_scroll, responsive_reflow = resolve_layout_pass_policy(settings.agent)
updated_ir, updated_clean = apply_ir_layout_passes(
    screen_ir,
    clean_tree,
    macro_height_threshold_px=threshold,
    inject_root_scroll_host=inject_scroll,
    responsive_reflow_enabled=responsive_reflow,
)
```

## LLM Context

Pass output is pre-emit layout truth; pair with `screen_ir` dumps under `.debug/<feature>/`. Provenance mutations for passes live in `provenance.json`. Layout responsive tier (`reflowed` / `scaled` / `preview`) is reported in `ai_ux.json` after layout emit.
