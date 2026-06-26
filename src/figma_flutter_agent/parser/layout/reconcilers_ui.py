"""Interactive UI component reconcilers: auth pills, consent rows, weekday chips, CTA footers."""

from __future__ import annotations

from figma_flutter_agent.parser.interaction import (
    COMPACT_CHIP_ROW_ROLE,
    layout_fact_checkbox_control,
    layout_fact_consent_label_text,
)
from figma_flutter_agent.parser.numeric_rounding import round_geometry
from figma_flutter_agent.parser.semantics.signals.chip_anatomy import layout_fact_compact_chip_stack
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    StackPlacement,
)

from .placement import _infer_stack_child_top

_AUTH_PILL_ICON_MAX_LEFT_RATIO = 0.28
_AUTH_PILL_ICON_MAX_WIDTH_RATIO = 0.35
_AUTH_PILL_ICON_CENTER_TOLERANCE_PX = 4.0

_CONSENT_ROW_MAX_TOP_GAP_PX = 12.0
WEEKDAY_CHIP_ROW_ID_PREFIX = "weekday-row:"
_WEEKDAY_CHIP_ROW_MAX_TOP_GAP_PX = 12.0
_WEEKDAY_CHIP_ROW_MIN_COUNT = 5


def is_weekday_chip_row_wrapper_id(node_id: str) -> bool:
    """Return whether ``node_id`` names a core-reconcile weekday chip row host."""
    return node_id.startswith(WEEKDAY_CHIP_ROW_ID_PREFIX)


def weekday_chip_row_synthesized_node_ids(root: CleanDesignTreeNode) -> frozenset[str]:
    """Collect compiler-synthesized weekday chip row wrapper ids under ``root``."""
    collected: set[str] = set()

    def walk(node: CleanDesignTreeNode) -> None:
        if is_weekday_chip_row_wrapper_id(node.id):
            collected.add(node.id)
        for child in node.children:
            walk(child)

    walk(root)
    return frozenset(collected)

_CTA_SURFACE_FOOTER_GAP_PX = 4.0
_MIN_CTA_SURFACE_HEIGHT_PX = 32.0


def _is_auth_pill_container(node: CleanDesignTreeNode) -> bool:
    """Return True for full-width social/login pill rows (geometry only)."""
    from figma_flutter_agent.parser.geometry import (
        auth_button_confidence,
        social_auth_row_confidence,
    )

    return auth_button_confidence(node) >= 0.5 or social_auth_row_confidence(node) >= 0.65


def reconcile_auth_button_icon_placements_in_tree(
    root: CleanDesignTreeNode,
) -> CleanDesignTreeNode:
    """Vertically center compact left icons inside auth pill stacks."""

    def patch_icon_placements(
        node: CleanDesignTreeNode,
        *,
        pill_height: float,
        pill_width: float,
    ) -> CleanDesignTreeNode:
        children = [
            patch_icon_placements(child, pill_height=pill_height, pill_width=pill_width)
            for child in node.children
        ]
        node = node.model_copy(update={"children": children})
        if node.type not in {NodeType.VECTOR, NodeType.IMAGE, NodeType.STACK}:
            return node
        if node.type == NodeType.STACK and not node.vector_asset_key:
            return node
        placement = node.stack_placement
        if placement is None:
            return node
        icon_height = placement.height if placement.height is not None else node.sizing.height
        icon_width = placement.width if placement.width is not None else node.sizing.width
        if icon_height is None or icon_width is None or icon_height <= 0:
            return node
        left = placement.left if placement.left is not None else node.offset_x
        if left is None or left > pill_width * _AUTH_PILL_ICON_MAX_LEFT_RATIO:
            return node
        if icon_width > pill_width * _AUTH_PILL_ICON_MAX_WIDTH_RATIO:
            return node
        current_top = _infer_stack_child_top(placement, parent_height=pill_height)
        if current_top is None:
            return node
        centered_top = (pill_height - float(icon_height)) / 2.0
        if abs(float(current_top) - centered_top) <= _AUTH_PILL_ICON_CENTER_TOLERANCE_PX:
            return node
        new_top = round_geometry(centered_top)
        if new_top is None:
            return node
        return node.model_copy(
            update={
                "stack_placement": placement.model_copy(
                    update={"top": new_top, "bottom": None},
                ),
            },
        )

    def walk(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
        children = [walk(child) for child in node.children]
        node = node.model_copy(update={"children": children})
        if not _is_auth_pill_container(node):
            return node
        pill_height = node.sizing.height
        pill_width = node.sizing.width
        if pill_height is None or pill_width is None or pill_height <= 0:
            return node
        return patch_icon_placements(
            node,
            pill_height=float(pill_height),
            pill_width=float(pill_width),
        )

    return walk(root)


def reconcile_consent_checkbox_rows_in_tree(
    root: CleanDesignTreeNode,
) -> CleanDesignTreeNode:
    """Merge privacy/consent copy with a sibling checkbox into one positioned row."""

    def walk(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
        children = [walk(child) for child in node.children]
        if node.type != NodeType.STACK:
            return node.model_copy(update={"children": children})
        consent_rows: list[CleanDesignTreeNode] = []
        consumed: set[str] = set()
        for child in children:
            if not layout_fact_checkbox_control(child):
                continue
            checkbox_place = child.stack_placement
            if checkbox_place is None or checkbox_place.top is None:
                continue
            label_node: CleanDesignTreeNode | None = None
            for candidate in children:
                if candidate.type != NodeType.TEXT or candidate.id in consumed:
                    continue
                if not layout_fact_consent_label_text(candidate.text or candidate.name):
                    continue
                label_place = candidate.stack_placement
                if label_place is None or label_place.top is None:
                    continue
                if (
                    abs(float(label_place.top) - float(checkbox_place.top))
                    > _CONSENT_ROW_MAX_TOP_GAP_PX
                ):
                    continue
                label_left = float(label_place.left or 0.0)
                checkbox_left = float(checkbox_place.left or 0.0)
                if label_left >= checkbox_left:
                    continue
                label_node = candidate
                break
            if label_node is None:
                continue
            consumed.add(label_node.id)
            consumed.add(child.id)
            label_place = label_node.stack_placement
            assert label_place is not None
            row_left = float(label_place.left or 0.0)
            row_top = float(label_place.top or checkbox_place.top or 0.0)
            row_width = (
                float(checkbox_place.left or 0.0)
                + float(child.sizing.width or checkbox_place.width or 24.0)
                - row_left
            )
            row_height = max(
                float(label_place.height or label_node.sizing.height or 0.0),
                float(checkbox_place.height or child.sizing.height or 0.0),
            )
            row_place = label_place.model_copy(
                update={
                    "left": round_geometry(row_left),
                    "top": round_geometry(row_top),
                    "width": round_geometry(row_width),
                    "height": round_geometry(row_height),
                    "horizontal": "LEFT",
                    "vertical": "TOP",
                },
            )
            consent_rows.append(
                CleanDesignTreeNode(
                    id=f"{child.id}-consent-row",
                    name="ConsentRow",
                    type=NodeType.STACK,
                    sizing=node.sizing.model_copy(
                        update={
                            "width": row_width,
                            "height": row_height,
                        },
                    ),
                    stack_placement=row_place,
                    children=[label_node, child],
                ),
            )
        merged_children = [child for child in children if child.id not in consumed] + consent_rows
        return node.model_copy(update={"children": merged_children})

    return walk(root)


def reconcile_weekday_chip_row_in_tree(
    root: CleanDesignTreeNode,
) -> CleanDesignTreeNode:
    """Merge sibling weekday chip stacks into one interactive row node."""

    def walk(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
        children = [walk(child) for child in node.children]
        node = node.model_copy(update={"children": children})
        if node.type != NodeType.STACK:
            return node
        chips = [child for child in children if layout_fact_compact_chip_stack(child)]
        if len(chips) < _WEEKDAY_CHIP_ROW_MIN_COUNT:
            return node
        tops = [
            float(chip.stack_placement.top)
            for chip in chips
            if chip.stack_placement is not None and chip.stack_placement.top is not None
        ]
        if tops and max(tops) - min(tops) > _WEEKDAY_CHIP_ROW_MAX_TOP_GAP_PX:
            return node
        consumed = {chip.id for chip in chips}
        lefts = [
            float(chip.stack_placement.left)
            for chip in chips
            if chip.stack_placement is not None and chip.stack_placement.left is not None
        ]
        rights = [
            float(chip.stack_placement.left or 0.0) + float(chip.sizing.width or 0.0)
            for chip in chips
            if chip.stack_placement is not None
        ]
        row_left = min(lefts) if lefts else 0.0
        row_top = min(tops) if tops else 0.0
        row_width = max(rights) - row_left if rights else float(node.sizing.width or 0.0)
        row_height = max(float(chip.sizing.height or 0.0) for chip in chips) if chips else 0.0
        row_place = StackPlacement(
            left=round_geometry(row_left),
            top=round_geometry(row_top),
            width=round_geometry(row_width),
            height=round_geometry(row_height),
            horizontal="LEFT",
            vertical="TOP",
        )
        row_node = CleanDesignTreeNode(
            id=f"{WEEKDAY_CHIP_ROW_ID_PREFIX}{chips[0].id}",
            name=node.name or "ChipRow",
            type=NodeType.STACK,
            layout_role=COMPACT_CHIP_ROW_ROLE,
            sizing=node.sizing.model_copy(
                update={
                    "width": row_width,
                    "height": row_height,
                },
            ),
            stack_placement=row_place,
            children=sorted(
                chips,
                key=lambda item: (
                    float(item.stack_placement.left or 0.0)
                    if item.stack_placement is not None
                    else 0.0
                ),
            ),
        )
        merged_children = [child for child in children if child.id not in consumed] + [row_node]
        return node.model_copy(update={"children": merged_children})

    return walk(root)


def reconcile_cta_footer_surfaces_in_tree(
    root: CleanDesignTreeNode,
) -> CleanDesignTreeNode:
    """Move footer link rows below the full CTA pill instead of shrinking the fill height."""
    from figma_flutter_agent.parser.interaction import (
        _is_footer_link_text_node,
        _local_nodes,
        _stack_spans_primary_button_and_footer_link,
        primary_surface_node,
    )

    def walk(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
        children = [walk(child) for child in node.children]
        node = node.model_copy(update={"children": children})
        if node.type != NodeType.STACK:
            return node
        text_nodes = [
            item for item in _local_nodes(node, 2) if item.type == NodeType.TEXT and item.text
        ]
        if not _stack_spans_primary_button_and_footer_link(node, text_nodes=text_nodes):
            return node
        surface = primary_surface_node(node)
        if surface is None:
            return node
        parent_height = float(node.sizing.height or 0)
        if parent_height <= 0:
            return node
        surface_placement = surface.stack_placement
        if surface_placement is None:
            return node
        surface_top = _infer_stack_child_top(surface_placement, parent_height=parent_height)
        if surface_top is None:
            return node
        surface_height = float(surface_placement.height or surface.sizing.height or 0)
        if surface_height < _MIN_CTA_SURFACE_HEIGHT_PX:
            surface_height = _MIN_CTA_SURFACE_HEIGHT_PX
        min_footer_top = surface_top + surface_height + _CTA_SURFACE_FOOTER_GAP_PX
        patched_children: list[CleanDesignTreeNode] = []
        stack_height = parent_height
        for child in node.children:
            if child.type != NodeType.TEXT or not _is_footer_link_text_node(child):
                patched_children.append(child)
                continue
            placement = child.stack_placement
            if placement is None or placement.top is None:
                patched_children.append(child)
                continue
            current_top = float(placement.top)
            if current_top + 0.5 >= min_footer_top:
                patched_children.append(child)
                continue
            footer_height = float(placement.height or child.sizing.height or 0)
            new_top = round_geometry(min_footer_top)
            if new_top is None:
                patched_children.append(child)
                continue
            patched_children.append(
                child.model_copy(
                    update={
                        "stack_placement": placement.model_copy(update={"top": new_top}),
                    },
                ),
            )
            if footer_height > 0:
                stack_height = max(stack_height, float(new_top) + footer_height)
        if stack_height > parent_height + 0.5:
            node = node.model_copy(
                update={"sizing": node.sizing.model_copy(update={"height": stack_height})},
            )
        return node.model_copy(update={"children": patched_children})

    return walk(root)


def reconcile_checkout_footer_bottom_nav_in_tree(
    root: CleanDesignTreeNode,
) -> CleanDesignTreeNode:
    """Demote misclassified checkout footers from bottom nav to absolute stack hosts."""
    from figma_flutter_agent.parser.interaction.product import (
        layout_fact_bottom_nav_is_checkout_footer,
    )

    def walk(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
        children = [walk(child) for child in node.children]
        node = node.model_copy(update={"children": children})
        if layout_fact_bottom_nav_is_checkout_footer(node):
            return node.model_copy(update={"type": NodeType.STACK})
        return node

    return walk(root)


def reconcile_payment_selection_state_in_tree(
    root: CleanDesignTreeNode,
) -> CleanDesignTreeNode:
    """Stamp payment margin indicators with selected/default variant from card fill."""
    from figma_flutter_agent.parser.interaction.selection import (
        layout_fact_hosts_payment_selection_indicator,
        payment_option_button_is_selected,
    )
    from figma_flutter_agent.schemas import ComponentVariant

    def walk(
        node: CleanDesignTreeNode,
        *,
        option_button: CleanDesignTreeNode | None,
    ) -> CleanDesignTreeNode:
        current_button = option_button
        if node.type == NodeType.BUTTON and node.style.background_color:
            current_button = node
        children = [walk(child, option_button=current_button) for child in node.children]
        node = node.model_copy(update={"children": children})
        if not layout_fact_hosts_payment_selection_indicator(node):
            return node
        selected = payment_option_button_is_selected(current_button)
        return node.model_copy(
            update={
                "variant": ComponentVariant(
                    state="selected" if selected else "default",
                )
            }
        )

    return walk(root, option_button=None)
