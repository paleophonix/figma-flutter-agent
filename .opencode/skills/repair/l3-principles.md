Edit only files listed in plan.steps[].targetFiles for the assigned planStepOrders.

Never edit generated Dart under Flutter app lib, .debug artifacts, golden baselines, or paths listed in plan.steps[].forbiddenFiles.

If plan.steps[] is missing, invalid, or empty, set blocked=true. Do not diagnose or build a new queue.

If the plan is unsafe, incomplete, or requires a forbidden shortcut, set blocked=true and explain in notes — do not improvise scope.

Keep changes surgical. Prefer existing helpers and repo patterns. Avoid unrelated cleanup and speculative abstractions.

Each edit must map to an assigned plan step order and lawId from the plan.

Add or update tests listed in plan.steps[].tests[] as regression proof for the law. Run scoped ruff and pytest; record results in repair.gates. Do not run the full test suite or signoff gates.

Implement all plan steps assigned to this repair pass in one bounded execution. Do not hunt for additional root causes beyond the plan.

Do not stop early because one test passed while other assigned plan steps remain unimplemented — finish the assigned pass, then report in repair.json.

Do not run full figma-flutter generate, dart analyze on app lib, golden capture, visual comparison, or baseline refresh. Check and capture are orchestrator-owned deterministic gates. Post-check fix is a separate OpenCode build phase on candidate planned_files only.

Repo navigation map deepModules slice in L6 is for assigned target files only; navigation not substitute for reading code.

Do not mutate the cumulative reasoning_chain; write executive JSON to output_path.
