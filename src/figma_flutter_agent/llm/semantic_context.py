"""Assemble navigation-only semantic context views for the IR structured LLM call."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType
from figma_flutter_agent.schemas.geometry import GeomRect

_FORBIDDEN_KEY_RE = re.compile(
    r"^(role|subtype|contract_kind|contract_traits|proposed_layout_laws|"
    r"control_node_id|boundary_node_id|placeholder_node_ids|value_node_ids|"
    r"decoration_node_ids|option_node_ids|state_node_ids|label_node_ids|"
    r"should_.*|production_effects|is_password|is_login|is_rating|is_textarea|is_button|is_form|label_for)$",
    re.IGNORECASE,
)

_RELATION_KINDS = frozenset(
    {
        "parent_child",
        "next_sibling",
        "previous_sibling",
        "next_sibling_in_column",
        "previous_sibling_in_column",
        "inside_bounds",
        "above",
        "below",
        "left_of",
        "right_of",
        "overlaps",
        "same_component_group",
    }
)

# SemanticContextPayloadBudgetLaw — hard backstop after structural-only spatial hints.
_MAX_RELATIONSHIP_HINTS = 2048

_STRUCTURAL_RELATION_KINDS = frozenset(
    {
        "parent_child",
        "next_sibling",
        "previous_sibling",
        "next_sibling_in_column",
        "previous_sibling_in_column",
        "same_component_group",
    }
)


class SemanticContextPacket(BaseModel):
    """Compact context views plus full raw subtree JSON for debug triage."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    raw_context: dict[str, Any] = Field(alias="rawContext")
    tree_outline: list[dict[str, Any]] = Field(alias="treeOutline")
    text_inventory: list[dict[str, Any]] = Field(alias="textInventory")
    component_inventory: list[dict[str, Any]] = Field(alias="componentInventory")
    geometry_inventory: list[dict[str, Any]] = Field(alias="geometryInventory")
    relationship_hints: list[dict[str, Any]] = Field(alias="relationshipHints")
    screen_ir_blueprint: dict[str, Any] | None = Field(default=None, alias="screenIrBlueprint")

    def model_dump_for_llm(self) -> dict[str, Any]:
        """Serialize compact sections for generate user payload (SemanticContextPayloadBudgetLaw).

        Omits ``rawContext`` and ``geometryInventory`` because ``### cleanTree`` already carries
        authoritative layout semantics. Omits ``screenIrBlueprint`` because the caller injects it
        once at the top level of the user payload.
        """
        return self.model_dump(
            by_alias=True,
            exclude_none=True,
            mode="json",
            exclude={"raw_context", "geometry_inventory", "screen_ir_blueprint"},
        )

    def model_dump_for_debug(self) -> dict[str, Any]:
        """Serialize the full packet for ``.debug`` triage artifacts."""
        return self.model_dump(by_alias=True, exclude_none=True, mode="json")


def assemble_semantic_context(
    root: CleanDesignTreeNode,
    *,
    screen_ir_blueprint: dict[str, Any] | None = None,
) -> SemanticContextPacket:
    """Build raw subtree JSON and compact navigation views (no semantic classification).

    Args:
        root: Parsed clean design tree root for the target screen.
        screen_ir_blueprint: Optional compiler IR skeleton already prepared for the LLM.

    Returns:
        Semantic context packet suitable for IR generate user payload and debug dumps.
    """
    indexed: dict[str, _NodeContext] = {}
    tree_outline: list[dict[str, Any]] = []
    text_inventory: list[dict[str, Any]] = []
    component_inventory: list[dict[str, Any]] = []
    geometry_inventory: list[dict[str, Any]] = []

    def walk(
        node: CleanDesignTreeNode,
        *,
        parent_id: str | None,
        depth: int,
        siblings: list[CleanDesignTreeNode],
    ) -> None:
        bounds = _node_bounds(node)
        ctx = _NodeContext(
            node=node,
            parent_id=parent_id,
            depth=depth,
            siblings=siblings,
            bounds=bounds,
        )
        indexed[node.id] = ctx
        tree_outline.append(
            _tree_outline_entry(node, parent_id=parent_id, depth=depth, bounds=bounds)
        )
        geometry_inventory.append(
            _geometry_inventory_entry(node, parent_id=parent_id, bounds=bounds),
        )
        if node.text and node.type in {NodeType.TEXT, NodeType.BUTTON, NodeType.INPUT}:
            text_inventory.append(_text_inventory_entry(node, parent_id=parent_id, bounds=bounds))
        if _has_component_metadata(node):
            component_inventory.append(
                _component_inventory_entry(node, parent_id=parent_id, bounds=bounds),
            )
        for child in node.children:
            walk(child, parent_id=node.id, depth=depth + 1, siblings=node.children)

    walk(root, parent_id=None, depth=0, siblings=[])

    text_inventory.sort(key=lambda item: (item["bounds"]["top"], item["bounds"]["left"]))
    relationship_hints = _build_relationship_hints(indexed)

    return SemanticContextPacket(
        rawContext=root.model_dump(by_alias=True, mode="json"),
        treeOutline=tree_outline,
        textInventory=text_inventory,
        componentInventory=component_inventory,
        geometryInventory=geometry_inventory,
        relationshipHints=relationship_hints,
        screenIrBlueprint=screen_ir_blueprint,
    )


def collect_forbidden_semantic_keys(payload: Any) -> list[str]:
    """Return forbidden semantic classifier key names found anywhere in a packet."""
    found: list[str] = []

    def visit(value: Any, key: str | None) -> None:
        if key is not None and _FORBIDDEN_KEY_RE.match(key):
            found.append(key)
        if isinstance(value, dict):
            for child_key, child_value in value.items():
                visit(child_value, str(child_key))
        elif isinstance(value, list):
            for item in value:
                visit(item, None)

    visit(payload, None)
    return found


class _NodeContext:
    """Indexed node with layout metadata for relationship hints."""

    __slots__ = ("bounds", "depth", "node", "parent_id", "siblings")

    def __init__(
        self,
        *,
        node: CleanDesignTreeNode,
        parent_id: str | None,
        depth: int,
        siblings: list[CleanDesignTreeNode],
        bounds: dict[str, float],
    ) -> None:
        self.node = node
        self.parent_id = parent_id
        self.depth = depth
        self.siblings = siblings
        self.bounds = bounds


def _node_bounds(node: CleanDesignTreeNode) -> dict[str, float]:
    if node.geometry_frame is not None:
        rect = node.geometry_frame.world_aabb
        if rect.width > 0 or rect.height > 0:
            return _rect_to_bounds(rect)
        rect = node.geometry_frame.layout_rect
        if rect.width > 0 or rect.height > 0:
            return _rect_to_bounds(rect)
    placement = node.stack_placement
    if placement is not None:
        width = placement.width if placement.width is not None else (node.sizing.width or 0.0)
        height = placement.height if placement.height is not None else (node.sizing.height or 0.0)
        return {
            "left": float(placement.left),
            "top": float(placement.top),
            "width": float(width),
            "height": float(height),
        }
    width = float(node.sizing.width or 0.0)
    height = float(node.sizing.height or 0.0)
    return {"left": 0.0, "top": 0.0, "width": width, "height": height}


def _rect_to_bounds(rect: GeomRect) -> dict[str, float]:
    return {
        "left": float(rect.x),
        "top": float(rect.y),
        "width": float(rect.width),
        "height": float(rect.height),
    }


def _size_summary(node: CleanDesignTreeNode) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "widthMode": node.sizing.width_mode.value,
        "heightMode": node.sizing.height_mode.value,
    }
    if node.sizing.width is not None:
        summary["width"] = node.sizing.width
    if node.sizing.height is not None:
        summary["height"] = node.sizing.height
    return summary


def _tree_outline_entry(
    node: CleanDesignTreeNode,
    *,
    parent_id: str | None,
    depth: int,
    bounds: dict[str, float],
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "id": node.id,
        "parent_id": parent_id,
        "depth": depth,
        "name": node.name,
        "type": node.type.value,
        "children_count": len(node.children),
        "size": {"width": bounds["width"], "height": bounds["height"]},
    }
    if node.variant and node.variant.component_name:
        entry["componentName"] = node.variant.component_name
    return entry


def _text_inventory_entry(
    node: CleanDesignTreeNode,
    *,
    parent_id: str | None,
    bounds: dict[str, float],
) -> dict[str, Any]:
    style = node.style
    style_summary: dict[str, Any] = {}
    if style.font_size is not None:
        style_summary["fontSize"] = style.font_size
    if style.font_weight is not None:
        style_summary["fontWeight"] = style.font_weight
    if style.text_color is not None:
        style_summary["textColor"] = style.text_color
    if style.text_align is not None:
        style_summary["textAlign"] = style.text_align
    if style.font_family is not None:
        style_summary["fontFamily"] = style.font_family
    entry: dict[str, Any] = {
        "id": node.id,
        "parent_id": parent_id,
        "text": node.text,
        "name": node.name,
        "bounds": bounds,
    }
    if node.accessibility_label:
        entry["accessibilityLabel"] = node.accessibility_label
    if style_summary:
        entry["style"] = style_summary
    return entry


def _has_component_metadata(node: CleanDesignTreeNode) -> bool:
    if node.component_ref:
        return True
    return bool(node.variant and (node.variant.component_name or node.variant.variant_properties))


def _component_inventory_entry(
    node: CleanDesignTreeNode,
    *,
    parent_id: str | None,
    bounds: dict[str, float],
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "id": node.id,
        "parent_id": parent_id,
        "name": node.name,
        "type": node.type.value,
        "bounds": bounds,
        "children_count": len(node.children),
    }
    if node.component_ref:
        entry["componentRef"] = node.component_ref
    if node.variant:
        if node.variant.component_name:
            entry["componentName"] = node.variant.component_name
        if node.variant.variant_properties:
            entry["variantProperties"] = dict(node.variant.variant_properties)
    return entry


def _geometry_inventory_entry(
    node: CleanDesignTreeNode,
    *,
    parent_id: str | None,
    bounds: dict[str, float],
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "id": node.id,
        "parent_id": parent_id,
        "name": node.name,
        "type": node.type.value,
        "bounds": bounds,
        "sizing": _size_summary(node),
        "padding": node.padding.model_dump(by_alias=True, mode="json"),
        "spacing": node.spacing,
        "alignment": node.alignment.model_dump(by_alias=True, mode="json"),
        "layoutPositioning": node.layout_positioning,
        "children_count": len(node.children),
    }
    if node.geometry_frame is not None:
        entry["worldAabb"] = _rect_to_bounds(node.geometry_frame.world_aabb)
        entry["layoutRect"] = _rect_to_bounds(node.geometry_frame.layout_rect)
    return entry


def _build_relationship_hints(indexed: dict[str, _NodeContext]) -> list[dict[str, Any]]:
    hints: list[dict[str, Any]] = []
    for node_id, ctx in indexed.items():
        if ctx.parent_id is not None:
            hints.append(
                {
                    "kind": "parent_child",
                    "from_node_id": ctx.parent_id,
                    "to_node_id": node_id,
                    "relation": "parent_child",
                    "parent_id": ctx.parent_id,
                }
            )
        sibling_ids = [sibling.id for sibling in ctx.siblings]
        if node_id in sibling_ids:
            index = sibling_ids.index(node_id)
            if index > 0:
                prev_id = sibling_ids[index - 1]
                hints.append(_sibling_hint(ctx, prev_id, "previous_sibling"))
                if _parent_is_column(ctx.parent_id, indexed):
                    hints.append(_column_sibling_hint(ctx, prev_id, "previous_sibling_in_column"))
            if index < len(sibling_ids) - 1:
                next_id = sibling_ids[index + 1]
                hints.append(_sibling_hint(ctx, next_id, "next_sibling"))
                if _parent_is_column(ctx.parent_id, indexed):
                    hints.append(_column_sibling_hint(ctx, next_id, "next_sibling_in_column"))

  # RelationshipHintStructuralOnlyLaw: never emit O(n^2) above/below/left_of for all pairs.
    node_ids = list(indexed.keys())
    for left_index, left_id in enumerate(node_ids):
        left_ctx = indexed[left_id]
        for right_id in node_ids[left_index + 1 :]:
            right_ctx = indexed[right_id]
            if _contains(left_ctx.bounds, right_ctx.bounds):
                hints.append(
                    {
                        "kind": "inside_bounds",
                        "from_node_id": left_id,
                        "to_node_id": right_id,
                        "relation": "inside_bounds",
                        "distance_px": _center_distance(left_ctx.bounds, right_ctx.bounds),
                    }
                )
            elif _contains(right_ctx.bounds, left_ctx.bounds):
                hints.append(
                    {
                        "kind": "inside_bounds",
                        "from_node_id": right_id,
                        "to_node_id": left_id,
                        "relation": "inside_bounds",
                        "distance_px": _center_distance(left_ctx.bounds, right_ctx.bounds),
                    }
                )
            elif _overlaps(left_ctx.bounds, right_ctx.bounds):
                hints.append(
                    {
                        "kind": "overlaps",
                        "from_node_id": left_id,
                        "to_node_id": right_id,
                        "relation": "overlaps",
                        "distance_px": _center_distance(left_ctx.bounds, right_ctx.bounds),
                    }
                )
            if _same_component_group(left_ctx.node, right_ctx.node):
                hints.append(
                    {
                        "kind": "same_component_group",
                        "from_node_id": left_id,
                        "to_node_id": right_id,
                        "relation": "same_component_group",
                    }
                )

    return _cap_relationship_hints(_dedupe_hints(hints))


def _parent_is_column(parent_id: str | None, indexed: dict[str, _NodeContext]) -> bool:
    if parent_id is None or parent_id not in indexed:
        return False
    return indexed[parent_id].node.type == NodeType.COLUMN


def _sibling_hint(ctx: _NodeContext, other_id: str, kind: str) -> dict[str, Any]:
    other_node = next(s for s in ctx.siblings if s.id == other_id)
    return {
        "kind": kind,
        "from_node_id": ctx.node.id,
        "to_node_id": other_id,
        "relation": kind,
        "distance_px": _center_distance(ctx.bounds, _node_bounds(other_node)),
        "parent_id": ctx.parent_id,
    }


def _column_sibling_hint(ctx: _NodeContext, other_id: str, kind: str) -> dict[str, Any]:
    other_node = next(s for s in ctx.siblings if s.id == other_id)
    return {
        "kind": kind,
        "from_node_id": ctx.node.id,
        "to_node_id": other_id,
        "relation": kind,
        "distance_px": _center_distance(ctx.bounds, _node_bounds(other_node)),
        "parent_id": ctx.parent_id,
    }



def _contains(outer: dict[str, float], inner: dict[str, float]) -> bool:
    return (
        inner["left"] >= outer["left"]
        and inner["top"] >= outer["top"]
        and inner["left"] + inner["width"] <= outer["left"] + outer["width"]
        and inner["top"] + inner["height"] <= outer["top"] + outer["height"]
    )


def _overlaps(left: dict[str, float], right: dict[str, float]) -> bool:
    return not (
        left["left"] + left["width"] <= right["left"]
        or right["left"] + right["width"] <= left["left"]
        or left["top"] + left["height"] <= right["top"]
        or right["top"] + right["height"] <= left["top"]
    )


def _center_distance(left: dict[str, float], right: dict[str, float]) -> float:
    left_cx = left["left"] + left["width"] / 2
    left_cy = left["top"] + left["height"] / 2
    right_cx = right["left"] + right["width"] / 2
    right_cy = right["top"] + right["height"] / 2
    return round(((right_cx - left_cx) ** 2 + (right_cy - left_cy) ** 2) ** 0.5, 2)


def _same_component_group(left: CleanDesignTreeNode, right: CleanDesignTreeNode) -> bool:
    if left.component_ref and left.component_ref == right.component_ref:
        return True
    left_set = left.variant.component_set_id if left.variant else None
    right_set = right.variant.component_set_id if right.variant else None
    return bool(left_set and left_set == right_set)


def _cap_relationship_hints(hints: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep structural hints first; drop overflow spatial pairs under budget."""
    if len(hints) <= _MAX_RELATIONSHIP_HINTS:
        return hints
    structural = [hint for hint in hints if hint.get("kind") in _STRUCTURAL_RELATION_KINDS]
    spatial = [hint for hint in hints if hint.get("kind") not in _STRUCTURAL_RELATION_KINDS]
    if len(structural) >= _MAX_RELATIONSHIP_HINTS:
        return structural[:_MAX_RELATIONSHIP_HINTS]
    return structural + spatial[: _MAX_RELATIONSHIP_HINTS - len(structural)]


def _dedupe_hints(hints: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    unique: list[dict[str, Any]] = []
    for hint in hints:
        if hint.get("kind") not in _RELATION_KINDS:
            continue
        key = (
            hint.get("kind"),
            hint.get("from_node_id"),
            hint.get("to_node_id"),
            hint.get("relation"),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(hint)
    return unique
