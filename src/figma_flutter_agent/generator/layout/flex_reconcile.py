"""Tree- and AST-driven flex guards for generated screen/layout Dart."""

from __future__ import annotations

from loguru import logger

from figma_flutter_agent.generator.figma_anchor import figma_key_token
from figma_flutter_agent.generator.layout.common import (
    GEOMETRY_PLANNER_MARKER,
    is_centered_glyph_badge,
)
from figma_flutter_agent.generator.layout.flex_policy import (
    FlexWrapKind,
    apply_flex_wrap_to_widget,
    resolve_flex_wrap,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, LayoutBackend, NodeType, WrapKind
from figma_flutter_agent.tools.ast_sidecar import (
    AstSidecarError,
    apply_ast_rules,
    ast_source_exceeds_sidecar_limit,
    extract_widget_by_figma_id,
    replace_widget_by_figma_id,
)

_WRAP_TO_FLEX_KIND = {
    WrapKind.EXPANDED: FlexWrapKind.EXPANDED,
    WrapKind.FLEXIBLE_LOOSE: FlexWrapKind.FLEXIBLE_LOOSE,
    WrapKind.CONSTRAINED_BOX: FlexWrapKind.SIZED_BOX_WIDTH,
}


def _walk_with_parent(
    root: CleanDesignTreeNode,
    parent: CleanDesignTreeNode | None,
) -> list[tuple[CleanDesignTreeNode | None, CleanDesignTreeNode]]:
    pairs: list[tuple[CleanDesignTreeNode | None, CleanDesignTreeNode]] = [(parent, root)]
    for child in root.children:
        pairs.extend(_walk_with_parent(child, root))
    return pairs


def _parent_node_type(parent: CleanDesignTreeNode | None) -> NodeType | None:
    return parent.type if parent is not None else None


def _skip_flex_wrap_for_glyph_badge_child(
    parent: CleanDesignTreeNode | None,
    kind: FlexWrapKind,
) -> bool:
    """Glyph badges center a single letter inside ``Container`` — not ``Row`` flex."""
    if parent is None or not is_centered_glyph_badge(parent):
        return False
    return kind in {FlexWrapKind.EXPANDED, FlexWrapKind.FLEXIBLE_LOOSE}


def _snippet_already_wrapped(snippet: str, kind: FlexWrapKind) -> bool:
    trimmed = snippet.strip()
    if kind == FlexWrapKind.EXPANDED:
        return trimmed.startswith("Expanded(") or trimmed.startswith("const Expanded(")
    if kind == FlexWrapKind.FLEXIBLE_LOOSE:
        return trimmed.startswith("Flexible(") or trimmed.startswith("const Flexible(")
    if kind == FlexWrapKind.SIZED_BOX_WIDTH:
        return "width: double.infinity" in trimmed or trimmed.startswith("SizedBox(")
    return False


def _apply_planner_wraps(source: str, root: CleanDesignTreeNode) -> str:
    """Verify/apply flex wraps authorized by ``layout_slot.wraps``."""
    updated = source
    for parent, node in _walk_with_parent(root, None):
        slot = node.layout_slot
        if slot is None or not slot.wraps:
            continue
        parent_type = _parent_node_type(parent)
        if parent_type not in {NodeType.ROW, NodeType.COLUMN}:
            continue
        for wrap in slot.wraps:
            kind = _WRAP_TO_FLEX_KIND.get(wrap)
            if kind is None or _skip_flex_wrap_for_glyph_badge_child(parent, kind):
                continue
            token = figma_key_token(node.id)
            if token not in updated:
                continue
            snippet = extract_widget_by_figma_id(updated, node.id)
            if snippet is None or _snippet_already_wrapped(snippet, kind):
                continue
            wrapped_inner = apply_flex_wrap_to_widget(
                snippet,
                parent_type=parent_type,
                node=node,
            )
            replaced = replace_widget_by_figma_id(updated, node.id, wrapped_inner)
            if replaced is not None:
                updated = replaced
    return updated


def apply_flex_guards_from_tree(
    source: str,
    root: CleanDesignTreeNode,
    *,
    run_ast_pass: bool = False,
) -> str:
    """Apply flex-child policy via optional AST pass and Figma-keyed tree reconciliation."""
    planner_managed = GEOMETRY_PLANNER_MARKER in source
    if planner_managed:
        run_ast_pass = False
    if ast_source_exceeds_sidecar_limit(source):
        logger.warning(
            "Flex guard reconciliation skipped for oversized Dart ({} bytes)",
            len(source.encode("utf-8")),
        )
        return source
    updated = source
    if run_ast_pass:
        try:
            updated = apply_ast_rules(
                updated,
                ("wrap_flex_row_column_children",),
                include_text_scaler=False,
            ).source
        except AstSidecarError as exc:
            logger.warning("AST flex wrap pass skipped: {}", exc)

    if planner_managed:
        return _apply_planner_wraps(updated, root)

    for parent, node in _walk_with_parent(root, None):
        if parent is not None:
            parent_slot = parent.layout_slot
            if parent_slot is not None and parent_slot.backend == LayoutBackend.STACK:
                continue
            if parent.type == NodeType.STACK:
                continue
        parent_type = _parent_node_type(parent)
        if parent_type not in {NodeType.ROW, NodeType.COLUMN}:
            continue
        kind = resolve_flex_wrap(parent_type=parent_type, node=node)
        if kind == FlexWrapKind.NONE or _skip_flex_wrap_for_glyph_badge_child(
            parent, kind
        ):
            continue
        token = figma_key_token(node.id)
        if token not in updated:
            continue
        snippet = extract_widget_by_figma_id(updated, node.id)
        if snippet is None or _snippet_already_wrapped(snippet, kind):
            continue
        wrapped_inner = apply_flex_wrap_to_widget(
            snippet,
            parent_type=parent_type,
            node=node,
        )
        replaced = replace_widget_by_figma_id(updated, node.id, wrapped_inner)
        if replaced is not None:
            updated = replaced
    return updated
