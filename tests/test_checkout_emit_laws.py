"""Checkout-class emit laws (radio glyph, step indicator, SVG gate, helper text)."""

from __future__ import annotations

from figma_flutter_agent.assets.optimize import svg_is_well_formed
from figma_flutter_agent.generator.ir.extracted import disambiguate_extracted_widget_name_collisions
from figma_flutter_agent.generator.ir.fidelity.styled_emit import emit_styled_primitive
from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.generator.layout import render_node_body
from figma_flutter_agent.generator.layout.form import render_radio
from figma_flutter_agent.generator.layout.widgets.svg import _is_skip_control_stack
from figma_flutter_agent.parser.interaction.forms import text_is_payment_option_secondary
from figma_flutter_agent.parser.interaction.selection import layout_fact_compact_radio_glyph
from figma_flutter_agent.parser.interaction.step import (
    layout_fact_step_indicator_completed,
    layout_fact_step_indicator_glyph_stack,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    ComponentVariant,
    ExtractedWidget,
    NodeStyle,
    NodeType,
    Sizing,
    WidgetIrKind,
    WidgetIrNode,
)


def test_compact_radio_glyph_in_labeled_column_emits_radio_not_list_tile() -> None:
    """Law: compact_radio_in_labeled_column_emits_glyph_not_list_tile."""
    label = CleanDesignTreeNode(
        id="label",
        name="Credit Card",
        type=NodeType.TEXT,
        text="Credit Card",
    )
    radio = CleanDesignTreeNode(
        id="radio",
        name="Radio",
        type=NodeType.RADIO,
        variant=ComponentVariant(component_id="r1", variant_properties={"State": "Selected"}),
    )
    column = CleanDesignTreeNode(
        id="col",
        name="Column",
        type=NodeType.COLUMN,
        children=[radio, label],
    )
    assert layout_fact_compact_radio_glyph(radio, column)
    emitted = render_radio(radio, theme_variant="material_3", parent_node=column)
    assert "Radio<String>" in emitted
    assert "RadioListTile" not in emitted


def test_list_tile_styled_primitive_uses_material_not_decorated_box() -> None:
    """Law: list_tile_paints_on_material_not_shadowed_by_bg_decoratedbox."""
    clean = CleanDesignTreeNode(
        id="tile",
        name="Item",
        type=NodeType.ROW,
        text="Item",
        children=[],
    )
    ir = WidgetIrNode(figma_id="tile", kind=WidgetIrKind.CONTAINER_LIST_TILE)
    ctx = IrEmitContext(uses_svg=False, responsive_enabled=False, is_layout_root=False)
    emitted = emit_styled_primitive(ir, clean=clean, ctx=ctx)
    assert "Material(" in emitted
    assert "DecoratedBox(" not in emitted


def test_malformed_svg_fails_well_formed_gate() -> None:
    """Law: exported_svg_must_parse_under_vector_graphics_compiler (XML gate)."""
    assert svg_is_well_formed("<svg xmlns='http://www.w3.org/2000/svg'><rect/></svg>")
    assert not svg_is_well_formed("<svg><path d='M0 0 L1 1' unclosed")


def test_section_helper_text_without_payment_host_is_not_payment_subtitle() -> None:
    """Law: text_wraps_within_bounded_width — helper copy must not use payment subtitle clip."""
    helper = CleanDesignTreeNode(
        id="helper",
        name="Helper",
        type=NodeType.TEXT,
        text="You won't be charged until you review the order on the next page",
        style=NodeStyle(font_size=12.0, font_weight="w400", text_color="0xFF71727A"),
    )
    assert not text_is_payment_option_secondary(helper)


def test_step_indicator_stack_is_not_skip_control() -> None:
    """Law: step_indicator_completed_state_renders_check_centered_single_label."""
    step = CleanDesignTreeNode(
        id="step",
        name="Step",
        type=NodeType.STACK,
        sizing=Sizing(width=24.0, height=24.0),
        variant=ComponentVariant(component_id="s1", variant_properties={"State": "Done"}, state="Done"),
        children=[
            CleanDesignTreeNode(
                id="bg",
                name="Background",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/bg.svg",
                sizing=Sizing(width=24.0, height=24.0),
            ),
            CleanDesignTreeNode(
                id="num",
                name="1",
                type=NodeType.TEXT,
                text="1",
                sizing=Sizing(width=8.0, height=12.0),
            ),
            CleanDesignTreeNode(
                id="ok",
                name="Success",
                type=NodeType.STACK,
                sizing=Sizing(width=24.0, height=24.0),
            ),
        ],
    )
    assert layout_fact_step_indicator_glyph_stack(step)
    assert layout_fact_step_indicator_completed(step)
    assert not _is_skip_control_stack(step)


def test_completed_step_numeral_suppressed_in_emit() -> None:
    """Completed step stacks must not paint the step numeral over the success glyph."""
    numeral = CleanDesignTreeNode(
        id="num",
        name="1",
        type=NodeType.TEXT,
        text="1",
        sizing=Sizing(width=8.0, height=12.0),
        stack_placement=None,
    )
    step = CleanDesignTreeNode(
        id="step",
        name="Step",
        type=NodeType.STACK,
        sizing=Sizing(width=24.0, height=24.0),
        variant=ComponentVariant(component_id="s1", variant_properties={"State": "Done"}, state="Done"),
        children=[
            CleanDesignTreeNode(
                id="bg",
                name="Background",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/bg.svg",
                sizing=Sizing(width=24.0, height=24.0),
            ),
            numeral,
            CleanDesignTreeNode(id="ok", name="Success", type=NodeType.STACK, sizing=Sizing(width=24.0, height=24.0)),
        ],
    )
    emitted = render_node_body(numeral, uses_svg=True, parent_type=NodeType.STACK, parent_node=step)
    assert "SizedBox.shrink()" in emitted


def test_disambiguate_extracted_widget_name_collisions() -> None:
    """Extracted widgets with the same name but different figma roots must split."""
    widgets = [
        ExtractedWidget(
            widget_name="Step1Widget",
            widget_ir=WidgetIrNode(figma_id="a:1", kind=WidgetIrKind.STACK),
        ),
        ExtractedWidget(
            widget_name="Step1Widget",
            widget_ir=WidgetIrNode(figma_id="a:2", kind=WidgetIrKind.STACK),
        ),
    ]
    resolved = disambiguate_extracted_widget_name_collisions(widgets)
    names = {item.widget_name for item in resolved}
    assert names == {"Step1Widget", "Step2Widget"}
