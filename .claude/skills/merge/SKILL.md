---
name: merge
description: >-
  Merge OpenCode repair worktree into agent repo after wizard debug. Mandatory
  MERGE REVIEW before port: pack diff + plan, law/anti-patching check, user
  approval on PARTIAL. Then agent-mediated apply + plan tests. Use for /merge,
  "смержи repair", "перенеси из worktree".
disable-model-invocation: true
---

# Merge — repair worktree → agent repo

Pairs with wizard **debug** / `run_repair_pipeline`. **Not** screen `/diagnose` → `/repair`.
**Not** `git merge repair/<case_id>`.

## Loop

```text
pack → MERGE REVIEW (mandatory) → [user ok if PARTIAL] → port → verify → cleanup → MERGE REPORT
```

The agent is the merge layer: **review first**, then re-apply intent in main checkout.

## When to run

- `/merge`, "смержи", "перенеси repair", "что в worktree"
- After debug stopped or finished; user gave `case_id` or worktree path

## Step 0 — Pack (one command)

```powershell
.\scripts\repair-merge-pack.ps1
.\scripts\repair-merge-pack.ps1 -CaseId <case_id> -OutFile .temp\merge-pack.md
```

Read pack only. Do **not** ask the user to run git.

## Step 1 — MERGE REVIEW (mandatory, before any edit)

**Stop rule:** Do **not** port to main repo until this review is written in chat.
For **PARTIAL** or **NO_MERGE with implement-from-plan** → ask user "катим?" before coding.

Read pack **and** (when helpful) `plan.json`, `diagnose.json`, `repair.json` from
`.repair/worktrees/<case_id>/.repair/state/`.

### Review checklist (brief, all items)

| Check | Pass? |
|-------|-------|
| Each diff hunk maps to a `plan.steps[].lawId` + `targetFiles` | |
| No screen/`figmaId`/feature-specific branches | |
| No edits under `.repair/`, `sandbox/`, `apps/*/lib`, golden baselines | |
| Tests in diff match `plan.steps[].tests` (or new test is plan-declared) | |
| Fix is universal law-level, not one-screen patch | |
| `repair.scope.passed` true (if false → PARTIAL, list violations) | |

### Verdict

| Verdict | When |
|---------|------|
| **NO_MERGE** | Empty diff + empty `files_touched` |
| **IMPLEMENT_FROM_PLAN** | Empty diff but plan is sound (OpenCode no-op) |
| **PARTIAL** | Diff exists but check failed / scope risk / off-plan hunks |
| **READY** | Diff ⊆ plan targets, scope ok |

### Output template (always use)

```markdown
## MERGE REVIEW

**case_id:** …
**Verdict:** NO_MERGE | IMPLEMENT_FROM_PLAN | PARTIAL | READY

**Laws in plan:** …
**Worktree changed:** … (files or "none")
**Aligned with plan:** yes / partial / no — …
**Red flags:** … (or "none")

**Recommendation:** port as-is | port subset: … | implement plan manually | re-run debug

**Proceed?** (required for PARTIAL / IMPLEMENT_FROM_PLAN)
```

Keep review **5–15 lines** of prose plus the table; no code changes in this step.

## Step 2 — Port (only after review + approval)

Apply in **agent repo root**, not worktree:

- Re-apply diff hunks approved in review (StrReplace/Write)
- `IMPLEMENT_FROM_PLAN`: implement laws from plan, not fake "merge from worktree"
- No drive-by refactors; no `git apply` without review

Forbidden: commit unless user asks.

## Step 3 — Verify

```powershell
poetry run ruff check <plan src paths>
poetry run pytest <plan test files> -q
```

Fallback: `poetry run pytest tests/test_debug_pipeline_models.py -q`

On fail → **MERGE BLOCKED**; do not claim success.

## Step 4 — Cleanup (after successful port or NO_MERGE when worktree is done)

Remove the repair worktree, `repair/*` branches, and stale git worktree metadata so
the repo does not accumulate orphan slots.

```powershell
# Preview
.\scripts\cleanup-repair-branches.ps1 -DryRun

# Default (after merge review + verify)
.\scripts\cleanup-repair-branches.ps1

# When Cursor locks .git/worktrees (quit IDE first or retry)
.\scripts\cleanup-repair-branches.ps1 -RetryUntilRemoved -WaitForIdeExit
```

**When to run**

| Situation | Cleanup |
|-----------|---------|
| `READY` / `PARTIAL` port succeeded | **Yes** — always |
| `NO_MERGE` — worktree empty or changes already on `main` | **Yes** — drop stale `repair/<case_id>` |
| `IMPLEMENT_FROM_PLAN` — manual port, no worktree diff | **Yes** if case worktree still exists |
| Port failed / **MERGE BLOCKED** | **No** — keep worktree for retry |

**What it does** (`scripts/cleanup-repair-branches.ps1`):

- `git worktree remove` under `.worktrees/` and `.repair/worktrees/`
- delete local `repair/*` branches (not remote)
- prune orphan `.git/worktrees/*` metadata
- call `prune_stale_git_worktree_registry` in Python

Does **not** delete `.debug/` agent trace exports — only git worktree hygiene.

On deferred removals (IDE file lock), report paths and suggest `-RetryUntilRemoved`
or quitting Cursor (`File → Exit`).

## Step 5 — MERGE REPORT

```markdown
## MERGE REPORT

**Review verdict:** …
**Ported:** …
**Tests:** pass / fail
**Cleanup:** `cleanup-repair-branches.ps1` ok / dry-run / deferred (paths)
**Next:** …
```

Delete `.temp/merge-pack.md` if created.

## Quick reference

| Artifact | Path |
|----------|------|
| Worktree | `.worktrees/<case_id>/` (legacy: `.repair/worktrees/<case_id>/`) |
| State | `…/.repair/state/{plan,repair,check,diagnose}.json` |
| Agent trace export | `.debug/agent/<project>/<feature>/` |
| Cleanup script | `scripts/cleanup-repair-branches.ps1` |

## Examples

**Empty worktree, good plan:** MERGE REVIEW → IMPLEMENT_FROM_PLAN → user ok → code from plan → pytest.

**Good diff:** MERGE REVIEW → READY → port → pytest → MERGE REPORT.
