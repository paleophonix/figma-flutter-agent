"""Baked fidelity tier emit (U6 / EPIC 4.5)."""

from __future__ import annotations

import pytest

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.generator.ir.expression import emit_widget_expression
from figma_flutter_agent.generator.ir.fidelity.baked_emit import emit_baked_asset
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    FidelityTier,
    NodeType,
    Sizing,
    SizingMode,
    WidgetIrKind,
    WidgetIrNode,
)


def _icon_vector(*, node_id: str = "icon-1") -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name="Icon",
        type=NodeType.VECTOR,
        sizing=Sizing(
            width=24.0,
            height=24.0,
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FIXED,
        ),
        vector_asset_key="assets/icons/star.svg",
    )


def _icon_png(*, node_id: str = "icon-2") -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name="Badge",
        type=NodeType.IMAGE,
        sizing=Sizing(
            width=32.0,
            height=32.0,
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FIXED,
        ),
        image_asset_key="assets/images/badge.png",
    )


def test_emit_baked_asset_svg() -> None:
    clean = _icon_vector()
    ir = WidgetIrNode(
        figma_id="icon-1",
        kind=WidgetIrKind.BUTTON_ICON,
        fidelity_tier=FidelityTier.SVG_BAKED,
    )
    ctx = IrEmitContext(uses_svg=True, responsive_enabled=False)
    dart = emit_baked_asset(ir, clean=clean, ctx=ctx)
    assert "SvgPicture.asset(" in dart
    assert "assets/icons/star.svg" in dart


def test_emit_baked_asset_png() -> None:
    clean = _icon_png()
    ir = WidgetIrNode(
        figma_id="icon-2",
        kind=WidgetIrKind.BUTTON_ICON,
        fidelity_tier=FidelityTier.PNG_BAKED,
    )
    ctx = IrEmitContext(uses_svg=False, responsive_enabled=False)
    dart = emit_baked_asset(ir, clean=clean, ctx=ctx)
    assert "Image.asset(" in dart
    assert "assets/images/badge.png" in dart


def test_emit_baked_asset_missing_export_raises() -> None:
    clean = CleanDesignTreeNode(
        id="empty",
        name="Empty",
        type=NodeType.VECTOR,
        sizing=Sizing(width=24.0, height=24.0),
    )
    ir = WidgetIrNode(
        figma_id="empty",
        kind=WidgetIrKind.BUTTON_ICON,
        fidelity_tier=FidelityTier.PNG_BAKED,
    )
    with pytest.raises(GenerationError, match="no exportable asset"):
        emit_baked_asset(ir, clean=clean, ctx=IrEmitContext())


def test_expression_baked_tier_emits_image_for_icon_only_subtree() -> None:
    clean = _icon_png(node_id="baked-btn")
    ir = WidgetIrNode(
        figma_id="baked-btn",
        kind=WidgetIrKind.BUTTON_ICON,
        fidelity_tier=FidelityTier.PNG_BAKED,
    )
    ctx = IrEmitContext(
        semantic_report_only=False,
        uses_svg=False,
        responsive_enabled=False,
    )
    dart = emit_widget_expression(ir, clean=clean, parent_type=None, ctx=ctx)
    assert "Image.asset(" in dart
    assert "Theme.of(context).colorScheme.primary" not in dart
