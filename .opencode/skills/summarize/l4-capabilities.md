You can read the full cumulative `reasoning_chain`, `review_summary_json`, and `task_completed_gate_snapshot` — no repo grep, no vision, no re-checks.

You can write `ticket_summary.md` (RU, product) only when gate snapshot has `task_completed=true`.

You always write `dev_summary.md` (EN, engineering) on valid summarize calls (CONTINUE or STOP).

You output `summarize.json` with `ticket`, `dev`, `routing`, `agent_task_completed_recommendation`, and orchestrator-mirrored completion flags.

You use `law_label_map_ru_json` for ticket prose; unknown laws get short plain RU from review/diagnose, not raw slugs.

You emit `blocked=true` when `review.decision=LOOP`; orchestrator should not invoke summarize in that case.

You understand `data_context.json` is orchestrator-written after summarize when ¬completed; your `dev` block must be complete enough to populate it.

You distinguish `forensic_completed` vs `screen_completed` on FORENSIC board — no screen success ticket when only forensic work closed.
