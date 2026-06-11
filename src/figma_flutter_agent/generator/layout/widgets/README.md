# Layout widget emit

## Purpose

Geometric fallback Dart emission from clean-tree nodes (`render_node_body`) and layout shells with pre-built child expressions (`emit/shell.py`).

## Usage Example

```python
from figma_flutter_agent.generator.layout.widgets.emit import render_leaf_body, render_layout_shell
```

## LLM Context

Dart widget string literals in this tree are legacy debt tracked by `scripts/lint_dart_in_python.py` (`layout_widgets_count` burn-down). New semantic emit belongs in Jinja templates under `generator/templates/widgets/`.
