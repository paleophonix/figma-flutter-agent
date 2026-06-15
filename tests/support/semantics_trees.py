"""Synthetic clean-tree builders for semantics corpus tests."""

from __future__ import annotations

from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    SizingMode,
)


def _text_node(node_id: str, label: str) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=f"{node_id}-text",
        name="label",
        type=NodeType.TEXT,
        text=label,
    )


def weekday_chip_stack(node_id: str, label: str) -> CleanDesignTreeNode:
    """Compact circular weekday chip (single-letter label)."""
    return CleanDesignTreeNode(
        id=node_id,
        name="chip",
        type=NodeType.STACK,
        sizing=Sizing(
            width=40.0, height=40.0, width_mode=SizingMode.FIXED, height_mode=SizingMode.FIXED
        ),
        style=NodeStyle(background_color="0xFFE0E0E0"),
        children=[_text_node(node_id, label)],
    )


def weekday_chip_row(node_id: str = "chip-row") -> CleanDesignTreeNode:
    """Row of weekday chips (positive CHIP_CHOICE parent target)."""
    return CleanDesignTreeNode(
        id=node_id,
        name="chip_row",
        type=NodeType.ROW,
        sizing=Sizing(width=300.0, height=48.0),
        children=[
            weekday_chip_stack(f"{node_id}-m", "m"),
            weekday_chip_stack(f"{node_id}-t", "t"),
            weekday_chip_stack(f"{node_id}-w", "w"),
        ],
    )


def size_picker_row(node_id: str = "size-picker") -> CleanDesignTreeNode:
    """S/M/L button row trap (must not classify as chip_choice)."""
    buttons = []
    for label in ("S", "M", "L"):
        buttons.append(
            CleanDesignTreeNode(
                id=f"{node_id}-{label.lower()}",
                name="size",
                type=NodeType.BUTTON,
                sizing=Sizing(width=48.0, height=40.0),
                style=NodeStyle(border_color="0xFF000000"),
                children=[_text_node(f"{node_id}-{label.lower()}", label)],
            )
        )
    return CleanDesignTreeNode(
        id=node_id,
        name="picker",
        type=NodeType.ROW,
        sizing=Sizing(width=200.0, height=48.0),
        children=buttons,
    )


def filled_button(node_id: str = "btn-filled", *, label: str = "Go") -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name="button",
        type=NodeType.BUTTON,
        sizing=Sizing(width=120.0, height=44.0),
        style=NodeStyle(background_color="0xFF6200EE"),
        children=[_text_node(node_id, label)],
    )


def input_field(node_id: str = "input-1") -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name="field",
        type=NodeType.INPUT,
        sizing=Sizing(width=280.0, height=48.0),
        style=NodeStyle(border_color="0xFFCCCCCC"),
        children=[_text_node(node_id, "Placeholder")],
    )


def dialog_overlay(node_id: str = "dialog-1") -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name="dialog",
        type=NodeType.DIALOG,
        sizing=Sizing(width=320.0, height=240.0),
        style=NodeStyle(background_color="0xFFFFFFFF"),
        children=[_text_node(node_id, "Confirm")],
    )


def decorative_card_trap(node_id: str = "card-trap") -> CleanDesignTreeNode:
    """Decorative scrim overlay trap (must not classify as container_card)."""
    return CleanDesignTreeNode(
        id=node_id,
        name="overlay_scrim",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=320.0, height=180.0),
        style=NodeStyle(opacity=0.25),
        children=[],
    )


def avatar_square(node_id: str = "avatar-1") -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name="avatar",
        type=NodeType.IMAGE,
        sizing=Sizing(width=48.0, height=48.0),
        image_asset_key="avatar.png",
    )


def decorative_pill_trap(node_id: str = "pill-trap") -> CleanDesignTreeNode:
    """Rounded badge trap (must not classify as button_*)."""
    return CleanDesignTreeNode(
        id=node_id,
        name="badge",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=80.0, height=28.0),
        style=NodeStyle(background_color="0xFFE0E0E0", border_radius=14.0),
        children=[_text_node(node_id, "NEW")],
    )


def input_decor_trap(node_id: str = "input-decor") -> CleanDesignTreeNode:
    """Static chrome row trap (must not classify as input_text_field)."""
    return CleanDesignTreeNode(
        id=node_id,
        name="field_hint",
        type=NodeType.ROW,
        sizing=Sizing(width=280.0, height=48.0),
        style=NodeStyle(border_color="0xFFCCCCCC"),
        children=[
            CleanDesignTreeNode(
                id=f"{node_id}-icon",
                name="icon",
                type=NodeType.VECTOR,
                sizing=Sizing(width=20.0, height=20.0),
            ),
            _text_node(node_id, "Search..."),
        ],
    )


def outlined_button(node_id: str = "btn-outlined", *, label: str = "Cancel") -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name="button",
        type=NodeType.BUTTON,
        sizing=Sizing(width=120.0, height=44.0),
        style=NodeStyle(border_color="0xFF6200EE"),
        children=[_text_node(node_id, label)],
    )


def text_button(node_id: str = "btn-text", *, label: str = "Skip") -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name="button",
        type=NodeType.BUTTON,
        sizing=Sizing(width=80.0, height=36.0),
        children=[_text_node(node_id, label)],
    )


def container_card(node_id: str = "card-1") -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name="card",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=320.0, height=180.0),
        style=NodeStyle(background_color="0xFFFFFFFF", border_color="0xFFE0E0E0"),
        children=[_text_node(node_id, "Card title")],
    )


def list_tile_row(node_id: str = "tile-1") -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name="list_tile",
        type=NodeType.ROW,
        sizing=Sizing(width=320.0, height=56.0),
        children=[
            CleanDesignTreeNode(
                id=f"{node_id}-icon",
                name="lead",
                type=NodeType.VECTOR,
                sizing=Sizing(width=40.0, height=40.0),
            ),
            _text_node(node_id, "List item"),
        ],
    )


def technical_divider(node_id: str = "divider-1") -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name="divider",
        type=NodeType.CONTAINER,
        sizing=Sizing(
            width=280.0, height=2.0, width_mode=SizingMode.FIXED, height_mode=SizingMode.FIXED
        ),
        style=NodeStyle(background_color="0xFFE0E0E0"),
        children=[],
    )


def thin_rect_not_divider_trap(node_id: str = "thin-rect-trap") -> CleanDesignTreeNode:
    """Tall thin container trap (must not classify as technical_divider)."""
    return CleanDesignTreeNode(
        id=node_id,
        name="stripe",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=8.0, height=120.0),
        style=NodeStyle(background_color="0xFFCCCCCC"),
        children=[],
    )


def plain_row_not_list_tile_trap(node_id: str = "row-trap") -> CleanDesignTreeNode:
    """Text-only row trap (must not classify as container_list_tile)."""
    return CleanDesignTreeNode(
        id=node_id,
        name="labels",
        type=NodeType.ROW,
        sizing=Sizing(width=200.0, height=40.0),
        children=[
            _text_node(f"{node_id}-a", "Left"),
            _text_node(f"{node_id}-b", "Right"),
        ],
    )


def text_label_not_button_trap(node_id: str = "label-trap") -> CleanDesignTreeNode:
    """Static text row trap (must not classify as button_text)."""
    return CleanDesignTreeNode(
        id=node_id,
        name="caption",
        type=NodeType.TEXT,
        sizing=Sizing(width=120.0, height=20.0),
        text="Learn more",
    )


def bordered_box_not_button_trap(node_id: str = "border-trap") -> CleanDesignTreeNode:
    """Decorative bordered container trap (must not classify as button_outlined)."""
    return CleanDesignTreeNode(
        id=node_id,
        name="frame",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=160.0, height=80.0),
        style=NodeStyle(border_color="0xFF999999"),
        children=[_text_node(node_id, "Info")],
    )


def compact_chip_stack(node_id: str, label: str) -> CleanDesignTreeNode:
    """Structural compact chip (no weekday lexicon)."""
    return weekday_chip_stack(node_id, label)


def compact_chip_row(node_id: str = "chip-row-alt") -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name="chip_row",
        type=NodeType.ROW,
        sizing=Sizing(width=300.0, height=48.0),
        children=[
            compact_chip_stack(f"{node_id}-a", "1"),
            compact_chip_stack(f"{node_id}-b", "2"),
            compact_chip_stack(f"{node_id}-c", "3"),
        ],
    )


def initial_letter_square_trap(node_id: str = "initial-trap") -> CleanDesignTreeNode:
    """Square glyph tile trap (must not classify as media_avatar)."""
    return CleanDesignTreeNode(
        id=node_id,
        name="tile",
        type=NodeType.STACK,
        sizing=Sizing(width=48.0, height=48.0),
        style=NodeStyle(background_color="0xFFEEEEEE"),
        children=[_text_node(node_id, "K")],
    )


def compact_vector_loader_trap(node_id: str = "compact-vector-trap") -> CleanDesignTreeNode:
    """Small vector icon trap (must not classify as feedback_loader without variant axis)."""
    return CleanDesignTreeNode(
        id=node_id,
        name="icon",
        type=NodeType.VECTOR,
        sizing=Sizing(
            width=24.0,
            height=24.0,
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FIXED,
        ),
        style=NodeStyle(has_stroke=True),
    )


def compact_stack_tooltip_trap(node_id: str = "compact-stack-trap") -> CleanDesignTreeNode:
    """Small stack icon trap (must not classify as feedback_tooltip without variant axis)."""
    return CleanDesignTreeNode(
        id=node_id,
        name="icon_stack",
        type=NodeType.STACK,
        sizing=Sizing(
            width=48.0,
            height=48.0,
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FIXED,
        ),
    )


def feedback_loader_variant(node_id: str = "loader-1") -> CleanDesignTreeNode:
    """Component-backed loader (positive feedback_loader classification)."""
    from figma_flutter_agent.schemas import ComponentVariant

    return CleanDesignTreeNode(
        id=node_id,
        name="Spinner",
        type=NodeType.VECTOR,
        sizing=Sizing(width=24.0, height=24.0),
        variant=ComponentVariant(
            component_id="spinner-1",
            component_name="Spinner",
            variant_properties={"Type": "Loader"},
        ),
    )


def feedback_tooltip_variant(node_id: str = "tooltip-1") -> CleanDesignTreeNode:
    """Component-backed tooltip host (positive feedback_tooltip classification)."""
    from figma_flutter_agent.schemas import ComponentVariant

    return CleanDesignTreeNode(
        id=node_id,
        name="Tooltip",
        type=NodeType.STACK,
        sizing=Sizing(width=48.0, height=48.0),
        variant=ComponentVariant(
            component_id="tooltip-1",
            component_name="Tooltip",
            variant_properties={"Role": "Tooltip"},
        ),
    )
