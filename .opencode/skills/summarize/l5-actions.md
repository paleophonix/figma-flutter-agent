1. Read `review.json`, `task_completed_gate_snapshot`, `run_context`, and cumulative `reasoning_chain`.
2. If `review.decision=LOOP`, emit `blocked=true` with `blocked_reason=SUMMARIZE_NOT_ALLOWED_FOR_LOOP` and stop.
3. Mirror `review.decision`, `reason_code`, `lawCompliance`, `symptomClosure`, `regression_risks`, and blockers.
4. Produce dev summary in English for every valid summarize call.
5. If `task_completed=true` (from gate snapshot), produce product ticket summary in Russian.
6. If `task_completed=false`, set `ticket.publish=false` and include data_context routing with `resume_hint`.
7. Do not inspect images, grep repo, re-run checks, or reinterpret capture.
8. Emit `summarize.json` and requested report paths (`ticket_summary.md` when publishing; `dev_summary.md` always).
