# audit

## Purpose

Systemic pipeline audit tooling: corpus diff-triada, predicate overlap matrix, baseline capture, and markdown deliverables for compiler layer reviews.

## Usage Example

```bash
poetry run figma-flutter audit all
poetry run figma-flutter audit diff-triada
poetry run figma-flutter audit predicate-matrix
```

```python
from figma_flutter_agent.audit import run_diff_triada, build_predicate_matrix
from pathlib import Path

records = run_diff_triada(output_dir=Path("docs/audit/26-06-13-pipeline-audit/artifacts"))
cells = build_predicate_matrix()
```

## LLM Context

Do not inject full audit JSON into prompts. Summarize `remediation-backlog.md` P0–P1 items and predicate-overlap rows where multiple `row_is_*` predicates match one pattern.
