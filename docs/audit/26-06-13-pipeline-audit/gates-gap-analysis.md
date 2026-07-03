# Gates gap analysis

| Gate | Source | Covers | Does not catch |
| --- | --- | --- | --- |
| ruff / mypy / pytest | `scripts/signoff.ps1` | style, unit contracts | predicate overlap |
| demo-signoff | `cli/live.py` | 5 Figma samples | structural misclassification |
| fixture-ir-validate | CLI | IR guards on fixtures | deterministic emit-only paths |
| fixture-geometry-check | `fixtures/geometry_check.py` | placements IoU | vertical text offset in inputs |
| spec23 | `validation/spec23/evaluate.py` | production readiness | archetype flatten regressions |
| `runtime_fail_renderflex_overflow` | production profile | golden RenderFlex logs | checkbox→TextField |

## Production vs dev profile

`config/profiles.py`: `strict_geometry_invariants`, `strict_contrast`, `analyze_scope: all_planned`.

**Recommendation:** run `figma-flutter generate` with production profile on customer dumps and compare soft invariant counts with dev baseline.
