"""Tests for decorative decision inventory ratchet (07-P0-0)."""

from __future__ import annotations

from figma_flutter_agent.audit.decorative_decision import (
    INVENTORY_JSON_REL,
    RATCHET_BASELINE_JSON_REL,
    DecorativeDecisionRecord,
    _repo_root,
    compare_decorative_ratchet,
    load_ratchet_baseline_records,
    records_from_json,
    run_decorative_decision_ratchet_gate,
    scan_decorative_decisions,
    write_inventory_artifacts,
)

_INVENTORY_JSON = _repo_root() / INVENTORY_JSON_REL
_RATchet_BASELINE_JSON = _repo_root() / RATCHET_BASELINE_JSON_REL


def test_scan_is_deterministic() -> None:
    assert scan_decorative_decisions() == scan_decorative_decisions()
    assert scan_decorative_decisions()


def test_ratchet_live_scan_against_baseline() -> None:
    report = run_decorative_decision_ratchet_gate()
    assert report.passed is True
    assert not report.new_unknown


def test_ratchet_blocks_new_unknown_route() -> None:
    baseline, _ = load_ratchet_baseline_records()
    rogue = DecorativeDecisionRecord(
        path="src/figma_flutter_agent/synthetic/rogue.py",
        symbol="rogue",
        route="unknown",
        marker="rogue_marker",
        line=1,
        rationale="test",
    )
    report = compare_decorative_ratchet(baseline=baseline, current=[*baseline, rogue])
    assert report.passed is False
    assert rogue in report.new_unknown


def test_write_inventory_matches_scan() -> None:
    scanned = scan_decorative_decisions()
    written = write_inventory_artifacts(json_path=_INVENTORY_JSON, records=scanned)
    loaded = records_from_json(_INVENTORY_JSON.read_text(encoding="utf-8"))
    assert written == loaded
