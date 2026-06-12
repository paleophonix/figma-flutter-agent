"""Legacy semantics heuristic burn-down gate."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.semantics_legacy_burndown import (
    _PREDICATE_CALL_RE,
    collect_all_fingerprints,
    collect_zone_counts,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "semantics_legacy_burndown.py"
BASELINE = ROOT / "tests" / "fixtures" / "semantics" / "legacy_predicate_fingerprints.txt"


def test_predicate_call_regex_matches_layout_predicates() -> None:
    assert _PREDICATE_CALL_RE.search("if row_is_toolbar_leading_title_row(row):")
    assert _PREDICATE_CALL_RE.search("def stack_is_card_metadata_host(node):")
    assert _PREDICATE_CALL_RE.search("hosts_primary_button(row)")


def test_layout_emit_zone_has_predicate_calls() -> None:
    fingerprints = collect_all_fingerprints()
    zones = collect_zone_counts(fingerprints)
    assert zones["layout_emit"] > 0
    assert zones["layout_flex_policy"] > 0


def test_legacy_burndown_passes_with_committed_baseline(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--write-report",
            str(report),
            "--baseline",
            str(BASELINE),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["fingerprint_ok"] is True
    assert payload["currentCount"] == len(collect_all_fingerprints())


def test_legacy_burndown_fails_on_new_fingerprint(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.txt"
    report = tmp_path / "report.json"
    current = collect_all_fingerprints()
    from scripts.lint_baseline import write_fingerprint_baseline

    trimmed = current[:-1]
    write_fingerprint_baseline(trimmed, baseline)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--write-report",
            str(report),
            "--baseline",
            str(baseline),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["fingerprint_ok"] is False
    assert payload["added"]
