# Defect corpus — family registry (Program 00)

## Purpose

Machine-checkable defect families for compiler pipeline failures. Each family names a **mechanism**, not a symptom.

**Workflow (agent-owned):**

```text
/diagnose → OPEN
/repair   → OPEN until proven → FIXED (or WONT_FIX / DEFERRED_BY_POLICY)
```

Binary rule: **not fixed = OPEN**, **proven fixed = FIXED**. `/repair` alone changes nothing.

**Agent lookup (before opening full case YAML):**

```text
corpus/families.yaml              → family_id
corpus/index/<family_id>.yaml     → case_id, project, feature, status, summary
corpus/cases/<case_id>.yaml       → full occurrence + evidence + repair
```

Indexes are **auto-generated** — never edit by hand:

```bash
poetry run figma-flutter defects index --write
poetry run figma-flutter defects index --check   # also runs on defects validate
```

## Usage Example

```python
from figma_flutter_agent.defects import load_families

doc = load_families()
for family in doc.families:
    print(family.id, family.law_ids)
```

## LLM Context

Diagnose/repair skills map root causes to `family_id` from this file. Cases reference families and must pass `figma-flutter defects validate`.

- **`/diagnose`:** write or update cases with `status: OPEN` when mechanism is classified.
- **`/repair`:** stay `OPEN` while trying; `FIXED` only with proof + `repair` block. Failed attempts: still `OPEN`, note in `summary`. Close without fix: `WONT_FIX` or `DEFERRED_BY_POLICY`.

Product owner supplies chat observations; agents maintain YAML and run `defects validate`.

**Location:** repo-root `corpus/`. Pipeline contract for agents: `.cursor/rules/pipeline-contracts.mdc`.
