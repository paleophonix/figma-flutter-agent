# OpenCode step skills

## Purpose

Per-step L2–L6 bodies for the 7-step repair pipeline. Assembled with prompts/repair-master-*.md (L1) and repair-invariants.md (shared L3).

## Layout

```text
skills/<step>/
  meta.yaml           # orchestrator: index, mode, paths — not sent to LLM
  l2-role.md
  l3-principles.md  # step-specific; merged with repair-invariants inside L3
  l4-capabilities.md
  l5-actions.md
  l6-environment.tpl
  README.md
```

## Implemented steps

| Step | Directory | Mode | Board |
|------|-------------|------|-------|
| 1 recognise | recognise-screen/ | plan | screen |
| 1 recognise | recognise-forensic/ | plan | forensic |
| 2 inspect | inspect-screen/ | plan | screen |
| 2 inspect | inspect-forensic/ | plan | forensic |
| 3 diagnose | diagnose/ | plan | shared |
| 4 plan | plan/ | plan | shared |
| 5 repair | repair/ | build | shared |
| — fix | fix/ | build | post-check (PATCH_CODE_EMIT) |
| 6 review | review/ | plan | shared — evidence judge, not pixel-police |
| 7 summarize | summarize/ | plan | shared — archivist handoff, not re-judge |

Prompt stack: 7 agent steps + fix post-check phase. Plan `actionKind` routes CODE_CHANGE to repair only. Code follow-ups: `dev/opencode/prompt.py`, `dev/opencode/repo_map.py`, schemas, vision bundle, inspect preflight, fix orchestrator loop, prompt lint gates (see prompts/README.md).

Inspect L6: `inspect_preflight` + `repo_map_compact_json` + `symptom_surface_hints_json`. Map source: `.opencode/context/repo-map.yaml` (navigation only, not evidence).

## LLM context

Load meta.yaml in Python only. Pass assembled L1→L6 prompt to OpenCode; inject plan_step_orders on repair step only.
