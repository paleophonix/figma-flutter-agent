"""Plausible-kind pre-filter before running semantic detectors."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, WidgetIrKind

_LAYOUT_KINDS = frozenset(
    {
        WidgetIrKind.AUTO,
        WidgetIrKind.COLUMN,
        WidgetIrKind.ROW,
        WidgetIrKind.WRAP,
        WidgetIrKind.STACK,
        WidgetIrKind.TEXT,
        WidgetIrKind.IMAGE,
        WidgetIrKind.BUTTON,
        WidgetIrKind.INPUT,
        WidgetIrKind.CONTAINER,
        WidgetIrKind.EXTRACTED,
    }
)

SEMANTIC_IR_KINDS: frozenset[WidgetIrKind] = frozenset(
    kind for kind in WidgetIrKind if kind not in _LAYOUT_KINDS
)

_OVERLAY_KINDS = frozenset(
    {
        WidgetIrKind.OVERLAY_DIALOG,
        WidgetIrKind.OVERLAY_BOTTOM_SHEET,
        WidgetIrKind.OVERLAY_SNACKBAR,
        WidgetIrKind.OVERLAY_BANNER,
    }
)

_NODE_TYPE_CANDIDATES: dict[NodeType, frozenset[WidgetIrKind]] = {
    NodeType.INPUT: frozenset(
        {
            WidgetIrKind.INPUT_TEXT_FIELD,
            WidgetIrKind.INPUT_SEARCH_BAR,
        }
    ),
    NodeType.DROPDOWN: frozenset({WidgetIrKind.INPUT_DROPDOWN}),
    NodeType.SLIDER: frozenset({WidgetIrKind.INPUT_SLIDER}),
    NodeType.BUTTON: frozenset(
        {
            WidgetIrKind.BUTTON_FILLED,
            WidgetIrKind.BUTTON_OUTLINED,
            WidgetIrKind.BUTTON_TEXT,
            WidgetIrKind.BUTTON_FAB,
            WidgetIrKind.BUTTON_ICON,
            WidgetIrKind.CHIP_ACTION,
        }
    ),
    NodeType.CHECKBOX: frozenset({WidgetIrKind.CONTROL_CHECKBOX}),
    NodeType.SWITCH: frozenset({WidgetIrKind.CONTROL_SWITCH}),
    NodeType.RADIO: frozenset({WidgetIrKind.CONTROL_RADIO}),
    NodeType.RADIO_GROUP: frozenset({WidgetIrKind.CONTROL_RADIO}),
    NodeType.CARD: frozenset({WidgetIrKind.CONTAINER_CARD}),
    NodeType.GRID: frozenset({WidgetIrKind.CONTAINER_GRID}),
    NodeType.CAROUSEL: frozenset({WidgetIrKind.CONTAINER_CAROUSEL}),
    NodeType.BOTTOM_NAV: frozenset({WidgetIrKind.NAV_BOTTOM_BAR}),
    NodeType.TABS: frozenset(
        {
            WidgetIrKind.NAV_TAB_BAR,
            WidgetIrKind.CONTROL_SEGMENTED,
        }
    ),
    NodeType.DIALOG: frozenset({WidgetIrKind.OVERLAY_DIALOG}),
    NodeType.ROW: frozenset(
        {
            WidgetIrKind.CHIP_CHOICE,
            WidgetIrKind.CHIP_FILTER,
            WidgetIrKind.CHIP_INPUT,
            WidgetIrKind.CONTROL_SEGMENTED,
            WidgetIrKind.NAV_PAGINATION,
            WidgetIrKind.NAV_STEPPER,
            WidgetIrKind.INPUT_STEPPER,
            WidgetIrKind.INPUT_FILE_UPLOADER,
            WidgetIrKind.INPUT_SEARCH_BAR,
            WidgetIrKind.TECHNICAL_DIVIDER,
        }
    ),
    NodeType.COLUMN: frozenset(
        {
            WidgetIrKind.NAV_SCROLL_HOST,
            WidgetIrKind.CONTAINER_ACCORDION,
            WidgetIrKind.OVERLAY_BOTTOM_SHEET,
            WidgetIrKind.FEEDBACK_SKELETON,
        }
    ),
    NodeType.STACK: frozenset(
        {
            WidgetIrKind.CONTAINER_LIST_TILE,
            WidgetIrKind.MEDIA_BADGE,
            WidgetIrKind.NAV_APP_BAR,
            WidgetIrKind.OVERLAY_SNACKBAR,
            WidgetIrKind.OVERLAY_BANNER,
            WidgetIrKind.FEEDBACK_TOOLTIP,
            WidgetIrKind.NAV_SCROLL_HOST,
        }
    ),
    NodeType.VECTOR: frozenset(
        {
            WidgetIrKind.TECHNICAL_DIVIDER,
            WidgetIrKind.MEDIA_AVATAR,
            WidgetIrKind.FEEDBACK_LOADER,
        }
    ),
    NodeType.IMAGE: frozenset(
        {
            WidgetIrKind.MEDIA_AVATAR,
            WidgetIrKind.MEDIA_BADGE,
        }
    ),
    NodeType.WRAP: frozenset(
        {
            WidgetIrKind.CHIP_CHOICE,
            WidgetIrKind.CHIP_FILTER,
            WidgetIrKind.CHIP_INPUT,
        }
    ),
}


def plausible_kinds(node: CleanDesignTreeNode) -> frozenset[WidgetIrKind]:
    """Return a small candidate set for ``node`` (typically 2–8 kinds)."""
    candidates: set[WidgetIrKind] = set()
    typed = _NODE_TYPE_CANDIDATES.get(node.type)
    if typed:
        candidates.update(typed)

    if node.scroll_axis == "vertical" and node.type in {NodeType.COLUMN, NodeType.STACK}:
        candidates.add(WidgetIrKind.NAV_SCROLL_HOST)

    variant = node.variant
    if variant is not None:
        for key, value in variant.variant_properties.items():
            axis = key.lower()
            value_text = str(value).lower()
            if axis in {"type", "role", "variant", "control"}:
                if "search" in value_text:
                    candidates.add(WidgetIrKind.INPUT_SEARCH_BAR)
                if "date" in value_text:
                    candidates.add(WidgetIrKind.INPUT_PICKER_DATE)
                if "time" in value_text:
                    candidates.add(WidgetIrKind.INPUT_PICKER_TIME)
                if "chip" in value_text:
                    candidates.update(
                        {
                            WidgetIrKind.CHIP_CHOICE,
                            WidgetIrKind.CHIP_FILTER,
                            WidgetIrKind.CHIP_INPUT,
                        }
                    )
                if "segment" in value_text:
                    candidates.add(WidgetIrKind.CONTROL_SEGMENTED)
                if "stepper" in value_text or "step" in value_text:
                    candidates.update(
                        {
                            WidgetIrKind.INPUT_STEPPER,
                            WidgetIrKind.NAV_STEPPER,
                        }
                    )
                if "upload" in value_text or "file" in value_text:
                    candidates.add(WidgetIrKind.INPUT_FILE_UPLOADER)
                if "tooltip" in value_text:
                    candidates.add(WidgetIrKind.FEEDBACK_TOOLTIP)
                if "skeleton" in value_text:
                    candidates.add(WidgetIrKind.FEEDBACK_SKELETON)
                if "loader" in value_text or "spinner" in value_text:
                    candidates.add(WidgetIrKind.FEEDBACK_LOADER)
                if "sheet" in value_text:
                    candidates.add(WidgetIrKind.OVERLAY_BOTTOM_SHEET)
                if "snackbar" in value_text or "toast" in value_text:
                    candidates.add(WidgetIrKind.OVERLAY_SNACKBAR)
                if "banner" in value_text:
                    candidates.add(WidgetIrKind.OVERLAY_BANNER)
                if "drawer" in value_text:
                    candidates.add(WidgetIrKind.NAV_DRAWER)
                if "pagination" in value_text or "pager" in value_text:
                    candidates.add(WidgetIrKind.NAV_PAGINATION)
                if "accordion" in value_text:
                    candidates.add(WidgetIrKind.CONTAINER_ACCORDION)
                if "avatar" in value_text:
                    candidates.add(WidgetIrKind.MEDIA_AVATAR)
                if "badge" in value_text:
                    candidates.add(WidgetIrKind.MEDIA_BADGE)

    if node.type in {NodeType.STACK, NodeType.ROW} and len(node.children) >= 2:
        candidates.add(WidgetIrKind.CONTAINER_LIST_TILE)

    if not candidates:
        if node.type == NodeType.CONTAINER:
            candidates.add(WidgetIrKind.CONTAINER_CARD)
        elif node.type in {NodeType.ROW, NodeType.COLUMN}:
            candidates.add(WidgetIrKind.TECHNICAL_DIVIDER)

    return frozenset(candidates)
