"""Shadow classifier inventory and baseline ratchet tests (Program 03 P0-0)."""

from __future__ import annotations

import json

from figma_flutter_agent.audit.shadow_classifier import (
    INVENTORY_JSON_REL,
    RATCHET_BASELINE_JSON_REL,
    ShadowClassifierRecord,
    _repo_root,
    compare_ratchet,
    load_ratchet_baseline_records,
    records_from_json,
    run_shadow_ratchet_gate,
    scan_generator_interaction_usage,
)

_INVENTORY_JSON = _repo_root() / INVENTORY_JSON_REL
_RATCHET_BASELINE_JSON = _repo_root() / RATCHET_BASELINE_JSON_REL


def test_scan_is_deterministic() -> None:
    first = scan_generator_interaction_usage()
    second = scan_generator_interaction_usage()
    assert first == second


def test_ratchet_live_scan_against_approved_baseline() -> None:
    report = run_shadow_ratchet_gate()
    assert report.passed is True
    assert not report.new_kind_decider
    assert not report.new_emit_archetype_decider
    assert not report.new_unknown


def test_ratchet_baseline_not_loaded_from_working_tree_inventory() -> None:
    baseline, source = load_ratchet_baseline_records()
    assert _INVENTORY_JSON.is_file()
    working_inventory = records_from_json(_INVENTORY_JSON.read_text(encoding="utf-8"))
    rogue = ShadowClassifierRecord(
        path="src/figma_flutter_agent/generator/ir/expression.py",
        symbol="emit_widget_expression",
        imported_symbol="synthetic_inventory_only_decider",
        category="emit_archetype_decider",
        semantic_family="general",
        rationale="inventory regen bypass attempt",
    )
    corrupted_inventory = [*working_inventory, rogue]
    _INVENTORY_JSON.write_text(
        json.dumps(
            [
                {
                    "path": item.path,
                    "symbol": item.symbol,
                    "imported_symbol": item.imported_symbol,
                    "category": item.category,
                    "semantic_family": item.semantic_family,
                    "rationale": item.rationale,
                    "status": item.status,
                }
                for item in corrupted_inventory
            ],
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    try:
        reloaded, _ = load_ratchet_baseline_records()
        live = scan_generator_interaction_usage()
        report = compare_ratchet(baseline=reloaded, current=live)
        assert rogue not in reloaded
        assert report.passed is True
        assert "inventory.json" not in source or source.startswith("git:")
    finally:
        _INVENTORY_JSON.write_text(
            _RATCHET_BASELINE_JSON.read_text(encoding="utf-8"),
            encoding="utf-8",
        )


def test_ratchet_passes_on_unchanged_baseline() -> None:
    baseline, _ = load_ratchet_baseline_records()
    report = compare_ratchet(baseline=baseline, current=baseline)
    assert report.passed is True
    assert not report.new_kind_decider
    assert not report.new_emit_archetype_decider
    assert not report.new_unknown
    assert not report.removed_without_baseline_update


def test_ratchet_allows_remediation_shrink() -> None:
    baseline, _ = load_ratchet_baseline_records()
    assert baseline
    current = baseline[1:]
    report = compare_ratchet(baseline=baseline, current=current)
    assert report.passed is True
    assert report.removed_without_baseline_update


def test_ratchet_allows_new_fact_reader() -> None:
    baseline, _ = load_ratchet_baseline_records()
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
    baseline, _ = load_ratchet_baseline_records()
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
    baseline, _ = load_ratchet_baseline_records()
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


def test_frozen_ratchet_baseline_file_exists() -> None:
    assert _RATCHET_BASELINE_JSON.is_file()


def test_generated_markdown_exists() -> None:
    md = _repo_root() / "docs/refactor/26-06-06-compiler-refactor/03-shadow-classifier-inventory.md"
    assert md.is_file()
    assert "Shadow classifier inventory" in md.read_text(encoding="utf-8")
