from figma_flutter_agent.parser.components import (
    extract_component_variant,
    infer_semantic_type_from_component,
    infer_semantic_type_from_component_properties,
    infer_semantic_type_from_figma_overlay,
    match_semantic_type_from_name,
    match_semantic_type_from_name_fallback,
    resolve_semantic_node_type,
)
from figma_flutter_agent.schemas import NodeType


def test_extract_component_variant_reads_properties() -> None:
    variant = extract_component_variant(
        {
            "type": "INSTANCE",
            "name": "Button/Default",
            "componentId": "comp-1",
            "componentProperties": {
                "State": {"value": "Hover", "type": "VARIANT"},
                "Size": {"value": "Large", "type": "VARIANT"},
            },
        },
        {
            "comp-1": {
                "name": "Button",
                "componentSetId": "set-1",
            }
        },
    )

    assert variant is not None
    assert variant.component_id == "comp-1"
    assert variant.component_set_id == "set-1"
    assert variant.component_name == "Button"
    assert variant.variant_properties["State"] == "Hover"
    assert variant.state == "Hover"


def test_extract_component_variant_returns_none_for_frame() -> None:
    assert extract_component_variant({"type": "FRAME", "name": "Card"}, {}) is None


def test_match_semantic_type_from_name_maps_buttons_and_inputs() -> None:
    assert match_semantic_type_from_name("Primary Button") == NodeType.BUTTON
    assert match_semantic_type_from_name("Email Input") == NodeType.INPUT
    assert match_semantic_type_from_name("Remember Checkbox") == NodeType.CHECKBOX
    assert match_semantic_type_from_name("Dark Mode Switch") == NodeType.SWITCH
    assert match_semantic_type_from_name("Profile Tabs") == NodeType.TABS
    assert match_semantic_type_from_name("Main Bottom Nav") == NodeType.BOTTOM_NAV
    assert match_semantic_type_from_name("Tablet Frame") is None
    assert match_semantic_type_from_name("Plan Radio") == NodeType.RADIO
    assert match_semantic_type_from_name("Billing Radio Group") == NodeType.RADIO_GROUP
    assert match_semantic_type_from_name("Country Dropdown") == NodeType.DROPDOWN
    assert match_semantic_type_from_name("Delete Dialog") == NodeType.DIALOG
    assert match_semantic_type_from_name("Volume Slider") == NodeType.SLIDER
    assert match_semantic_type_from_name("Hero Carousel") == NodeType.CAROUSEL


def test_name_modal_rejects_custom_overlay_sheet() -> None:
    node = {
        "type": "FRAME",
        "name": "Modal",
        "absoluteBoundingBox": {"width": 375, "height": 1213},
        "children": [
            {"type": "FRAME", "name": "Head", "absoluteBoundingBox": {"width": 375, "height": 52}},
            {"type": "FRAME", "name": "Body", "absoluteBoundingBox": {"width": 375, "height": 1100}},
        ],
    }
    assert match_semantic_type_from_name_fallback(node, "Modal") is None


def test_name_delete_dialog_keeps_compact_confirmation_dialog() -> None:
    node = {
        "type": "FRAME",
        "name": "Delete Dialog",
        "absoluteBoundingBox": {"width": 320, "height": 180},
        "children": [
            {"type": "TEXT", "name": "Message", "characters": "Are you sure?"},
        ],
    }
    assert match_semantic_type_from_name_fallback(node, "Delete Dialog") == NodeType.DIALOG


def test_name_card_rejects_horizontal_product_row_frame() -> None:
    node = {
        "type": "FRAME",
        "name": "Card",
        "layoutMode": "HORIZONTAL",
        "absoluteBoundingBox": {"width": 347, "height": 76},
        "children": [
            {"type": "RECTANGLE", "name": "Img", "absoluteBoundingBox": {"width": 76, "height": 76}},
            {"type": "FRAME", "name": "Body", "absoluteBoundingBox": {"width": 259, "height": 72}},
        ],
    }
    assert match_semantic_type_from_name_fallback(node, "Card") is None


def test_infer_semantic_type_from_component_rejects_compact_credit_card_glyph() -> None:
    """Published component names with a card token must not type compact icon glyphs as CARD."""
    node = {
        "type": "INSTANCE",
        "name": "Icon / Category / icons/credit-card-in 1",
        "componentId": "comp-credit",
        "absoluteBoundingBox": {"width": 28, "height": 28},
        "children": [
            {
                "type": "FRAME",
                "name": "Group",
                "absoluteBoundingBox": {"width": 28, "height": 28},
                "children": [
                    {
                        "type": "VECTOR",
                        "name": "Vector",
                        "absoluteBoundingBox": {"width": 10, "height": 23},
                    },
                ],
            },
        ],
    }
    node_type = infer_semantic_type_from_component(
        node,
        {
            "comp-credit": {
                "name": "Icon / Category / icons/credit-card-in 1",
            }
        },
    )

    assert node_type is None


def test_infer_semantic_type_from_component_set_name() -> None:
    node_type = infer_semantic_type_from_component(
        {"type": "INSTANCE", "name": "Default", "componentId": "comp-1"},
        {"comp-1": {"name": "Default", "componentSetId": "set-1"}},
        {"set-1": {"name": "Button/Primary"}},
    )

    assert node_type == NodeType.BUTTON


def test_infer_semantic_type_from_component_set_without_name_hint_on_instance() -> None:
    """Component set name drives type when instance layer name is generic."""
    node_type = infer_semantic_type_from_component(
        {"type": "INSTANCE", "name": "State=Default", "componentId": "comp-1"},
        {"comp-1": {"name": "Default", "componentSetId": "set-1"}},
        {"set-1": {"name": "Input Field"}},
    )

    assert node_type == NodeType.INPUT


def test_infer_semantic_type_from_component_uses_published_name() -> None:
    node_type = infer_semantic_type_from_component(
        {"type": "INSTANCE", "name": "Submit", "componentId": "comp-1"},
        {"comp-1": {"name": "Button/Primary"}},
    )

    assert node_type == NodeType.BUTTON


def test_resolve_semantic_type_skips_layer_name_when_components_api_present() -> None:
    """Instance layer name must not override published component metadata."""
    node_type = resolve_semantic_node_type(
        {"type": "INSTANCE", "name": "Primary Button", "componentId": "comp-1"},
        {"comp-1": {"name": "Glyph/24", "componentSetId": "set-1"}},
        {"set-1": {"name": "Avatar"}},
    )

    assert node_type is None


def test_infer_semantic_type_from_component_properties_type_axis() -> None:
    node_type = infer_semantic_type_from_component_properties(
        {
            "type": "INSTANCE",
            "componentId": "comp-1",
            "componentProperties": {
                "Type": {"value": "Button", "type": "VARIANT"},
            },
        }
    )

    assert node_type == NodeType.BUTTON


def test_infer_semantic_type_from_figma_overlay_fields() -> None:
    node_type = infer_semantic_type_from_figma_overlay(
        {
            "type": "FRAME",
            "name": "Confirmation",
            "overlayPositionType": "CENTER",
            "overlayBackground": {"r": 0, "g": 0, "b": 0, "a": 0.4},
        }
    )

    assert node_type == NodeType.DIALOG


def test_name_fallback_rejects_decorative_card_gradient_vector() -> None:
    node_type = match_semantic_type_from_name_fallback(
        {
            "type": "VECTOR",
            "name": "card_gradient_blur",
            "absoluteBoundingBox": {"width": 120, "height": 80},
            "children": [],
        },
        "card_gradient_blur",
    )
    assert node_type is None


def test_name_fallback_requires_positive_bbox_for_buttons() -> None:
    node_type = match_semantic_type_from_name_fallback(
        {
            "type": "FRAME",
            "name": "Primary Button",
            "absoluteBoundingBox": {"width": 0, "height": 40},
        },
        "Primary Button",
    )
    assert node_type is None


def test_resolve_maps_instance_via_variant_property_without_button_in_name() -> None:
    node_type = resolve_semantic_node_type(
        {
            "type": "INSTANCE",
            "name": "State=Default",
            "componentId": "comp-1",
            "componentProperties": {
                "Type": {"value": "Button", "type": "VARIANT"},
            },
        },
        {"comp-1": {"name": "Default"}},
    )

    assert node_type == NodeType.BUTTON


def test_named_slider_component_without_track_anatomy_not_slider() -> None:
    """Law: slider_type_requires_structural_anatomy_not_name."""
    node = {
        "type": "INSTANCE",
        "name": "Content row slider",
        "componentId": "comp-slider-row",
        "absoluteBoundingBox": {"width": 390, "height": 296},
        "children": [
            {
                "type": "FRAME",
                "name": "scroll_frame",
                "layoutMode": "HORIZONTAL",
                "absoluteBoundingBox": {"width": 360, "height": 280},
                "children": [
                    {
                        "type": "INSTANCE",
                        "name": "Image Card",
                        "absoluteBoundingBox": {"width": 160, "height": 240},
                    },
                    {
                        "type": "INSTANCE",
                        "name": "Image Card",
                        "absoluteBoundingBox": {"width": 160, "height": 240},
                    },
                ],
            }
        ],
    }
    assert match_semantic_type_from_name("Content row slider") == NodeType.SLIDER
    assert match_semantic_type_from_name_fallback(node, "Content row slider") is None
    assert (
        resolve_semantic_node_type(node, {"comp-slider-row": {"name": "Content row slider"}})
        is None
    )
