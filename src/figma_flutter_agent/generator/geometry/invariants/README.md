# Geometry invariants

## Purpose

Validate translation-theory geometry on the clean tree before and after layout emit. Catches flex conservation drift, bounded slot overflow, and artboard extent issues before Flutter runtime.

## Usage

```python
from figma_flutter_agent.generator.geometry.invariants.validate import validate_geometry_invariants
from figma_flutter_agent.generator.geometry.planner import plan_geometry_tree

planned = plan_geometry_tree(clean_tree)
violations = validate_geometry_invariants(planned, require_layout_slots=True, layout_source=dart_source)
```

## Checks (selected)

| Code | Severity | Meaning |
|------|----------|---------|
| `t2_flex_conservation` | soft | Rigid flex children exceed parent main-axis span |
| `t2_bounded_slot_conservation` | soft | Predicted vertical flow exceeds bounded `Positioned` slot |
| `t2_artboard_extent_drift` | soft | Grown intrinsic content exceeds artboard height |

## Remediation ladder (overflow)

1. Prefer `minHeight` over fixed `SizedBox(height)` for intrinsic hosts.
2. Apply `column_bounded_slot_should_grow` for bounded cards with flow buttons.
3. Add typography slack from `predict_typography_slack` when summing text slots.
4. **`OverflowBox` max extent = full positioned slot** when host `Padding` is already inside the wrapped widget (never subtract padding twice).
5. **`flex_host_prefers_min_height_pin`** when a fixed-height frame hosts intrinsic flow stacks/buttons (`grow_then_gate`) — emit `ConstrainedBox(minHeight: …)`, never `SizedBox(height: …)` on the artboard shell.
6. Runtime: `runtime_fail_renderflex_overflow` in signoff gates.

## LLM context

Inject violation summaries into repair prompts when `strict_geometry_invariants` is enabled. Never patch a single screen — fix the invariant or emit policy that failed.
