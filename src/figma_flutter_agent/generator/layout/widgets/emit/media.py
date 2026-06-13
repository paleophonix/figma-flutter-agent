"""IMAGE / VECTOR node rendering branch."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode

from ..finalize import _finalize_widget
from ..playback import _render_native_blur_vector, _render_svg_picture_variant
from ..svg import (
    _render_exported_vector,
    _should_center_in_parent_stack,
    _wrap_centered_stack_child,
)


def render_image_or_vector(node: CleanDesignTreeNode, ctx: dict, flow: dict) -> str | None:
    """Render NodeType.IMAGE / NodeType.VECTOR nodes. Returns None if no branch matches."""
    parent_type = flow["parent_type"]
    parent_node = flow["parent_node"]
    scroll_content_root = flow["scroll_content_root"]
    uses_svg = ctx["uses_svg"]
    cluster_vector_variant = ctx["cluster_vector_variant"]

    if node.vector_asset_key:
        raw_asset = node.vector_asset_key
        if cluster_vector_variant and raw_asset in {
            cluster_vector_variant.forward_asset,
            cluster_vector_variant.backward_asset,
        }:
            widget = _render_svg_picture_variant(
                node,
                forward_asset=cluster_vector_variant.forward_asset,
                backward_asset=cluster_vector_variant.backward_asset,
                param_name=cluster_vector_variant.param_name,
            )
            fill_parent = _should_center_in_parent_stack(node, parent_node)
            if fill_parent:
                widget = _wrap_centered_stack_child(node, widget)
            return _finalize_widget(
                node,
                widget,
                parent_type=parent_type,
                parent_node=parent_node,
                fill_parent=fill_parent,
                scroll_content_root=scroll_content_root,
            )

        exported = _render_exported_vector(node, uses_svg=uses_svg)
        if exported is not None:
            widget = exported
            fill_parent = _should_center_in_parent_stack(node, parent_node)
            if fill_parent:
                widget = _wrap_centered_stack_child(node, widget)
            return _finalize_widget(
                node,
                widget,
                parent_type=parent_type,
                parent_node=parent_node,
                fill_parent=fill_parent,
                scroll_content_root=scroll_content_root,
            )

    if node.style.layer_blur or node.vector_svg_has_filter:
        widget = _render_native_blur_vector(node)
        fill_parent = _should_center_in_parent_stack(node, parent_node)
        if fill_parent:
            widget = _wrap_centered_stack_child(node, widget)
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            fill_parent=fill_parent,
            scroll_content_root=scroll_content_root,
        )

    from ..svg import render_filled_vector_leaf

    filled = render_filled_vector_leaf(node)
    if filled is not None:
        fill_parent = _should_center_in_parent_stack(node, parent_node)
        widget = filled
        if fill_parent:
            widget = _wrap_centered_stack_child(node, widget)
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            parent_node=parent_node,
            fill_parent=fill_parent,
            scroll_content_root=scroll_content_root,
        )

    return None
