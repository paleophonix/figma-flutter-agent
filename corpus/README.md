# Defect corpus — family registry (Program 00)

## Purpose

Machine-checkable defect families for compiler pipeline failures. Each family names a **mechanism**, not a symptom.

## Usage Example

```python
from figma_flutter_agent.defects import load_families

doc = load_families()
for family in doc.families:
    print(family.id, family.law_ids)
```

## LLM Context

Diagnose/repair skills map root causes to `family_id` from this file. Cases reference families and must pass `figma-flutter defects validate`.

**Location:** repo-root `corpus/`. Pipeline contract for agents: `.cursor/rules/pipeline-contracts.mdc`.
