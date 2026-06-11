"""Fidelity text policy and baked gating (EPIC 4.5)."""

from __future__ import annotations

import pytest

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.ir.fidelity.baked_gate import evaluate_baked_emit
from figma_flutter_agent.generator.ir.fidelity.router import FidelityRoutePolicy
from figma_flutter_agent.generator.ir.fidelity.text_policy import (
    TextPolicyClass,
    classify_subtree_text_policy,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    FidelityTier,
    NodeStyle,
    NodeType,
    Sizing,
    SizingMode,
    WidgetIrKind,
    WidgetIrNode,
)
from tests.support.semantics_trees import filled_button


def test_button_text_is_live_accessibility() -> None:
    policy = classify_subtree_text_policy(filled_button())
    assert policy == TextPolicyClass.LIVE_ACCESSIBILITY


def test_marketing_banner_classified_static() -> None:
    banner = CleanDesignTreeNode(
        id="banner",
        name="banner",
        type=NodeType.STACK,
        sizing=Sizing(width=320.0, height=180.0, width_mode=SizingMode.FIXED, height_mode=SizingMode.FIXED),
        style=NodeStyle(background_color="0xFFFFE082"),
        children=[
            CleanDesignTreeNode(
                id="banner-text",
                name="title",
                type=NodeType.TEXT,
                text="Summer sale",
                sizing=Sizing(width=200.0, height=32.0),
            ),
        ],
    )
    assert classify_subtree_text_policy(banner) == TextPolicyClass.MARKETING_STATIC


def test_strict_profile_blocks_baked_live_text() -> None:
    ir = WidgetIrNode(
        figma_id="btn-filled",
        kind=WidgetIrKind.BUTTON_FILLED,
        fidelity_tier=FidelityTier.PNG_BAKED,
    )
    with pytest.raises(GenerationError, match="baked emit blocked"):
        evaluate_baked_emit(
            ir,
            clean=filled_button(),
            policy=FidelityRoutePolicy(strict_fidelity=True),
        )


def test_dev_profile_downgrades_baked_live_text() -> None:
    from figma_flutter_agent.generator.ir.fidelity.router import EmitPath

    ir = WidgetIrNode(
        figma_id="btn-filled",
        kind=WidgetIrKind.BUTTON_FILLED,
        fidelity_tier=FidelityTier.PNG_BAKED,
    )
    decision = evaluate_baked_emit(
        ir,
        clean=filled_button(),
        policy=FidelityRoutePolicy(),
    )
    assert decision.emit_path == EmitPath.STYLED_PRIMITIVE
