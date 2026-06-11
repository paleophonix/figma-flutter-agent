# parser/semantics

## Purpose

Deterministic staged classifier that assigns `WidgetIrKind` and typed payloads on screen IR nodes using clean-tree structural signals (no layer-name matching).

## Usage Example

```python
from figma_flutter_agent.parser.semantics import classify_screen_ir
from figma_flutter_agent.parser.semantics.metrics import evaluate_w1_corpus

updated_ir, report = classify_screen_ir(screen_ir, clean_tree)
gate = evaluate_w1_corpus()
```

CLI: `poetry run figma-flutter semantics corpus-gate --write-report logs/semantics/w1_classification_gate.json`

## LLM Context

Do not assign authoritative semantic kinds in generate prompts. Emit optional `classificationHint` only; this module consumes hints in the grey zone (0.5–0.8) after layout passes in `materialize.py`.
