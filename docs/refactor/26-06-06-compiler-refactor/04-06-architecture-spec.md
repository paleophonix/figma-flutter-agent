# Programs 04–06 — Architecture RFC (non-normative)

**Status:** RFC — execution authority lives in [04-05-06-refactoring-spec-cursor.md](04-05-06-refactoring-spec-cursor.md) v2.1.

This document is the demoted successor to PR #6. It records **why** the three programs exist and how they connect; it does **not** override the execution TZ or contract files.

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

`parallel implementation ≠ parallel authority switch`. Shadow and additive models may merge before M2 closure; production authority switches (DefinitionKey, blocking bijection, per-route resolver) require M2 closure record + green CI.
