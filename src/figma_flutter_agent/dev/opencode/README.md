# dev/opencode

## Purpose

Local OpenCode repair pipeline: Run Gate (M0), workspace orchestration, OpenRouter read steps, OpenCode build repair, deterministic check/fix/capture gates, and summarize routing (M0–M6).

## Usage Example

```python
import asyncio
from pathlib import Path

from figma_flutter_agent.config import load_settings
from figma_flutter_agent.dev.opencode import (
    evaluate_run_gate,
    run_repair_pipeline,
    ensure_opencode_serve,
    OpenCodeClient,
)

async def main() -> None:
    settings = load_settings()
    project_dir = Path("../demo_app")
    feature = "login_version_1"
    gate = evaluate_run_gate(project_dir, feature)
    await ensure_opencode_serve(
        base_url=settings.opencode_base_url,
        password=settings.opencode_server_password.get_secret_value(),
    )
    client = OpenCodeClient(base_url=settings.opencode_base_url)
    outcome = await run_repair_pipeline(
        settings=settings,
        project_dir=project_dir,
        feature=feature,
        opencode_client=client,
    )
    print(gate.verdict, outcome.stop_reason)

asyncio.run(main())
```

Wizard entry: `poetry run figma-flutter -i` → **debug**.

Install OpenCode CLI once: `npm install -g opencode-ai` (or run `scripts/bootstrap.ps1`). Wizard auto-starts `opencode serve` when the CLI is on PATH, restarts stale listeners when `restart_opencode_serve_with_overlay: true`, and runs a short OpenCode→OpenRouter preflight before repair.

## LLM Context

`RepairTraceRecorder.record_step` emits PostHog ``$ai_generation`` for every OpenRouter read step (recognise → summarize) when ``trace.posthog`` is enabled. OpenCode write steps use ``record_opencode``. The OpenRouter client skips duplicate repair spans when the recorder owns PostHog.

Edit scope is enforced post-hoc via `scope_enforcement.py`: repair uses `git diff` plus `git status --porcelain` (untracked included); fix uses before/after SHA snapshots of `.repair/candidate/planned_files/` because that tree is gitignored. OpenCode `permission.edit` remains best-effort; Python gates are authoritative.

`check.py` fails loud when `dart-errors.json` is missing (`UNKNOWN_BLOCKED` or `TOOLCHAIN_FLAKE` from `last.log` markers). Compiler-path errors in the plan route to `repair.retry`; emit errors route to `fix`. After hard review overrides, `persist_review_state` rewrites `review.json` and the reasoning chain.

Resume checkpoints map `recognise → inspect → diagnose → plan` (no skipped read steps). SCREEN runs require a vision bundle (`figma.png` minimum) under `.repair/vision/` via `vision_bundle.py`.

`plan_validate.py` rejects plan `targetFiles` that do not exist on disk or use Flutter-style paths under `src/figma_flutter_agent/`. `repo_map.py` + `l6_context.py` + `l6_bindings.py` inject navigation, gate snapshots, and law-label maps into L6 prompts.

`worktree_runtime.py` runs ``poetry -P <worktree>`` with ``isolated_poetry_env()``:
parent ``VIRTUAL_ENV`` is cleared but ``POETRY_PYTHON`` / ``PYTHON`` are pinned to
``sys.executable`` so Windows PATH stubs do not break ``poetry install`` in repair gates.

After compiler repair, `regenerate_mirror.py` replays `generate` from cached `raw.json` / screen IR (no LLM) using the repaired worktree code, refreshes `.repair/debug/`, then `check` reads the fresh mirror. Set `debug_pipeline.regenerate_after_compiler_repair: false` to fall back to gate-only bypass.

`repair_salvage.py` implements ``RepairWorktreeSalvageLaw``: when repair noop or ``plan.blocked`` but the worktree still has compiler diffs from a prior OpenCode session, scoped ruff/pytest gates run on those paths and the pipeline continues to regenerate/check without re-planning.

`worktree_runtime.isolated_poetry_env_for_worktree` injects the orchestrator checkout `tools/bin/ast_compiler*` binary into worktree subprocesses (worktrees omit gitignored prebuilts). Regenerate emits wizard heartbeats every 30s and fails with `REGENERATE_TIMEOUT` after `debug_pipeline.loops.regenerate_timeout_sec` (default 900).

`debug_pipeline.fix_enabled` defaults to `false`: emit-layer fix loops are guarded until planned-files fix path is wired. When disabled, `PATCH_CODE_EMIT` routes stop with `fix_disabled`.

`repair_gates_failed` is an intentional hard stop after OpenCode repair when ruff/pytest gates fail (no automatic repair retry).

Schema strictness (`schema_gate` + OpenRouter `strict_json_schema`) is deferred until build-identity and proof-integrity epics are stable in production.

`worktree_retention.py` keeps `debug_pipeline.worktrees.retain_latest` repair sandboxes (default `1`) under `<repo>/.worktrees/<MMDD-HHMM-project-screen>/` and runs `git worktree prune` after each pipeline exit. Legacy sandboxes under `.repair/worktrees/` are still listed for retention and merge. Inside each sandbox, case artifacts remain under `.repair/state`, `.repair/debug`, etc. Pytest repair suites tear down worktrees they create.
