"""Profile-aware fidelity routing matrix (EPIC 4.5)."""

from __future__ import annotations

import pytest

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.ir.fidelity.baked_gate import evaluate_baked_emit
from figma_flutter_agent.generator.ir.fidelity.router import (
    EmitPath,
    FidelityRoutePolicy,
    route_with_policy,
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


def _marketing_banner() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="banner",
        name="banner",
        type=NodeType.STACK,
        sizing=Sizing(
            width=320.0, height=180.0, width_mode=SizingMode.FIXED, height_mode=SizingMode.FIXED
        ),
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


def test_strict_l10n_blocks_marketing_baked_text() -> None:
    ir = WidgetIrNode(
        figma_id="banner",
        kind=WidgetIrKind.CONTAINER_CARD,
        fidelity_tier=FidelityTier.PNG_BAKED,
    )
    with pytest.raises(GenerationError):
        evaluate_baked_emit(
            ir,
            clean=_marketing_banner(),
            policy=FidelityRoutePolicy(strict_l10n=True),
        )


def test_unsupported_strict_fidelity_hard_fail() -> None:
    ir = WidgetIrNode(
        figma_id="x",
        kind=WidgetIrKind.BUTTON_FILLED,
        fidelity_tier=FidelityTier.UNSUPPORTED,
    )
    with pytest.raises(GenerationError, match="strict_fidelity"):
        route_with_policy(ir, policy=FidelityRoutePolicy(strict_fidelity=True))


def test_unsupported_dev_routes_styled_primitive() -> None:
    ir = WidgetIrNode(
        figma_id="x",
        kind=WidgetIrKind.BUTTON_FILLED,
        fidelity_tier=FidelityTier.UNSUPPORTED,
    )
    assert route_with_policy(ir, policy=FidelityRoutePolicy()) == EmitPath.STYLED_PRIMITIVE
