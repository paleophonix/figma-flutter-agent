# Programs 04–06 — Architecture RFC (non-normative)

**Status:** RFC — execution authority lives in [04-05-06-refactoring-spec-cursor.md](04-05-06-refactoring-spec-cursor.md) v2.1.

This document is the demoted successor to **GitHub PR #6** (draft, superseded — do not merge; canonical docs live here on `main` since `d524fce6`).

## Programs

| Program | Doc | Role |
|---------|-----|------|
| **04** | [04_extraction-dedup-bijection.md](04_extraction-dedup-bijection.md) | Cluster identity, bijection, cycle-safe walks, asset index |
| **05** | [05_visual-ownership-layout-inference.md](05_visual-ownership-layout-inference.md) | Ownership graph, layout hypothesis, reconcile conflicts |
| **06** | [06_geometry-constraint-algebra.md](06_geometry-constraint-algebra.md) | Constraint algebra, resolver, geometry laws |

## Contracts (normative vocabulary)

- [contracts/geometry_algebra.md](contracts/geometry_algebra.md) — Track 06
- [contracts/cluster_signature.md](contracts/cluster_signature.md) — Track 04
- [contracts/layout_hypothesis.md](contracts/layout_hypothesis.md) — Track 05

## Cross-links

- Milestone 2 TZ: [02-03-refactoring-spec-cursor.md](02-03-refactoring-spec-cursor.md)
- Pipeline arrows: [contracts/PIPELINE_ARROWS.md](contracts/PIPELINE_ARROWS.md)
- M2 acceptance: [generated/m2-acceptance-report.md](generated/m2-acceptance-report.md)
- M3 closure gate: [generated/m2-closure-record.md](generated/m2-closure-record.md)

## Principle (Option B)

`parallel implementation ≠ parallel authority switch`. Shadow and additive models may merge before M2 closure; production authority switches require M2 closure record + green CI.

## Enforce decision records

**M3 signoff ≠ global enforce approval.** Each law family / route needs a separate record under `generated/`:

| Field | Description |
|-------|-------------|
| `law_id` | Stable compiler law (e.g. `LAW-GEOM-CONSTRAINT-SEMANTICS`, `LAW-CLUSTER-BIJECTION`) |
| `family_id` | Defect / corpus family that motivated the law (e.g. `wrong_pin_center`, `delegate_cycle`) |
| `routes` | Code paths switched (e.g. `slots.py`, `widget_extractor.py`) |
| `evidence` | Tests, shadow report, corpus case IDs |
| `fallback` | How to revert to legacy (flag, commit) |
| `rollback` | Owner action if production regression |
| `owner` | Engineer / reviewer |
| `approval` | Date + M2/M3 gate passed |

Rollout per family:

```text
off → report_only → shadow → enforce
```

Never combine additive model + authority switch in one PR.
