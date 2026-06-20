# Repair pipeline eval fixtures

Offline cases for agent-harness regression. Each case supplies a debug mirror
bundle and expected routing metadata.

## Cases

| Case | Expected failure / route |
|------|--------------------------|
| `stale_capture_rollback` | `STALE_CAPTURE` / forensic |
| `patch_code_emit` | `PATCH_CODE_EMIT` / fix |
| `capture_visual_mismatch` | capture fail / `diagnose.refine` |
| `scope_drift` | `SCOPE_DRIFT` stop |
| `review_loop_refine` | `review.LOOP` / `diagnose.refine` |

Run: `pytest tests/evals/repair_pipeline -q`
