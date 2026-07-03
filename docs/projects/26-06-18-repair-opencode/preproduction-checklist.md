# Repair pipeline pre-production checklist

Use before enabling autonomous outer-loop repair in production or control panel.

## Stop conditions and budgets

- [ ] All eight `debug_pipeline.loops` budgets are enforced in `route_dispatch.apply_budget`.
- [ ] `same_root_hash_repeat_without_improvement` escalates to `STOP_HUMAN`.
- [ ] `review.LOOP` dispatches to refine routes; does not stop with `review_loop`.
- [ ] Outer loop capped by `_MAX_OUTER_ROUNDS` and per-route budgets.

## Enforcement

- [ ] Post-hoc `scope_enforcement` blocks repair outside plan `targetFiles`.
- [ ] Fix step limited to `.repair/candidate/planned_files/`.
- [ ] `run_repair_gates` uses plan-derived paths and blocks pipeline on failure.
- [ ] Untrusted-artifact invariant present in `repair-invariants.md`.

## Observability

- [ ] Trace records `tokens_in` / `tokens_out` per read step.
- [ ] `trace.finish` writes rollup with outlier step and token totals.
- [ ] Checkpoints append to `state/checkpoints.jsonl` after each step.

## Eval and stress

- [ ] `tests/evals/repair_pipeline/` routing fixtures pass offline.
- [ ] `tests/test_repair_outer_loop.py` covers LOOP dispatch and gate failure.
- [ ] `tests/test_repair_scope_enforcement.py` covers scope drift.

## Cost per successful case

- [ ] PostHog `$ai_trace_id` matches repair `run_id`.
- [ ] Completed runs expose `rollup.cost_per_completed_case` in trace outcome.

## Explicit non-goals

- Embedding-based loop detection
- Multi-agent fan-out
- RL / fine-tune on traces
