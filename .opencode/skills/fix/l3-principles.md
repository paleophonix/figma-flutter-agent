Fix unblocks check. Fix does not close a law. Fix cannot prove product correctness.

planned_files fix may unblock check; it must never become the product fix.

Treat diagnose.laws and plan.steps as frozen context in frozenContext. Do not add, remove, rename, or reinterpret laws.

Use board master purpose from L1; this phase only unblocks materialized Dart while compiler law remains frozen.

Edit only files listed in allowedEditFiles under .repair/candidate/planned_files/. Do not edit src/figma_flutter_agent, project lib, apps lib, sandbox lib, canonical .debug artifacts, .repair/debug mirrors, golden baselines, or fixtures.

Do not edit .repair/debug screen.dart or other mirrors directly. Orchestrator regenerates mirrors from candidate after fix.

Only address concrete analyzer, parser, import, syntax, type, const, or identifier errors from check_summary and analyze_errors.

Do not perform visual refinement, pixel polish, layout redesign, root-cause diagnosis, or mini inspect/diagnose passes.

Do not broaden scope on repeated failure. If the same error root persists, set exhausted=true or blocked=true rather than improvising wider patches.

One OpenCode invocation equals one fix attempt. Do not run check, capture, visual comparison, or review. The orchestrator runs check next.

errorsAfter is determined by the next check.json, not by fix. You may set expectedErrorsAfter or notes only.

If the error cannot be fixed within allowedEditFiles, set blocked=true and set routeAfter to diagnose.refine or repair.retry only when the orchestrator route options explicitly allow it.

On FORENSIC board, fix runs only for candidate materialization when candidate_available and allowedEditFiles are set. Do not treat fix as screen visual success or capture-based closure.

Do not receive repo navigation map. Fix scope is allowedEditFiles only to prevent wandering into compiler src.

Do not emit lawClosed, task_completed, or product success fields.

Do not mutate the cumulative reasoning_chain; write only executive JSON to output_path.
