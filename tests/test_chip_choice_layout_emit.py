"""LAW-CHIP-INTERACTIVE / LAW-CHIP-LABEL-STATIC layout emit for chip_choice IR."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.generator.ir.expression import emit_widget_expression
from figma_flutter_agent.generator.layout.flex_policy.stack import (
    layout_fact_stack_circular_option_glyph_host,
)
from figma_flutter_agent.generator.layout.widgets import render_node_body
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
    assert "selected: true" in body
    assert "BoxDecoration" in body or "decoration:" in body


def test_layout_path_chip_choice_emits_interactive_surface() -> None:
    chip = _circular_size_option_stack("1:chip", label='10"')
    ir = WidgetIrNode(
        figma_id="1:chip",
        kind=WidgetIrKind.CHIP_CHOICE,
        is_selected=False,
        fidelity_tier=FidelityTier.NATIVE_VERIFIED,
    )
    body = render_node_body(
        chip,
        uses_svg=False,
        ir_by_id={"1:chip": ir},
    )
    compact = body.replace("\n", "")
    assert "InkWell(" in compact
    assert "Semantics(button: true" in compact
    assert "TextField" not in compact


def test_structural_chip_choice_selected_from_orange_surface() -> None:
    """Circular chips infer selection from painted surface without IR metadata."""
    chip = _circular_size_option_stack("1:chip", label="14", selected=True)
    body = render_node_body(chip, uses_svg=False)
    assert "selected: true" in body


def test_circular_option_chip_row_emits_stateful_mutual_selection() -> None:
    """Chip rows emit a StatefulWidget with mutual exclusive selection on tap."""
    from figma_flutter_agent.generator.layout.interactive import interactive_layout_helpers

    row = CleanDesignTreeNode(
        id="size:row",
        name="Sizes",
        type=NodeType.STACK,
        sizing=Sizing(width=200.0, height=48.0),
        children=[
            _circular_size_option_stack("chip:s", label="S"),
            _circular_size_option_stack("chip:m", label="M", selected=True),
            _circular_size_option_stack("chip:l", label="L"),
        ],
    )
    body = render_node_body(row, uses_svg=False)
    compact = body.replace("\n", "")
    helpers = interactive_layout_helpers(row)
    assert "_GeneratedCircularOptionChipRow" in compact
    assert "_GeneratedCircularOptionChipRowState" in helpers
    assert "setState(() => _selectedIndex = index)" in helpers


def test_circular_option_chip_row_body_omits_positioned_wrapper() -> None:
    """Chip row body must not emit Positioned; parent stack owns placement."""
    from figma_flutter_agent.generator.layout.choice_chip_row import (
        render_circular_option_chip_row_stateful,
    )

    row = CleanDesignTreeNode(
        id="size:row",
        name="Sizes",
        type=NodeType.STACK,
        sizing=Sizing(width=200.0, height=48.0),
        stack_placement=StackPlacement(left=24.0, top=558.0, width=216.0, height=48.0),
        children=[
            _circular_size_option_stack("chip:s", label="S"),
            _circular_size_option_stack("chip:m", label="M", selected=True),
            _circular_size_option_stack("chip:l", label="L"),
        ],
    )
    body = render_circular_option_chip_row_stateful(row)
    assert body.startswith("_GeneratedCircularOptionChipRow(")
    assert "Positioned(" not in body


def test_circular_option_chip_row_role_palette_is_shared() -> None:
    """Selected/unselected foreground must follow surface contrast, not per-chip Figma fill."""
    from figma_flutter_agent.generator.layout.choice_chip_row import (
        render_circular_option_chip_row_stateful,
    )

    row = CleanDesignTreeNode(
        id="size:row",
        name="Sizes",
        type=NodeType.STACK,
        sizing=Sizing(width=200.0, height=48.0),
        children=[
            _circular_size_option_stack("chip:s", label="S"),
            _circular_size_option_stack("chip:m", label="M", selected=True),
            _circular_size_option_stack("chip:l", label="L"),
        ],
    )
    body = render_circular_option_chip_row_stateful(row)
    assert body.count("selectedFg: Theme.of(context).colorScheme.onPrimary") >= 1
    assert body.count("unselectedFg: Theme.of(context).colorScheme.onSurface") >= 1
    assert "unselectedFg: Color(0xFFFFFFFF)" not in body


def test_circular_option_chip_long_label_scales_down_inside_circle() -> None:
    """Long numeric labels inside circular chips must scale down instead of overflowing."""
    from figma_flutter_agent.generator.layout.interactive import interactive_layout_helpers

    row = CleanDesignTreeNode(
        id="size:row",
        name="Sizes",
        type=NodeType.STACK,
        sizing=Sizing(width=216.0, height=48.0),
        children=[
            _circular_size_option_stack("chip:10", label='10"'),
            _circular_size_option_stack("chip:12", label='12"'),
            _circular_size_option_stack("chip:16", label='16"'),
        ],
    )
    helpers = interactive_layout_helpers(row)
    assert "FittedBox(" in helpers
    assert "BoxFit.scaleDown" in helpers


def test_circular_option_chip_row_preserves_section_label() -> None:
    """Section captions like ``Size:`` must survive circular chip row specialization."""
    row = CleanDesignTreeNode(
        id="size:row",
        name="Size",
        type=NodeType.STACK,
        sizing=Sizing(width=216.0, height=48.0),
        children=[
            CleanDesignTreeNode(
                id="size:label",
                name="Size:",
                type=NodeType.TEXT,
                text="Size:",
                sizing=Sizing(width=36.0, height=16.0),
                stack_placement=StackPlacement(top=16.0, width=36.0, height=16.0),
                style=NodeStyle(font_size=13.0, text_case="UPPER"),
            ),
            _circular_size_option_stack("chip:s", label="S"),
            _circular_size_option_stack("chip:m", label="M", selected=True),
            _circular_size_option_stack("chip:l", label="L"),
        ],
    )
    body = render_node_body(row, uses_svg=False)
    compact = body.replace("\n", "")
    assert "Size:" in compact
    assert "_GeneratedCircularOptionChipRow" in compact
    assert "Column(mainAxisSize: MainAxisSize.min" not in compact
    assert "Stack(clipBehavior: Clip.none" in compact
    assert "Positioned(left:" in compact


def test_circular_option_chip_row_section_label_flows_when_above_chip_band() -> None:
    """Non-overlapping captions emit as flow children, not positioned stack children."""
    row = CleanDesignTreeNode(
        id="size:row",
        name="Size",
        type=NodeType.STACK,
        sizing=Sizing(width=216.0, height=80.0),
        children=[
            CleanDesignTreeNode(
                id="size:label",
                name="Size:",
                type=NodeType.TEXT,
                text="Size:",
                sizing=Sizing(width=36.0, height=16.0),
                stack_placement=StackPlacement(top=0.0, width=36.0, height=16.0),
                style=NodeStyle(font_size=13.0, text_case="UPPER"),
            ),
            _circular_size_option_stack(
                "chip:s",
                label="S",
            ),
            _circular_size_option_stack("chip:m", label="M", selected=True),
            _circular_size_option_stack("chip:l", label="L"),
        ],
    )
    row.children[1].stack_placement = StackPlacement(left=0.0, top=24.0, width=48.0, height=48.0)
    row.children[2].stack_placement = StackPlacement(left=60.0, top=24.0, width=48.0, height=48.0)
    row.children[3].stack_placement = StackPlacement(left=120.0, top=24.0, width=48.0, height=48.0)
    body = render_node_body(row, uses_svg=False)
    compact = body.replace("\n", "")
    assert "Column(mainAxisSize: MainAxisSize.min" in compact
    assert "Size:" in compact
    assert "Positioned(" not in compact
