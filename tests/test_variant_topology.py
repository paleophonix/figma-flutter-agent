"""Variant topology signature and split decisions (WP-3)."""

from __future__ import annotations

from figma_flutter_agent.generator.variant_props import ComponentConfig
from figma_flutter_agent.generator.variant_topology import (
    compare_variant_topology,
    validate_variant_signature,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing


def test_variant_topology_split() -> None:
    left = CleanDesignTreeNode(
        id="v1",
        name="Primary",
        type=NodeType.BUTTON,
        sizing=Sizing(width=120.0, height=48.0),
        children=[
            CleanDesignTreeNode(
                id="v1-label",
                name="Label",
                type=NodeType.TEXT,
            )
        ],
    )
    right = CleanDesignTreeNode(
        id="v2",
        name="Secondary",
        type=NodeType.BUTTON,
        sizing=Sizing(width=120.0, height=48.0),
        children=[
            CleanDesignTreeNode(
                id="v2-icon",
                name="Icon",
                type=NodeType.VECTOR,
            ),
            CleanDesignTreeNode(
                id="v2-label",
                name="Label",
                type=NodeType.TEXT,
            ),
        ],
    )
    decision = compare_variant_topology(left, right)
    assert decision.should_split
    assert decision.similarity < 0.85
    drift = validate_variant_signature([left, right])
    assert drift


def test_widget_signature_backward_compatible() -> None:
    cfg = ComponentConfig(visible=True, frozen_params=("isEnabled",))
    assert cfg.visible is True
    assert cfg.frozen_params == ("isEnabled",)
