"""Snapshot test for semantic classification report schema."""

from __future__ import annotations

import json

from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.parser.semantics.classify import classify_screen_ir
from tests.support.semantics_trees import filled_button


def test_classification_report_schema_snapshot() -> None:
    clean = filled_button()
    screen_ir = default_screen_ir(clean)
    _, report = classify_screen_ir(screen_ir, clean)
    assert report.semantic is not None
    payload = report.semantic.to_dict()
    assert "accepted" in payload
    assert "rejectedBelowThreshold" in payload
    assert "rejectedByInvariant" in payload
    assert "legacySemanticTypeDetected" in payload
    assert "nameSignalUsed" in payload
    assert "llmAnnotationUsed" in payload
    assert payload["acceptedCount"] >= 1
    json.dumps(payload)
