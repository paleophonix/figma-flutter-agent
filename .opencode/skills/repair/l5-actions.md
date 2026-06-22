Read `.repair/state/plan.json` and `.repair/state/diagnose.json` first, then open only plan `targetFiles` and named tests.

Tool budget (hard):
- At most one read pass on plan + diagnose state files.
- At most two source reads beyond state (target file + one helper if needed).
- Then apply the patch with `edit` tools. Do not explore the repo.

Do not run shell commands (`bash` is disabled). Orchestrator runs ruff and pytest after repair.

If plan is missing or no steps are assigned, set blocked=true and stop without edits.

Implement only assigned plan steps whose actionKind is CODE_CHANGE. Skip REPORT_ONLY, INFRA_RETRY, and HUMAN_REQUIRED steps; the orchestrator routes those outside repair.

For each assigned plan step, implement the smallest durable compiler-law fix that satisfies expectedChange and respects repairClass.

Add or update the tests named in the plan step before or alongside the fix when practical.

Emit repair.json with filesTouched, planStepOrders implemented, gates, diffStat, blocked, and notes mapping each change to a lawId.

Do not run full generate, project-wide analyze, capture, or golden update.
