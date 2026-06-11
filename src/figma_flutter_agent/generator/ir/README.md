# Screen IR emit

## Purpose

Compile `ScreenIr` + merged clean tree into Dart widget expressions with IR-primary walk, semantic Jinja templates, and fidelity tier routing.

## Usage Example

```python
from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.generator.ir.expression import emit_screen_body_from_ir
from figma_flutter_agent.generator.ir.tree import merge_screen_ir

merged = merge_screen_ir(clean_tree, screen_ir)
body = emit_screen_body_from_ir(screen_ir, merged, ctx=IrEmitContext(semantic_report_only=False))
```

## LLM Context

Do not emit Dart strings in this package; semantic widgets use `generator/templates/widgets/*.dart.j2`. Classifier-assigned `kind` and `fidelity_tier` must survive emit-time validation (`strip_llm_semantic_kinds=False`).
