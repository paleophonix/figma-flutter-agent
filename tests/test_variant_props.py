"""Unit tests for Figma variant property mapping."""

from figma_flutter_agent.generator.variant_props import (
    button_on_pressed_expr,
    get_variant_property,
    input_decoration_expr,
    input_obscure_text_expr,
    render_material_button_widget,
    variant_blocks_interaction,
    variant_button_kind,
    variant_input_has_error,
    variant_is_checked,
    variant_is_loading,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, ComponentVariant, NodeType


def _node(**properties: str) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="1",
        name="Control",
        type=NodeType.BUTTON,
        variant=ComponentVariant(
            component_id="c1",
            variant_properties=properties,
            state=properties.get("State") or properties.get("state"),
        ),
    )


def test_get_variant_property_is_case_insensitive() -> None:
    node = _node(Size="Large", type="Primary")

    assert get_variant_property(node, "size") == "Large"
    assert get_variant_property(node, "TYPE") == "Primary"


def test_variant_button_kind_maps_type_aliases() -> None:
    assert variant_button_kind(_node(Type="Secondary")) == "outlined"
    assert variant_button_kind(_node(Style="Destructive")) == "destructive"
    assert variant_button_kind(_node(Variant="Ghost")) == "text"
    assert variant_button_kind(_node(Type="Primary")) == "elevated"


def test_variant_is_checked_reads_state_and_property() -> None:
    assert variant_is_checked(_node(State="On")) is True
    assert variant_is_checked(_node(Checked="true")) is True
    assert variant_is_checked(_node(State="Off")) is False


def test_loading_state_blocks_button_press() -> None:
    node = _node(State="Loading")

    assert variant_is_loading(node) is True
    assert variant_blocks_interaction(node) is True
    assert button_on_pressed_expr(node) == "null"


def test_render_material_button_secondary_is_outlined() -> None:
    node = _node(Type="Secondary", Size="Small")
    widget = render_material_button_widget(
        label="Save",
        on_pressed="() {}",
        background_color="AppColors.primary",
        node=node,
    )

    assert "OutlinedButton(" in widget
    assert "AppSpacing.sm" in widget


def test_input_password_and_error_variants() -> None:
    password = CleanDesignTreeNode(
        id="2",
        name="Password",
        type=NodeType.INPUT,
        variant=ComponentVariant(
            component_id="c2",
            variant_properties={"Type": "Password"},
        ),
    )
    error = CleanDesignTreeNode(
        id="3",
        name="Email",
        type=NodeType.INPUT,
        variant=ComponentVariant(
            component_id="c3",
            variant_properties={"State": "Error"},
            state="Error",
        ),
    )

    assert input_obscure_text_expr(password) == "true"
    assert variant_input_has_error(error) is True
    assert "errorText:" in input_decoration_expr(error, label="Email")
    assert "obscureText: false" not in input_obscure_text_expr(error)
