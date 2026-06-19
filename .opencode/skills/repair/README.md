# Repair step skill (OpenCode repair pipeline)

## Purpose

Step 5/7: execute plan.steps[] in sandbox worktree. Only build-mode step. Ruff/pytest on touched scope only.

## Usage example

```python
from pathlib import Path

skill_dir = Path(".opencode/skills/repair")
# Orchestrator sets mode=build and plan_step_orders before assembly
```

## LLM context

After repair, orchestrator runs check, optional fix, capture, and review — not the repair agent.
