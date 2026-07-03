"""Tests for tier-0 layout scorer shadow (05-P0-4)."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.passes.layout_scorer import score_layout_candidates_shadow
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def test_scorer_emits_breakdown_candidates() -> None:
    stack = CleanDesignTreeNode(
        id="s1",
        name="stack",
        type=NodeType.STACK,
        children=[
            CleanDesignTreeNode(id="c1", name="a", type=NodeType.TEXT, children=[]),
            CleanDesignTreeNode(id="c2", name="b", type=NodeType.TEXT, children=[]),
        ],
    )
    audit = score_layout_candidates_shadow(stack)
    assert len(audit.candidates) == 4
    assert all(candidate.score.total >= 0 for candidate in audit.candidates)


def test_scorer_abstains_on_single_child() -> None:
    node = CleanDesignTreeNode(
        id="solo",
        name="solo",
        type=NodeType.STACK,
        children=[CleanDesignTreeNode(id="c1", name="a", type=NodeType.TEXT, children=[])],
    )
    audit = score_layout_candidates_shadow(node)
    assert audit.abstained is True
