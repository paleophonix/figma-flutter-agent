"""Shadow classifier inventory and baseline ratchet tests (Program 03 P0-0)."""

from __future__ import annotations

from figma_flutter_agent.audit.shadow_classifier import (
    ShadowClassifierRecord,
    _repo_root,
    compare_ratchet,
    records_from_json,
    scan_generator_interaction_usage,
)

_BASELINE_JSON = (
    _repo_root() / "docs/refactor/generated/shadow-classifier-inventory.json"
)


def test_scan_is_deterministic() -> None:
    first = scan_generator_interaction_usage()
    second = scan_generator_interaction_usage()
    assert first == second


def test_ratchet_live_scan_against_committed_baseline() -> None:
    assert _BASELINE_JSON.is_file()
    baseline = records_from_json(_BASELINE_JSON.read_text(encoding="utf-8"))
    live = scan_generator_interaction_usage()
    report = compare_ratchet(baseline=baseline, current=live)
    assert report.passed is True
    assert not report.new_kind_decider
    assert not report.new_emit_archetype_decider
    assert not report.new_unknown


def test_ratchet_passes_on_unchanged_baseline() -> None:
    baseline = records_from_json(_BASELINE_JSON.read_text(encoding="utf-8"))
    report = compare_ratchet(baseline=baseline, current=baseline)
    assert report.passed is True
    assert not report.new_kind_decider
    assert not report.new_emit_archetype_decider
    assert not report.new_unknown
    assert not report.removed_without_baseline_update


def test_ratchet_allows_remediation_shrink() -> None:
    baseline = records_from_json(_BASELINE_JSON.read_text(encoding="utf-8"))
    assert baseline
    current = baseline[1:]
    report = compare_ratchet(baseline=baseline, current=current)
    assert report.passed is True
    assert report.removed_without_baseline_update


def test_ratchet_allows_new_fact_reader() -> None:
    baseline = records_from_json(_BASELINE_JSON.read_text(encoding="utf-8"))
    allowed = ShadowClassifierRecord(
        path="src/figma_flutter_agent/generator/ir/expression.py",
        symbol="emit_widget_expression",
        imported_symbol="synthetic_fact_reader",
        category="fact_reader",
        semantic_family="general",
        rationale="test ratchet allow",
    )
    report = compare_ratchet(baseline=baseline, current=[*baseline, allowed])
    assert report.passed is True


def test_ratchet_blocks_new_emit_archetype_decider() -> None:
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


def test_ratchet_blocks_new_kind_decider() -> None:
    baseline = records_from_json(_BASELINE_JSON.read_text(encoding="utf-8"))
    rogue = ShadowClassifierRecord(
        path="src/figma_flutter_agent/generator/ir/expression.py",
        symbol="emit_widget_expression",
        imported_symbol="synthetic_kind_decider",
        category="kind_decider",
        semantic_family="general",
        rationale="test ratchet",
    )
    report = compare_ratchet(baseline=baseline, current=[*baseline, rogue])
    assert report.passed is False
    assert len(report.new_kind_decider) == 1


def test_generated_markdown_exists() -> None:
    md = _repo_root() / "docs/refactor/03-shadow-classifier-inventory.md"
    assert md.is_file()
    assert "Shadow classifier inventory" in md.read_text(encoding="utf-8")
