"""Semantic context assembler tests (offline)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from figma_flutter_agent.llm.semantic_context import (
    assemble_semantic_context,
    collect_forbidden_semantic_keys,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "semantic_ir" / "feedback_layout.json"

REQUIRED_TEXTS = (
    "Your project is finished.",
    "How would you rate the prototyping kit?",
    "What did you like about it?",
    "What could be improved?",
    "Anything else?",
    "Tell us everything.",
    "Submit",
)


@pytest.fixture
def feedback_tree() -> CleanDesignTreeNode:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return CleanDesignTreeNode.model_validate(payload)


def test_raw_context_present_and_root_is_feedback(feedback_tree: CleanDesignTreeNode) -> None:
    packet = assemble_semantic_context(feedback_tree)
    assert packet.raw_context["name"] == "Feedback"
    assert packet.raw_context["id"] == "281:7179"


def test_tree_outline_includes_feedback_root(feedback_tree: CleanDesignTreeNode) -> None:
    packet = assemble_semantic_context(feedback_tree)
    root_rows = [row for row in packet.tree_outline if row["id"] == "281:7179"]
    assert root_rows
    assert root_rows[0]["name"] == "Feedback"
    assert root_rows[0]["children_count"] == 3


@pytest.mark.parametrize("snippet", REQUIRED_TEXTS)
def test_text_inventory_includes_required_copy(
    feedback_tree: CleanDesignTreeNode,
    snippet: str,
) -> None:
    packet = assemble_semantic_context(feedback_tree)
    texts = [row["text"] for row in packet.text_inventory]
    assert snippet in texts


def test_component_inventory_includes_star_rating_text_area_and_button(
    feedback_tree: CleanDesignTreeNode,
) -> None:
    packet = assemble_semantic_context(feedback_tree)
    by_id = {row["id"]: row for row in packet.component_inventory}
    assert by_id["281:7386"]["componentName"] == "Star Rating"
    assert by_id["281:7386"]["variantProperties"]["Rating"] == "4"
    assert by_id["281:7500"]["componentName"] == "Text Area"
    assert by_id["281:7600"]["componentName"] == "Button Primary"


def test_relationship_hints_include_column_sibling_before_star_rating(
    feedback_tree: CleanDesignTreeNode,
) -> None:
    packet = assemble_semantic_context(feedback_tree)
    kinds = {
        (hint["from_node_id"], hint["to_node_id"], hint["kind"])
        for hint in packet.relationship_hints
    }
    assert ("281:7261", "281:7386", "next_sibling_in_column") in kinds


def test_context_packet_has_no_forbidden_semantic_keys(feedback_tree: CleanDesignTreeNode) -> None:
    packet = assemble_semantic_context(feedback_tree)
    forbidden = collect_forbidden_semantic_keys(packet.model_dump_for_llm())
    assert forbidden == []
