"""Semantic detector registry coverage."""

from __future__ import annotations

from figma_flutter_agent.parser.semantics.detectors import DETECTORS
from figma_flutter_agent.parser.semantics.prefilter import SEMANTIC_IR_KINDS


def test_all_semantic_kinds_have_detectors() -> None:
    missing = sorted(kind.value for kind in SEMANTIC_IR_KINDS - set(DETECTORS))
    assert missing == [], f"missing detectors: {missing}"
