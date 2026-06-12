# validation/oracle

## Purpose

Orchestrate real-design corpus gates: blocking subset pixel/geometry checks, advisory full-corpus reports, and fidelity promotion candidate evidence (no manifest mutation).

## Usage Example

```python
from pathlib import Path

from figma_flutter_agent.validation.oracle import run_corpus_oracle, write_all_oracle_reports

report = run_corpus_oracle()
write_all_oracle_reports(report, Path("logs/oracle"))
assert report.blocking_passed
```

CLI:

```bash
poetry run figma-flutter corpus-oracle gate --blocking --write-report-dir logs/oracle
```

## LLM Context

Inject `CorpusGateReport.to_dict()` or the three JSON artifacts (`blocking_gate.json`, `advisory_pixel_report.json`, `fidelity_promotion_candidates.json`) when diagnosing corpus regressions. `text_region_pixel_diff` is advisory pre-E7; only `non_text_pixel_diff`, `geometry_iou`, and `text_bounds_delta` block release on `strict_pixel_blocking` fixtures.
