"""JSON report writers for corpus oracle gates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from figma_flutter_agent.validation.oracle.models import CorpusGateReport


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_blocking_gate_json(report: CorpusGateReport, path: Path) -> None:
    """Write blocking subset gate report."""
    blocking = report.blocking_results()
    payload = {
        "passed": report.blocking_passed,
        "screen_count": len(blocking),
        "results": [item.to_dict() for item in blocking],
    }
    _write_json(path, payload)


def write_advisory_report_json(report: CorpusGateReport, path: Path) -> None:
    """Write full corpus advisory report."""
    payload = {
        "blocking_passed": report.blocking_passed,
        "full_corpus_passed": report.full_corpus_passed,
        "advisory_only_failures": report.advisory_only_failures,
        "results": [item.to_dict() for item in report.results],
    }
    _write_json(path, payload)


def write_promotion_candidates_json(report: CorpusGateReport, path: Path) -> None:
    """Write fidelity promotion candidate recommendations."""
    payload = {
        "candidate_count": len(report.promotion_candidates),
        "candidates": [item.to_dict() for item in report.promotion_candidates],
    }
    _write_json(path, payload)


def write_all_oracle_reports(report: CorpusGateReport, report_dir: Path) -> None:
    """Write all standard oracle artifacts under ``report_dir``."""
    write_blocking_gate_json(report, report_dir / "blocking_gate.json")
    write_advisory_report_json(report, report_dir / "advisory_pixel_report.json")
    write_promotion_candidates_json(report, report_dir / "fidelity_promotion_candidates.json")
