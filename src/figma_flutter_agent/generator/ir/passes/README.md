# IR layout passes

## Purpose

Runs dual-graph layout transforms (unstack, unpin, scroll host) through a single `PassManager` with CP2 conservation checks.

## Usage Example

```python
from figma_flutter_agent.generator.ir.passes import apply_ir_layout_passes

updated_ir, updated_clean = apply_ir_layout_passes(screen_ir, clean_tree)
```

## LLM Context

Pass output is pre-emit layout truth; pair with `screen_ir` dumps under `.figma_debug/ir/`. Provenance mutations for passes live in `.figma_debug/provenance/<feature>.json`.
