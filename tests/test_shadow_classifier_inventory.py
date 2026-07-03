"""Shadow classifier inventory and baseline ratchet tests (Program 03 P0-0)."""

from __future__ import annotations

from figma_flutter_agent.audit.shadow_classifier import (
    ShadowClassifierRecord,
    _repo_root,
    compare_ratchet,
    records_from_json,
    records_to_json,
    scan_generator_interaction_usage,
)

_BASELINE_JSON = (
    _repo_root() / "docs/refactor/generated/shadow-classifier-inventory.json"
)


def test_scan_is_deterministic() -> None:
    first = records_to_json(scan_generator_interaction_usage())
    second = records_to_json(scan_generator_interaction_usage())
    assert first == second


def test_baseline_json_matches_live_scan() -> None:
    assert _BASELINE_JSON.is_file()
    baseline = records_from_json(_BASELINE_JSON.read_text(encoding="utf-8"))
    live = scan_generator_interaction_usage()
    assert records_to_json(baseline) == records_to_json(live)


def test_ratchet_passes_on_unchanged_baseline() -> None:
    baseline = records_from_json(_BASELINE_JSON.read_text(encoding="utf-8"))
    report = compare_ratchet(baseline=baseline, current=baseline)
    assert report.passed is True
    assert not report.new_kind_decider
    assert not report.new_emit_archetype_decider
    assert not report.new_unknown
    assert not report.removed_without_baseline_update


def test_ratchet_fails_on_new_emit_archetype_decider() -> None:
    baseline = records_from_json(_BASELINE_JSON.read_text(encoding="utf-8"))
    rogue = ShadowClassifierRecord(
        path="src/figma_flutter_agent/generator/ir/expression.py",
        symbol="emit_widget_expression",
        imported_symbol="synthetic_new_decider",
        category="emit_archetype_decider",
        semantic_family="general",
        rationale="test ratchet",
    )
    report = compare_ratchet(baseline=baseline, current=[*baseline, rogue])
    assert report.passed is False
    assert len(report.new_emit_archetype_decider) == 1


def test_generated_markdown_exists() -> None:
    md = _repo_root() / "docs/refactor/03-shadow-classifier-inventory.md"
    assert md.is_file()
    assert "Shadow classifier inventory" in md.read_text(encoding="utf-8")


def test_write_inventory_roundtrip() -> None:
    records = scan_generator_interaction_usage()[:3]
    text = records_to_json(records)
    restored = records_from_json(text)
    assert restored == records
