"""Tests for constraint consumer inventory ratchet (06-P0-0a)."""

from __future__ import annotations

from figma_flutter_agent.audit.constraint_consumer import (
    INVENTORY_JSON_REL,
    RATCHET_BASELINE_JSON_REL,
    ConstraintConsumerRecord,
    _repo_root,
    compare_constraint_ratchet,
    load_ratchet_baseline_records,
    records_from_json,
    run_constraint_consumer_ratchet_gate,
    scan_constraint_consumers,
    write_inventory_artifacts,
)

_INVENTORY_JSON = _repo_root() / INVENTORY_JSON_REL
_RATCHET_BASELINE_JSON = _repo_root() / RATCHET_BASELINE_JSON_REL


def test_scan_is_deterministic() -> None:
    first = scan_constraint_consumers()
    second = scan_constraint_consumers()
    assert first == second
    assert first


def test_ratchet_live_scan_against_baseline() -> None:
    report = run_constraint_consumer_ratchet_gate()
    assert report.passed is True
    assert not report.new_direct_consumer


def test_ratchet_allows_shrink() -> None:
    baseline, _ = load_ratchet_baseline_records()
    assert baseline
    current = baseline[1:]
    report = compare_constraint_ratchet(baseline=baseline, current=current)
    assert report.passed is True


def test_ratchet_blocks_new_direct_consumer() -> None:
    baseline, _ = load_ratchet_baseline_records()
    rogue = ConstraintConsumerRecord(
        path="src/figma_flutter_agent/generator/geometry/slots.py",
        symbol="synthetic_rogue",
        token="LEFT_RIGHT",
        line=1,
        category="planner_slot",
        axis="horizontal",
        rationale="test rogue",
    )
    report = compare_constraint_ratchet(baseline=baseline, current=[*baseline, rogue])
    assert report.passed is False
    assert rogue in report.new_direct_consumer


def test_baseline_not_from_working_inventory_only() -> None:
    baseline, source = load_ratchet_baseline_records()
    assert baseline
    assert "inventory" not in source or source.startswith("git:") or source.startswith("frozen:")


def test_write_inventory_matches_scan() -> None:
    scanned = scan_constraint_consumers()
    written = write_inventory_artifacts(json_path=_INVENTORY_JSON, records=scanned)
    loaded = records_from_json(_INVENTORY_JSON.read_text(encoding="utf-8"))
    assert written == loaded
