# Geometry and emit fidelity audit

## Invariant catalog (T2 / hard)

| Code | Severity | Emit linkage |
| --- | --- | --- |
| `t2_flex_conservation` | soft | `resolve_flex_wrap`, rigid children |
| `t2_bounded_slot_conservation` | soft | `column_bounded_slot_should_grow`, OverflowBox |
| `t2_artboard_extent_drift` | soft | `grow_then_gate`, minHeight vs SizedBox |
| `inv_flex_axis` | hard | Expanded on wrong axis |
| `inv_z` | hard | ghost occlusion |

Tests: `test_extent_conservation`, `test_bounded_slot_conservation`, `test_artboard_frame_growth`, `test_renderflex_overflow_gate`.

## Emit remediation ladder

1. Prefer `minHeight` over fixed `SizedBox(height)` for intrinsic buttons.
2. `OverflowBox` maxHeight uses full slot — padding not subtracted twice (`widgets/text.py`).
3. `flex_host_prefers_min_height_pin` on artboard shell.
4. `predict_typography_slack` included in T2b sums.

## Typography / input contract

- `decoration.py`: `omit_line_height` + line-box `contentPadding` when `vertical_center`.
- `geometry/flex.compute_input_metrics`: prefers value node over hint for metrics.

## FID-26 (`emit_fidelity_audit`)

Corpus diff-triada records `emit_fidelity_violations` per layout. Common codes:

- `layer_blur_missing_backdrop`
- `line_height_missing_strut`
- `bottom_pin_used_top`
- `opacity_missing_wrapper`

See `diff-triada-summary.md` for per-fixture results.
