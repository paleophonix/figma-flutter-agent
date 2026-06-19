# OpenCode workspace (figma-flutter-agent)

## Purpose

Local OpenCode config and repair prompt stack for wizard debug and (future) shared control-plane pipeline.

## Layout

```text
.opencode/
  opencode.json              # provider, permissions
  prompts/                   # master L1 + shared L3 (see prompts/README.md)
  skills/                    # step skills L2–L6 (to be added per M1)
  README.md
```

Legacy `agents/` (diagnose-*, repair-consilium, repair-planner, …) removed 2026-06-19 in favor of orchestrated 7-step pipeline + step skills.

## Usage example

```bash
export OPENROUTER_API_KEY=...
poetry run figma-flutter -i   # 8. debug → spawns opencode serve when configured
```

Config: `.ai-figma-flutter.yml` → `opencode_base_url`, `opencode_server_password`.

## LLM context

When assembling a repair step prompt, load L1 body from `prompts/repair-master-{screen|forensic}.md`; the assembler wraps it in `<L1:PURPOSE>`. Step skills supply L2–L6 bodies the same way.

**Note:** Headless control-plane repair (`repair.enabled`) still references removed agent names until M6 refactor; keep `repair.enabled: false` until then.
