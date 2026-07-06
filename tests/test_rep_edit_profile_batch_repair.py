"""Regression tests for rep_edit_profile batch repair mechanisms."""

from __future__ import annotations

from figma_flutter_agent.generator.layout import render_node_body
from figma_flutter_agent.generator.layout.flex_policy.row import _column_child_keeps_intrinsic_width
from figma_flutter_agent.generator.layout.flex_policy.wrap import apply_flex_wrap_to_widget
from figma_flutter_agent.generator.layout.spacer import dimensioned_spacer_widget_expr
from figma_flutter_agent.generator.layout.widgets.flex_sizing import (
    _button_painted_surface_overlay_body,
)
from figma_flutter_agent.generator.variant.controls import render_slider_widget
from figma_flutter_agent.generator.variant.slider_facts import layout_fact_dual_thumb_range_slider
from figma_flutter_agent.parser.interaction.buttons import (
    button_has_painted_surface_overlay_label,
    button_painted_overlay_surface,
)
from figma_flutter_agent.parser.interaction.forms import layout_fact_composite_dropdown_host
from figma_flutter_agent.parser.interaction.input_fields import input_hint_text
from figma_flutter_agent.parser.semantics.arbiter import arbitrate
from figma_flutter_agent.parser.semantics.detectors.inputs import INPUT_DETECTORS
from figma_flutter_agent.parser.semantics.models import (
    Classification,
    DetectorContext,
    SignalTier,
    TierSignals,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    ScreenIr,
    Sizing,
    SizingMode,
    WidgetIrKind,
    WidgetIrNode,
)


def _ctx(node: CleanDesignTreeNode) -> DetectorContext:
    ir = WidgetIrNode(figma_id=node.id)
    return DetectorContext(
        clean_node=node,
        ir_node=ir,
        clean_by_id={node.id: node},
        screen_ir=ScreenIr(root=ir),
        signals=TierSignals(),
        confidence_threshold=0.8,
        grey_zone_min=0.5,
    )


def _dual_thumb_range_node() -> CleanDesignTreeNode:
    left = CleanDesignTreeNode(
        id="t1",
        name="Left-Thumb",
        type=NodeType.STACK,
        sizing=Sizing(width=24.0, height=24.0),
    )
    right = CleanDesignTreeNode(
        id="t2",
        name="Right-Thumb",
        type=NodeType.STACK,
        sizing=Sizing(width=24.0, height=24.0),
    )
    inner = CleanDesignTreeNode(
        id="inner",
        name="Range",
        type=NodeType.SLIDER,
        sizing=Sizing(width=103.0, height=8.0),
        children=[left, right],
    )
    return CleanDesignTreeNode(
        id="host",
        name="Slider / Range",
        type=NodeType.SLIDER,
        sizing=Sizing(width=345.0, height=8.0),
        children=[inner],
    )


def test_dual_thumb_range_slider_emits_range_slider() -> None:
    node = _dual_thumb_range_node()
    assert layout_fact_dual_thumb_range_slider(node)
    emitted = render_slider_widget(label="Slider / Range", node=node, theme_variant="material_3")
    assert "RangeSlider(" in emitted
    assert "Slider(value:" not in emitted
    assert "Text('Slider / Range')" not in emitted
    assert "height: 48.0" in emitted


def test_input_with_trailing_chevron_classifies_as_dropdown() -> None:
    chevron = CleanDesignTreeNode(
        id="chev",
        name="chevron",
        type=NodeType.BUTTON,
        sizing=Sizing(width=24.0, height=24.0),
        children=[
            CleanDesignTreeNode(
                id="v",
                name="vector",
                type=NodeType.VECTOR,
                sizing=Sizing(width=12.0, height=8.0),
                vector_asset_key="keyboard_arrow_down.svg",
            )
        ],
    )
    host = CleanDesignTreeNode(
        id="select",
        name="master input",
        type=NodeType.INPUT,
        sizing=Sizing(width=345.0, height=48.0),
        children=[
            CleanDesignTreeNode(
                id="surface",
                name="surface",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=345.0, height=48.0),
                style={"backgroundColor": "0xFFFFFFFF"},
                children=[],
            ),
            chevron,
        ],
    )
    ctx = _ctx(host)
    dropdown = next(det for det in INPUT_DETECTORS if det.kind == WidgetIrKind.INPUT_DROPDOWN)
    text_field = next(det for det in INPUT_DETECTORS if det.kind == WidgetIrKind.INPUT_TEXT_FIELD)
    assert dropdown.detect(ctx) is not None
    assert text_field.detect(ctx) is None


def test_input_with_trailing_stack_vector_classifies_as_dropdown() -> None:
    """Trailing chevron vectors inside a compact STACK must route to dropdown."""
    chevron_stack = CleanDesignTreeNode(
        id="chev-stack",
        name="icon",
        type=NodeType.STACK,
        sizing=Sizing(width=24.0, height=24.0),
        children=[
            CleanDesignTreeNode(
                id="chev-vector",
                name="Vector",
                type=NodeType.VECTOR,
                sizing=Sizing(width=12.0, height=8.0),
                style=NodeStyle(has_stroke=True),
            )
        ],
    )
    host = CleanDesignTreeNode(
        id="select",
        name="master input",
        type=NodeType.INPUT,
        component_ref="8:2230",
        sizing=Sizing(width=345.0, height=48.0),
        children=[
            CleanDesignTreeNode(
                id="value-row",
                name="atom input",
                type=NodeType.ROW,
                sizing=Sizing(width=300.0, height=48.0),
                children=[
                    CleanDesignTreeNode(
                        id="value",
                        name="label",
                        type=NodeType.TEXT,
                        text="Choose your countries",
                    ),
                    chevron_stack,
                ],
            ),
        ],
    )
    ctx = _ctx(host)
    dropdown = next(det for det in INPUT_DETECTORS if det.kind == WidgetIrKind.INPUT_DROPDOWN)
    text_field = next(det for det in INPUT_DETECTORS if det.kind == WidgetIrKind.INPUT_TEXT_FIELD)
    assert dropdown.detect(ctx) is not None
    assert text_field.detect(ctx) is None


def test_button_row_surface_is_painted_overlay() -> None:
    button = CleanDesignTreeNode(
        id="btn",
        name="Save",
        type=NodeType.BUTTON,
        sizing=Sizing(width=345.0, height=50.0),
        style=NodeStyle(border_radius=25.0),
        children=[
            CleanDesignTreeNode(
                id="surface",
                name="surface",
                type=NodeType.ROW,
                sizing=Sizing(width=350.0, height=50.0),
                style=NodeStyle(background_color="0xFFFFFFFF", border_radius=12.0),
                children=[
                    CleanDesignTreeNode(
                        id="inner",
                        name="inner",
                        type=NodeType.ROW,
                        children=[
                            CleanDesignTreeNode(
                                id="label",
                                name="label",
                                type=NodeType.TEXT,
                                text="Save",
                            )
                        ],
                    )
                ],
            )
        ],
    )
    surface = button_painted_overlay_surface(button)
    assert surface is not None
    assert surface.type == NodeType.ROW
    assert button_has_painted_surface_overlay_label(button)
    stack_body = _button_painted_surface_overlay_body(
        button,
        ["const SaveButtonContentWidget()"],
    )
    assert stack_body == "Center(child: const SaveButtonContentWidget())"


def test_composite_dropdown_host_emits_without_dropdown_button() -> None:
    host = CleanDesignTreeNode(
        id="composite",
        name="Select interval",
        type=NodeType.DROPDOWN,
        sizing=Sizing(width=345.0, height=80.0),
        children=[
            CleanDesignTreeNode(
                id="label-row",
                name="label",
                type=NodeType.ROW,
                children=[
                    CleanDesignTreeNode(
                        id="label",
                        name="label",
                        type=NodeType.TEXT,
                        text="Commission",
                    )
                ],
            ),
            CleanDesignTreeNode(
                id="inputs",
                name="inputs",
                type=NodeType.ROW,
                children=[
                    CleanDesignTreeNode(
                        id="a",
                        name="a",
                        type=NodeType.INPUT,
                        sizing=Sizing(width=100.0, height=24.0),
                    ),
                    CleanDesignTreeNode(
                        id="b",
                        name="b",
                        type=NodeType.INPUT,
                        sizing=Sizing(width=100.0, height=24.0),
                    ),
                ],
            ),
        ],
    )
    assert layout_fact_composite_dropdown_host(host)
    emitted = render_node_body(host, uses_svg=False, parent_type=NodeType.COLUMN)
    assert "DropdownButton" not in emitted


def test_composite_dropdown_veto_rejects_multi_input_host() -> None:
    host = CleanDesignTreeNode(
        id="composite",
        name="Select interval",
        type=NodeType.DROPDOWN,
        sizing=Sizing(width=345.0, height=80.0),
        children=[
            CleanDesignTreeNode(id="a", name="a", type=NodeType.INPUT, sizing=Sizing(width=100.0, height=24.0)),
            CleanDesignTreeNode(id="b", name="b", type=NodeType.INPUT, sizing=Sizing(width=100.0, height=24.0)),
        ],
    )
    ctx = _ctx(host)
    outcome = arbitrate(
        [
            Classification(
                kind=WidgetIrKind.INPUT_DROPDOWN,
                confidence=0.9,
                winning_tier=SignalTier.ANATOMY,
            )
        ],
        ctx,
    )
    assert outcome.kind is None
    assert outcome.reject_reason == "composite_dropdown_veto"


def test_component_instance_does_not_leak_master_placeholder_hint() -> None:
    node = CleanDesignTreeNode(
        id="inst",
        name="master input",
        type=NodeType.INPUT,
        component_ref="8:2230",
        sizing=Sizing(width=345.0, height=48.0),
    )
    assert input_hint_text(node) == ""


def test_dimensioned_spacer_leaf_emits_finite_box() -> None:
    node = CleanDesignTreeNode(
        id="gap",
        name="padding",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=345.0, height=16.0),
    )
    assert dimensioned_spacer_widget_expr(node) == "SizedBox(width: 345.0, height: 16.0)"


def test_column_stretch_wraps_hug_child_with_align() -> None:
    parent = CleanDesignTreeNode(
        id="col",
        name="form",
        type=NodeType.COLUMN,
        sizing=Sizing(width=345.0, height=400.0, width_mode=SizingMode.FILL),
    )
    chip = CleanDesignTreeNode(
        id="chip",
        name="chip",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=89.0, height=20.0, width_mode=SizingMode.FIXED),
    )
    assert _column_child_keeps_intrinsic_width(chip, parent)
    wrapped = apply_flex_wrap_to_widget(
        "Container(width: 89.0)",
        parent_type=NodeType.COLUMN,
        node=chip,
        parent_node=parent,
    )
    assert wrapped.startswith("Align(alignment: Alignment.centerLeft")
