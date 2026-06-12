"""W1 semantics corpus metrics gate tests."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.parser.semantics.corpus import (
    CorpusCase,
    allowed_semantic_target_ids,
)
from figma_flutter_agent.parser.semantics.metrics import (
    KindMetrics,
    audit_full_tree_w1_semantics,
    evaluate_w1_corpus,
    load_w1_manifest,
)
from figma_flutter_agent.schemas import WidgetIrKind, WidgetIrNode


def test_w1_manifest_loads() -> None:
    manifest = load_w1_manifest()
    assert len(manifest.kinds) == 8
    assert len(manifest.positive_paths) >= 24
    assert len(manifest.blocker_negative_paths) >= 6


def test_w1_corpus_gate_passes() -> None:
    report = evaluate_w1_corpus()
    assert report.passed is True
    assert report.overall_precision is not None and report.overall_precision >= 0.95
    assert report.overall_recall is not None and report.overall_recall >= 0.80
    assert report.blocker_negative_false_positives == 0
    assert report.full_tree_semantic_fp_count == 0
    assert report.unexpected_semantic_nodes == []


def test_kind_metrics_precision_recall() -> None:
    metrics = KindMetrics(kind="button_filled", true_positive=9, false_positive=1, false_negative=0)
    assert metrics.precision == 0.9
    assert metrics.recall == 1.0


def test_w1_gate_report_json_roundtrip() -> None:
    report = evaluate_w1_corpus()
    payload = report.to_json_dict()
    assert payload["passed"] is True
    assert "per_kind" in payload
    assert payload["full_tree_semantic_fp_count"] == 0


def test_allowed_semantic_target_ids_positive_vs_trap() -> None:
    positive = CorpusCase(
        path=Path("positive/x.json"),
        expected_kind=WidgetIrKind.BUTTON_FILLED,
        forbidden_kinds=frozenset(),
        target_figma_id="btn-1",
    )
    trap = CorpusCase(
        path=Path("negative/x.json"),
        expected_kind=None,
        forbidden_kinds=frozenset({WidgetIrKind.BUTTON_FILLED}),
        target_figma_id="trap-1",
    )
    assert allowed_semantic_target_ids(positive) == frozenset({"btn-1"})
    assert allowed_semantic_target_ids(trap) == frozenset()


def test_full_tree_audit_trap_flags_forbidden_kind_only() -> None:
    case = CorpusCase(
        path=Path("negative/size_picker.json"),
        expected_kind=None,
        forbidden_kinds=frozenset({WidgetIrKind.CHIP_CHOICE, WidgetIrKind.CHIP_FILTER}),
        target_figma_id="size-picker",
    )
    root = WidgetIrNode(
        figma_id="size-picker",
        kind=WidgetIrKind.AUTO,
        children=[
            WidgetIrNode(
                figma_id="size-picker-s",
                kind=WidgetIrKind.BUTTON_OUTLINED,
                children=[],
            ),
        ],
    )
    assert audit_full_tree_w1_semantics(case, updated_ir_root=root) == []


def test_full_tree_audit_flags_neighbor_w1_kind() -> None:
    case = CorpusCase(
        path=Path("positive/chip.json"),
        expected_kind=WidgetIrKind.CHIP_CHOICE,
        forbidden_kinds=frozenset(),
        target_figma_id="chip-row",
    )
    root = WidgetIrNode(
        figma_id="chip-row",
        kind=WidgetIrKind.CHIP_CHOICE,
        children=[
            WidgetIrNode(
                figma_id="neighbor-btn",
                kind=WidgetIrKind.BUTTON_FILLED,
                children=[],
            ),
        ],
    )
    hits = audit_full_tree_w1_semantics(case, updated_ir_root=root)
    assert len(hits) == 1
    assert hits[0].figma_id == "neighbor-btn"
    assert hits[0].allowed_semantic_target_ids == ("chip-row",)
