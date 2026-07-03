# Systemic pipeline audit

Automated artifacts for the Figma→Flutter compiler systemic review.

## Refresh

```bash
poetry run figma-flutter audit all
poetry run figma-flutter audit all --run-pytest   # include pytest summary in baseline
```

## Artifacts

| File | Phase |
| --- | --- |
| `baseline.md` | 0 — git SHA, pytest summary |
| `diff-triada-summary.md` | 0/4 — corpus normalize+emit |
| `artifacts/diff_triada.json` | 0 — machine-readable triada |
| `parse-classification.md` | 1 |
| `interaction-predicates.md` | 1 |
| `reconcile-passes.md` | 2 |
| `artifacts/predicate-overlap-matrix.md` | 3 |
| `geometry-emit-fidelity.md` | 4 |
| `ir-llm-coverage.md` | 5 |
| `gates-gap-analysis.md` | 6 |
| `test-conflicts.md` | 7 |
| `remediation-backlog.md` | 8 |
| `pipeline-contracts.md` | 8 |

## Source

Python package: `src/figma_flutter_agent/audit/`.
