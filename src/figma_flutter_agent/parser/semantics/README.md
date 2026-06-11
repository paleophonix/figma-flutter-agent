# parser/semantics

## Purpose

Deterministic staged classifier that assigns `WidgetIrKind` and typed payloads on screen IR nodes using clean-tree structural signals (no layer-name matching).

## Usage Example

```python
from figma_flutter_agent.parser.semantics import classify_screen_ir

updated_ir, report = classify_screen_ir(screen_ir, clean_tree)
```

## LLM Context

Do not assign authoritative semantic kinds in generate prompts. Emit optional `classificationHint` only; this module consumes hints in the grey zone (0.5–0.8) after layout passes in `materialize.py`.
