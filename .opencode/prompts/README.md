# OpenCode repair prompts

## Purpose

Raw ACDP layer bodies for the 7-step OpenCode repair pipeline. Tags and ordering are applied by `dev/opencode/prompt.py` via `_acdp_layer` / `_compose_acdp_prompt` (see `docs/projects/26-06-18-repair-opencode/opencode-debug-state.md` §8.2).

## Layout

```text
.opencode/prompts/
  repair-master-screen.md    # L1 body — SCREEN board
  repair-master-forensic.md  # L1 body — FORENSIC board
  repair-invariants.md       # shared L3 body (merged into every step L3)
  README.md

.opencode/skills/<step>/     # L2–L6 bodies per step
  meta.yaml                  # orchestrator index — not sent to LLM
  l2-role.md … l6-environment.tpl
```

**Source file rule:** plain prose in bodies — no `<Lx:...>` tags, no markdown headings inside bodies sent to the model.

## Assembly (strict L1→L6)

```text
L1 = master[board]
L2 = skill.l2
L3 = repair-invariants + "\n\n" + skill.l3    # shared inside L3, not between L1 and L2
L4 = skill.l4
L5 = skill.l5
L6 = render(skill.l6-environment.tpl, runtime)
```

Use `_compose_acdp_prompt(l1=…, l2=…, l3_core=invariants, l3_principles_ext=skill.l3, l4=…, l5=…, l6=…)`.

Runtime placeholders (reasoning_chain, run_context, paths) are substituted into L6 only.

**Fix phase:** uses same board master L1 as repair (no separate fix-master). Skill: `.opencode/skills/fix/`. Canonical edit root: `.repair/candidate/planned_files/` only.

**Repo navigation map:** curated `.opencode/context/repo-map.yaml`; orchestrator slices into L6 (`repo_map_compact_json`, `symptom_surface_hints_json`, `repo_map_deep_json`). Not evidence. Fix step excludes map.

## Orchestrator enforcement (not optional)

Prompt restrictions are not security boundaries. The orchestrator must enforce OpenCode mode (plan vs build), allowed edit roots, JSON schema validation, scope diff, and step routing.

Especially for repair (sandbox `src/` + `tests/` only) and fix (`.repair/candidate/planned_files/**` only). `.opencode/opencode.json` permissions are a secondary guard; gates in Python are authoritative.

## Planned prompt lint gates (M1+)

1. **Body lint:** skill bodies contain no `<L`, `</L`, markdown headings, or runtime placeholders outside `l6-environment.tpl`.
2. **Step boundary lint:** recognise schema forbids `repoPaths`/`lawId`; inspect forbids `lawId`/`repairShape`/`targetFiles`; diagnose forbids `targetFiles`; plan forbids edits; summarize forbids new laws.
3. **Scope lint:** `repair.filesTouched` ⊆ plan `targetFiles` for CODE_CHANGE steps; `fix.filesTouched` ⊆ `allowedEditFiles` under planned_files.
4. **Board lint:** forensic output forbids screen visual regions (`primary_cta`, `header`, `form`); screen recognise requires verified capture.
5. **Review coercion:** CONTINUE impossible without gates, change_proof, and closed lawCompliance with evidence.
6. **Plan routing lint:** only `actionKind=CODE_CHANGE` steps receive `planStepOrders` for repair.

## Usage example

```python
from pathlib import Path
from figma_flutter_agent.llm.prompts.compose import _compose_acdp_prompt

repo = Path(__file__).resolve().parents[2]
prompts = repo / ".opencode/prompts"
skill = repo / ".opencode/skills/diagnose"

prompt = _compose_acdp_prompt(
    l1=(prompts / "repair-master-screen.md").read_text(encoding="utf-8").strip(),
    l2=(skill / "l2-role.md").read_text(encoding="utf-8").strip(),
    l3_core=(prompts / "repair-invariants.md").read_text(encoding="utf-8").strip(),
    l3_principles_ext=(skill / "l3-principles.md").read_text(encoding="utf-8").strip(),
    l4=(skill / "l4-capabilities.md").read_text(encoding="utf-8").strip(),
    l5=(skill / "l5-actions.md").read_text(encoding="utf-8").strip(),
    l6=render_l6(skill / "l6-environment.tpl", runtime),
)
```

## LLM context

Pass fully assembled tagged blocks to the model. Step `meta.yaml` is for the orchestrator only.
