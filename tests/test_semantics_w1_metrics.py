"""W1 semantics corpus metrics gate tests."""

from __future__ import annotations

from figma_flutter_agent.parser.semantics.metrics import (
    KindMetrics,
    evaluate_w1_corpus,
    load_w1_manifest,
)


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


def test_kind_metrics_precision_recall() -> None:
    metrics = KindMetrics(kind="button_filled", true_positive=9, false_positive=1, false_negative=0)
    assert metrics.precision == 0.9
    assert metrics.recall == 1.0


def test_w1_gate_report_json_roundtrip() -> None:
    report = evaluate_w1_corpus()
    payload = report.to_json_dict()
    assert payload["passed"] is True
    assert "per_kind" in payload
