# Review baseline — systemic compiler audit

- **Captured:** 2026-06-13 (audit `figma-flutter audit all`, pytest skipped per product request)
- **Git SHA:** `756d14baccd6f683416f7a6a1810ecc29229d559`
- **Last commit:** `feat: update linting configurations and improve code quality checks`

## Signoff gate stack (blocking vs optional)

Source: [`scripts/signoff.ps1`](../../scripts/signoff.ps1)

| Step | Command / check | Blocking default | Skip env |
| --- | --- | --- | --- |
| 1 | `ruff check` + `ruff format --check` | yes | — |
| 2 | lint burndown scripts (dart/settings/colors/regex) | yes | — |
| 3 | `mypy src tests` | yes | — |
| 4 | `figma-flutter demo-signoff --strict --signoff-gates` | yes | — |
| 5 | `figma-flutter fixture-ir-validate` | yes | — |
| 6 | `figma-flutter fidelity validate` | yes | — |
| 7 | `corpus-oracle gate --blocking` | yes | `FIGMA_CORPUS_ORACLE_SIGNOFF=0` |
| 8 | `semantics corpus-gate` | yes | — |
| 9 | `semantics_legacy_burndown` | yes | — |
| 10 | `fixture-geometry-check` | yes | `FIGMA_GEOMETRY_SIGNOFF=0` |
| 11 | `pytest -m "not live_figma"` | yes | — |
| 12 | Docker golden smoke | optional | `FIGMA_SIGNOFF_DOCKER=1` |

**Oracle skip (local dev only):** `FIGMA_CORPUS_ORACLE_ALLOW_SKIP=1` allows skipped blocking screens to pass corpus-oracle (documented in `validation/oracle/README.md`).

## Default profiles

Source: [`src/figma_flutter_agent/config/profiles.py`](../../src/figma_flutter_agent/config/profiles.py)

| Profile | Applied when | Notable flags |
| --- | --- | --- |
| `apply_production_profile` | `generate` (default) | `strict_geometry_invariants`, `strict_contrast`, `spec23_dart_analyze`, `semantics.strict_fidelity` |
| `apply_signoff_profile` | `demo-signoff --signoff-gates` | spec9 gates, `runtime_fail_renderflex_overflow` |
| `apply_interactive_preview_profile` | wizard launch/run | **no-op** — returns settings unchanged |
| `apply_visual_qa_profile` | `--visual-qa` | golden tests, reference PNG |

**Generation defaults** (`config/models.py`): `llm_visual_refine: true`, `llm_visual_refine_capture_golden: false`, `semantics.report_only: true`, `semantics.enabled: true`.

## Red-flag grep summary (src/, excluding audit boundary fixtures)

| Pattern | Count / signal | Risk class |
| --- | --- | --- |
| `feature ==` / `feature_name ==` in src (excl. audit) | ~14 hits — CLI/wizard/batch infra only | **low** (no emit branches) |
| Figma id literals `"N:M"` in src | 1 hit — `generator/planner/fixtures.py` | **low** (test planner) |
| Hardcoded `0xFF…` / `Color(0x` in parser | ~21 files | **medium** — corpus-tuned palette |
| Hardcoded colors in generator emit | ~22 files | **medium** — token bypass |
| Synthetic names `ConsentRow` / `WEEKDAY_CHIP` | reconciler synthesizes + emit branches | **high** — hidden heuristic |
| `quiet_expected` / broad `except Exception` | ~40 files | **medium** — silent fallback risk |
| Text/name hints in parser (`_HINTS`, `node.name`) | ~15 files | **high** — semantic permission leak |

## Audit tooling refresh

```bash
poetry run figma-flutter audit all          # no pytest
poetry run figma-flutter audit diff-triada  # corpus normalize→emit
```

**Diff-triada note:** `elastic_form_a11y.json` skipped — raw Figma-shaped JSON fails `CleanDesignTreeNode` validation (expected; synthetic fixtures need parse path).

## Deliverables from this review

| File | Purpose |
| --- | --- |
| [`systemic-review-findings.md`](systemic-review-findings.md) | Primary findings (≥8) |
| [`latency-matrix.md`](latency-matrix.md) | Preview vs oracle path costs |
| [`gate-truth-matrix.md`](gate-truth-matrix.md) | What gates actually prove |
| [`architectural-boundaries.md`](architectural-boundaries.md) | Target mode splits |
| [`remediation-backlog.md`](remediation-backlog.md) | Updated P0–P2 from review |
