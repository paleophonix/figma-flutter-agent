# Fix phase skill (post-check)

## Purpose

OpenCode build pass after PATCH_CODE_EMIT check failure. Edits `.repair/candidate/planned_files/` only. Same session contract as repair; not a separate board master L1.

## Usage example

Orchestrator: one OpenCode invocation per attempt; `git diff` → `fix.diff`; then re-check. Config: `debug_pipeline.emit_fix_engine: opencode`.

## LLM context

Not CP `/debug → /fix`. Not `run_analyze_repair_loop` inside debug pipeline (legacy generate only). See `docs/projects/26-06-18-repair-opencode/opencode-debug-state.md` §8.8.
