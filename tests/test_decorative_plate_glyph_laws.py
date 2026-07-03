"""Decorative plate/glyph generic laws (Program 07 P1)."""

from __future__ import annotations

from figma_flutter_agent.compiler.contracts.decorative import (
    DecorativeVerdict,
    evaluate_decorative_node,
)
from figma_flutter_agent.parser.boundaries.collapse import collapse_render_boundaries
from tests.synthetic.builders import column_tree


def test_collapse_boundary_marks_plate_role() -> None:
    tree = column_tree(depth=1)
    result = collapse_render_boundaries(tree)
    assert isinstance(result.decorative_role_map, dict)


def test_decorative_contract_report_only_collapsed_boundary() -> None:
    record = evaluate_decorative_node(
        node_id="n1",
        route="collapse_boundary",
        render_boundary=True,
        has_vector_asset=True,
    )
    assert record.verdict == DecorativeVerdict.COLLAPSED
    assert record.role == "glyph"


def test_decorative_contract_unknown_without_boundary() -> None:
    record = evaluate_decorative_node(node_id="n2", route="vector_dispatch")
    assert record.verdict == DecorativeVerdict.UNKNOWN


def test_decorative_contract_plate_without_asset() -> None:
    record = evaluate_decorative_node(
        node_id="n3",
        route="collapse_boundary",
        render_boundary=True,
        has_vector_asset=False,
    )
    assert record.role == "plate"
    assert record.tier == "png_baked"


def test_stroke_audit_empty_tree() -> None:
    from figma_flutter_agent.audit.stroke_survival import audit_stroke_chain

    assert audit_stroke_chain(column_tree()) == []
