Read run_context, plan.steps[], and the orchestrator-assigned planStepOrders for this pass.

If plan is missing or no steps are assigned, set blocked=true and stop without edits.

Inspect targetFiles and related tests only as needed to implement each assigned step.

For each assigned plan step, implement the smallest durable compiler-law fix that satisfies expectedChange and respects repairClass.

Add or update the tests named in the plan step before or alongside the fix when practical.

Run ruff and pytest on the touched scope when available. Record results in repair.gates.

Emit repair.json with filesTouched, planStepOrders implemented, gates, diffStat, blocked, and notes mapping each change to a lawId.

Do not run full generate, project-wide analyze, capture, or golden update.
