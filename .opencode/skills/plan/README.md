# Plan step skill (OpenCode repair pipeline)

## Purpose

Step 4/7: convert diagnose.laws[] into bounded plan.steps[] with scope lock. Read-only; plan mode.

## Usage example

```python
from pathlib import Path

skill_dir = Path(".opencode/skills/plan")
# Assembler: L1 master + L2 + L3(invariants + l3-principles) + L4 + L5 + L6 template
```

## LLM context

Repair step must implement only plan.steps[]; plan must not edit code or re-diagnose.

Every actionable plan step must declare actionKind and name tests[] for CODE_CHANGE steps — orchestrator blocks plan without them. Only CODE_CHANGE routes to repair.
