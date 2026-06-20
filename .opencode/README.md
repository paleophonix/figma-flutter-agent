# OpenCode workspace (figma-flutter-agent)

## Purpose

Local OpenCode config and repair prompt stack for wizard debug and (future) shared control-plane pipeline.

## Layout

```text
.opencode/
  opencode.json              # provider, permissions
  context/law-label-map-ru.yaml  # lawId → RU for summarize ticket
  context/repo-map.yaml      # curated module atlas for L6 slices
  prompts/                   # master L1 + shared L3 (see prompts/README.md)
  skills/recognise-screen/   # step 1 SCREEN vision symptoms
  skills/recognise-forensic/ # step 1 FORENSIC pipeline trust
  skills/inspect-screen/     # step 2 SCREEN symptom → artifact → repo map
  skills/inspect-forensic/   # step 2 FORENSIC pipeline cartography
  skills/diagnose/           # step 3 law queue
  skills/plan/               # step 4 scope lock
  skills/repair/             # step 5 build mode
  skills/fix/                # post-check candidate planned_files patch
  skills/review/             # step 6 CONTINUE|LOOP|STOP
  skills/summarize/          # step 7 archivist: RU ticket + EN dev + routing
  README.md
```

Legacy `agents/` (diagnose-*, repair-consilium, repair-planner, …) removed 2026-06-19 in favor of orchestrated 7-step pipeline + step skills.

## Usage example

```bash
export OPENROUTER_API_KEY=...
poetry run figma-flutter -i   # 8. debug → spawns opencode serve when configured
```

Config: `.ai-figma-flutter.yml` → `debug_pipeline.effort`, `debug_pipeline.models.single`, `opencode_base_url`, `opencode_server_password`. Wizard spawns `opencode serve` with `OPENCODE_CONFIG_CONTENT` overlay from `debug_pipeline`.

## LLM context

When assembling a repair step prompt, load L1 body from `prompts/repair-master-{screen|forensic}.md`; the assembler wraps it in `<L1:PURPOSE>`. Step skills supply L2–L6 bodies the same way. Repo map slices come from `context/repo-map.yaml` via planned `dev/opencode/repo_map.py`.

Prompt restrictions are contracts only. The orchestrator enforces mode, allowed edit roots, schema validation, and scope diff — especially repair vs fix. See `prompts/README.md` § Orchestrator enforcement.

**Note:** Headless control-plane repair (`repair.enabled`) still references removed agent names until M6 refactor; keep `repair.enabled: false` until then.
