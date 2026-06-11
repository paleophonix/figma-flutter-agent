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
        sizing=Sizing(width=40.0, height=40.0, width_mode=SizingMode.FIXED, height_mode=SizingMode.FIXED),
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


def filled_button(node_id: str = "btn-filled") -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name="button",
        type=NodeType.BUTTON,
        sizing=Sizing(width=120.0, height=44.0),
        style=NodeStyle(background_color="0xFF6200EE"),
        children=[_text_node(node_id, "Go")],
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
    """Card-like container trap (must not classify as overlay dialog)."""
    return CleanDesignTreeNode(
        id=node_id,
        name="card",
        type=NodeType.CARD,
        sizing=Sizing(width=320.0, height=180.0),
        style=NodeStyle(background_color="0xFFFFFFFF", border_color="0x22000000"),
        children=[_text_node(node_id, "Summary")],
    )


def avatar_square(node_id: str = "avatar-1") -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name="avatar",
        type=NodeType.IMAGE,
        sizing=Sizing(width=48.0, height=48.0),
        image_asset_key="avatar.png",
    )


def initial_letter_square_trap(node_id: str = "initial-trap") -> CleanDesignTreeNode:
    """Square with letter trap (must not classify as avatar without variant)."""
    return CleanDesignTreeNode(
        id=node_id,
        name="tile",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=48.0, height=48.0),
        style=NodeStyle(background_color="0xFFEEEEEE"),
        children=[_text_node(node_id, "K")],
    )
