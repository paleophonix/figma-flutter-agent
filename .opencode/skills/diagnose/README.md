# Diagnose step skill (OpenCode repair pipeline)

## Purpose

Step 3/7: WHY inside inspect entities — named laws, layers, evidence, repairShape. Read-only; plan mode.

Input boundary: inspect.entities (artifactRefs, repoPaths, confidence). Does not re-map WHERE or repeat symptoms.

## Usage example

```python
from pathlib import Path

skill_dir = Path(".opencode/skills/diagnose")
meta = skill_dir / "meta.yaml"  # orchestrator only
l2 = (skill_dir / "l2-role.md").read_text(encoding="utf-8").strip()
# Assembler: L1 master + L2 + L3(invariants + l3-principles) + L4 + L5 + L6 template
```

## LLM context

Load bodies from l2-role.md through l6-environment.tpl; wrap with `_acdp_layer` in strict L1→L6 order. Inject run_context and reasoning_chain via l6-environment.tpl placeholders only.
