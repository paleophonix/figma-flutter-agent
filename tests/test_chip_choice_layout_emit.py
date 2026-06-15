"""LAW-CHIP-INTERACTIVE / LAW-CHIP-LABEL-STATIC layout emit for chip_choice IR."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.generator.ir.expression import emit_widget_expression
from figma_flutter_agent.generator.layout.flex_policy.stack import (
    layout_fact_stack_circular_option_glyph_host,
)
from figma_flutter_agent.parser.interaction import stack_interaction_kind
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    FidelityTier,
    NodeStyle,
    NodeType,
    Sizing,
    StackPlacement,
    WidgetIrKind,
    WidgetIrNode,
)


def _circular_size_option_stack(
    node_id: str,
    *,
    label: str,
    selected: bool = False,
) -> CleanDesignTreeNode:
    surface_color = "0xFFFF7622" if selected else "0xFFF0F5FA"
    text_color = "0xFFFFFFFF" if selected else "0xFF181C2E"
    return CleanDesignTreeNode(
        id=node_id,
        name="size_option",
        type=NodeType.STACK,
        sizing=Sizing(width=48.0, height=48.0),
        stack_placement=StackPlacement(left=0.0, bottom=0.0, width=48.0, height=48.0),
        children=[
            CleanDesignTreeNode(
                id=f"{node_id}:surface",
                name="surface",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=48.0, height=48.0),
                style=NodeStyle(background_color=surface_color, border_radius=110.0),
                stack_placement=StackPlacement(width=48.0, height=48.0),
            ),
            CleanDesignTreeNode(
                id=f"{node_id}:label",
                name="label",
                type=NodeType.TEXT,
                text=label,
                sizing=Sizing(width=24.0, height=19.0),
                style=NodeStyle(font_size=16.0, text_align="CENTER", text_color=text_color),
                stack_placement=StackPlacement(
                    horizontal="LEFT_RIGHT",
                    top=15.0,
                    bottom=14.0,
                    width=24.0,
                    height=19.0,
                ),
            ),
        ],
    )


def test_circular_option_not_classified_as_input() -> None:
    chip = _circular_size_option_stack("1:chip", label='10"')
    assert layout_fact_stack_circular_option_glyph_host(chip)
    assert stack_interaction_kind(chip) is None


def test_chip_choice_ir_emits_interactive_static_text() -> None:
    chip = _circular_size_option_stack("1:chip", label='10"')
    ir = WidgetIrNode(
        figma_id="1:chip",
        kind=WidgetIrKind.CHIP_CHOICE,
        is_selected=False,
        fidelity_tier=FidelityTier.NATIVE_VERIFIED,
    )
    ctx = IrEmitContext(uses_svg=False, responsive_enabled=False, semantic_report_only=True)
    body = emit_widget_expression(
        ir,
        clean=chip,
        parent_type=NodeType.STACK,
        ctx=ctx,
    )
    compact = body.replace("\n", "")
    assert "InkWell(" in compact
    assert "Semantics(button: true" in compact
    assert "Text('10" in compact or 'Text("10' in compact
    assert "TextField" not in compact


def test_chip_choice_selected_surface_color_preserved() -> None:
    chip = _circular_size_option_stack("1:chip", label="14", selected=True)
    ir = WidgetIrNode(
        figma_id="1:chip",
        kind=WidgetIrKind.CHIP_CHOICE,
        is_selected=True,
        fidelity_tier=FidelityTier.NATIVE_VERIFIED,
    )
    ctx = IrEmitContext(uses_svg=False, responsive_enabled=False, semantic_report_only=True)
    body = emit_widget_expression(ir, clean=chip, parent_type=NodeType.STACK, ctx=ctx)
    assert "Color(0xFFFF7622)" in body
    assert "selected: true" in body
