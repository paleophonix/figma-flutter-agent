"""Checkout-class emit laws (radio glyph, step indicator, SVG gate, helper text)."""

from __future__ import annotations

from figma_flutter_agent.assets.optimize import svg_is_well_formed
from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.generator.ir.expression import emit_extracted_ref
from figma_flutter_agent.generator.ir.extracted import (
    align_extracted_widgets_with_screen_ir,
    build_figma_id_to_widget_name,
    disambiguate_extracted_widget_name_collisions,
    remap_screen_ir_extracted_refs,
)
from figma_flutter_agent.generator.ir.fidelity.styled_emit import emit_styled_primitive
from figma_flutter_agent.generator.layout import render_node_body
from figma_flutter_agent.generator.layout.form import render_radio
from figma_flutter_agent.generator.layout.widgets.svg import _is_skip_control_stack
from figma_flutter_agent.parser.interaction.forms import text_is_payment_option_secondary
from figma_flutter_agent.parser.interaction.selection import (
    layout_fact_compact_radio_glyph,
    radio_external_semantic_label,
)
from figma_flutter_agent.parser.interaction.step import (
    layout_fact_step_indicator_completed,
    layout_fact_step_indicator_glyph_stack,
    layout_fact_step_indicator_title_column,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    ComponentVariant,
    ExtractedWidget,
    NodeStyle,
    NodeType,
    ScreenIr,
    Sizing,
    WidgetIrKind,
    WidgetIrNode,
    WidgetIrRef,
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


def test_compact_radio_glyph_in_bounded_card_slot_emits_radio_not_list_tile() -> None:
    """Law: figma_radio_with_external_label_must_emit_glyph_not_listtile."""
    radio = CleanDesignTreeNode(
        id="radio",
        name="Radio Button",
        type=NodeType.RADIO,
        sizing=Sizing(width=16.0, height=16.0),
        accessibility_label="Radio Button",
        variant=ComponentVariant(component_id="r1", variant_properties={"State": "Selected"}),
    )
    card = CleanDesignTreeNode(
        id="card",
        name="Credit card",
        type=NodeType.CARD,
        children=[radio],
    )
    assert layout_fact_compact_radio_glyph(radio, card)
    emitted = render_radio(radio, theme_variant="material_3", parent_node=card)
    assert "Radio<String>" in emitted
    assert "RadioListTile" not in emitted
    assert "Credit Card" not in emitted or "Semantics(label: 'Radio Button'" in emitted


def test_radio_external_semantic_label_prefers_row_sibling() -> None:
    label = CleanDesignTreeNode(
        id="label",
        name="Apple Pay",
        type=NodeType.TEXT,
        text="Apple Pay",
    )
    radio = CleanDesignTreeNode(
        id="radio",
        name="Radio Button",
        type=NodeType.RADIO,
        sizing=Sizing(width=16.0, height=16.0),
        accessibility_label="Radio Button",
    )
    row = CleanDesignTreeNode(
        id="row",
        name="Row",
        type=NodeType.ROW,
        children=[radio, label],
    )
    assert radio_external_semantic_label(radio, row) == "Apple Pay"
    emitted = render_radio(radio, theme_variant="material_3", parent_node=row)
    assert "Semantics(label: 'Apple Pay'" in emitted


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


def test_raster_asset_must_emit_image_not_svgpicture() -> None:
    """Law: raster_asset_must_emit_image_asset_not_svgpicture."""
    from figma_flutter_agent.generator.dart.syntax_repairs import (
        replace_raster_svgpicture_asset_calls,
    )

    broken = (
        "SvgPicture.asset('assets/images/ellipse_foo.png', "
        "width: 24.0, height: 24.0, fit: BoxFit.contain)"
    )
    fixed = replace_raster_svgpicture_asset_calls(broken)
    assert "Image.asset('assets/images/ellipse_foo.png'" in fixed
    assert "SvgPicture" not in fixed


def test_compact_trailing_selection_glyph_emits_check_not_ink() -> None:
    """Law: list_item_trailing_check_not_button_ink."""
    from figma_flutter_agent.generator.layout.widgets.selection import (
        render_compact_trailing_selection_glyph,
    )
    from figma_flutter_agent.parser.interaction.selection import (
        layout_fact_compact_trailing_selection_glyph,
    )

    glyph = CleanDesignTreeNode(
        id="shape",
        name="Shape",
        type=NodeType.VECTOR,
        image_asset_key="assets/images/shape.png",
        sizing=Sizing(width=12.0, height=8.5),
        style=NodeStyle(background_color="0xFF006FFD"),
    )
    button = CleanDesignTreeNode(
        id="trail",
        name="Right Button",
        type=NodeType.BUTTON,
        sizing=Sizing(width=12.0, height=12.0),
        children=[glyph],
        variant=ComponentVariant(component_id="8:477", component_name="Right Button"),
    )
    assert layout_fact_compact_trailing_selection_glyph(button)
    emitted = render_compact_trailing_selection_glyph(button, selected=True)
    assert "Icons.check" in emitted
    assert "Ink(" not in emitted
    assert "InkWell(" not in emitted


def test_step_indicator_title_column_skips_fixed_height_pin() -> None:
    """Law: component_host_height_fits_intrinsic_content."""
    from figma_flutter_agent.generator.layout.flex_policy.alignment import (
        _flex_child_should_bind_fixed_height,
    )

    title = CleanDesignTreeNode(
        id="title",
        name="Your bag",
        type=NodeType.TEXT,
        text="Your bag",
        sizing=Sizing(width=53.0, height=15.0),
    )
    glyph = CleanDesignTreeNode(
        id="glyph",
        name="Step",
        type=NodeType.STACK,
        sizing=Sizing(width=24.0, height=24.0),
        children=[
            CleanDesignTreeNode(
                id="bg",
                name="Background",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/bg.svg",
                sizing=Sizing(width=24.0, height=24.0),
            ),
        ],
    )
    column = CleanDesignTreeNode(
        id="step-col",
        name="Step",
        type=NodeType.COLUMN,
        spacing=12.0,
        sizing=Sizing(width=89.8, height=67.0),
        padding={"top": 8.0, "bottom": 8.0, "left": 8.0, "right": 8.0},
        children=[glyph, title],
    )
    assert not _flex_child_should_bind_fixed_height(column)


def test_active_step_numeral_centered_in_glyph_stack() -> None:
    """Law: step_circle_number_centered."""
    numeral = CleanDesignTreeNode(
        id="num",
        name="3",
        type=NodeType.TEXT,
        text="3",
        sizing=Sizing(width=8.0, height=12.0),
        stack_placement=None,
    )
    numeral.stack_placement = None
    from figma_flutter_agent.schemas import StackPlacement

    numeral = numeral.model_copy(
        update={
            "stack_placement": StackPlacement(
                left=0.0,
                top=6.0,
                width=24.0,
                height=12.0,
            )
        }
    )
    step = CleanDesignTreeNode(
        id="step",
        name="Step",
        type=NodeType.STACK,
        sizing=Sizing(width=24.0, height=24.0),
        variant=ComponentVariant(
            component_id="s1",
            variant_properties={"State": "Active"},
            state="Active",
        ),
        children=[
            CleanDesignTreeNode(
                id="bg",
                name="Background",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/bg.svg",
                sizing=Sizing(width=24.0, height=24.0),
            ),
            numeral,
        ],
    )
    emitted = render_node_body(
        numeral,
        uses_svg=True,
        parent_type=NodeType.STACK,
        parent_node=step,
    )
    assert "top: 0.0" in emitted
    assert "bottom: 0.0" in emitted
    assert "height:" not in emitted
    assert "top: 6.0" not in emitted
    assert "Center(child:" in emitted


def test_sanitize_positioned_axis_fields_drops_height_when_top_bottom() -> None:
    """Law: positioned_emits_at_most_two_per_axis."""
    from figma_flutter_agent.generator.layout.widgets.positioned import (
        sanitize_positioned_axis_fields,
    )

    fields = sanitize_positioned_axis_fields(
        [
            "left: 0.0",
            "right: 0.0",
            "height: 16.5",
            "top: 0.0",
            "bottom: 0.0",
        ]
    )
    assert "height: 16.5" not in fields
    assert "top: 0.0" in fields
    assert "bottom: 0.0" in fields
    assert sum(1 for field in fields if field.startswith(("top:", "bottom:", "height:"))) == 2


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


def test_align_extracted_widgets_with_screen_ir_creates_missing_roots() -> None:
    clean = CleanDesignTreeNode(
        id="root",
        name="Root",
        type=NodeType.COLUMN,
        children=[
            CleanDesignTreeNode(id="step:1", name="Step 1", type=NodeType.COLUMN),
            CleanDesignTreeNode(id="step:2", name="Step 2", type=NodeType.COLUMN),
        ],
    )
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id="root",
            kind=WidgetIrKind.COLUMN,
            children=[
                WidgetIrNode(
                    figma_id="step:1",
                    kind=WidgetIrKind.EXTRACTED,
                    ref=WidgetIrRef(widget_name="Step1Widget"),
                ),
                WidgetIrNode(
                    figma_id="step:2",
                    kind=WidgetIrKind.EXTRACTED,
                    ref=WidgetIrRef(widget_name="Step1Widget"),
                ),
            ],
        )
    )
    widgets = [
        ExtractedWidget(
            widget_name="Step1Widget",
            widget_ir=WidgetIrNode(figma_id="step:1", kind=WidgetIrKind.STACK),
        )
    ]
    aligned = align_extracted_widgets_with_screen_ir(screen_ir, widgets, clean)
    figma_map = build_figma_id_to_widget_name(
        disambiguate_extracted_widget_name_collisions(aligned)
    )
    remapped = remap_screen_ir_extracted_refs(screen_ir, figma_id_to_widget_name=figma_map)
    step_refs = [
        child.ref.widget_name
        for child in remapped.root.children
        if child.ref is not None
    ]
    assert set(figma_map.values()) == {"Step1Widget", "Step2Widget"}
    assert set(step_refs) == {"Step1Widget", "Step2Widget"}
    assert emit_extracted_ref(
        remapped.root.children[1],
        figma_id_to_widget_name=figma_map,
    ) == "Step2Widget()"


def test_step_indicator_title_column_uses_single_line_centered_label() -> None:
    title = CleanDesignTreeNode(
        id="title",
        name="Shipping",
        type=NodeType.TEXT,
        text="Shipping",
        sizing=Sizing(width=53.0, height=15.0),
    )
    glyph = CleanDesignTreeNode(
        id="glyph",
        name="Step",
        type=NodeType.STACK,
        sizing=Sizing(width=24.0, height=24.0),
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
        ],
    )
    column = CleanDesignTreeNode(
        id="step-col",
        name="Step",
        type=NodeType.COLUMN,
        children=[glyph, title],
    )
    assert layout_fact_step_indicator_title_column(column)
    emitted = render_node_body(
        title,
        uses_svg=True,
        parent_type=NodeType.COLUMN,
        parent_node=column,
    )
    assert "textAlign: TextAlign.center" in emitted
    assert "clip_single_line" in emitted or "softWrap: false" in emitted
