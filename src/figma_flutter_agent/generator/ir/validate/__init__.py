"""Validate screen IR against a clean design tree before Dart emission."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.ir.tree import index_clean_tree

if TYPE_CHECKING:
    from figma_flutter_agent.config.models import SemanticsSettings

# Re-exports from sub-modules — keep the public surface identical to the old validate.py
from figma_flutter_agent.generator.ir.validate.graph import (
    _align_ir_stack_children_to_clean_tree,
    _attach_ir_child_unique,
    _build_parent_map,
    _ensure_ir_hosts_on_path,
    _has_stack_ancestor,
    _index_ir_nodes,
    _ir_kind_for_clean_stub,
    _ir_node_is_stack_host,
    _is_opaque_stack_occluder,
    _is_stack_interactive,
    _realign_ir_node_children_to_clean_tree,
    _resolve_ir_host_for_clean_child,
    _stack_has_bounded_horizontal,
    _stack_has_bounded_vertical,
    _validate_ir_graph_integrity,
    _validate_stack_placement_bounds,
    _viewport_size,
    _walk_ir,
    ensure_ir_direct_children_match_clean,
    realign_screen_ir_children_to_clean_tree,
    stack_placement_bounded_for_ir,
    sync_screen_ir_graph_to_clean_tree,
)
from figma_flutter_agent.generator.ir.validate.guards import (
    _ancestor_scroll_axes,
    _apply_keyboard_scroll_guard,
    _apply_min_touch_target_guard,
    _apply_nested_scroll_guard,
    _apply_row_text_flex_guard,
    _Bounds,
    _bounds_overlap,
    _flex_wrap_covers_parent_axis,
    _in_scroll_context,
    _input_bottom_edge,
    _input_needs_keyboard_scroll_fix,
    _is_scroll_like_host,
    _is_skip_control_text,
    _nearest_column_scroll_host,
    _needs_nested_scroll_constraints,
    _node_bounds,
    _node_box_size,
    _scroll_axes_for,
    _validate_asset_paths,
    _validate_flex_child_slot,
    _validate_keyboard_scroll_trap,
    _validate_stack_ghost_occlusion,
    _validate_text_contrast,
    validate_render_safety,
)
from figma_flutter_agent.generator.ir.validate.tokens import (
    _build_token_registry,
    _collect_clean_tree_font_sizes,
    _collect_clean_tree_token_colors,
    _color_rgb,
    _merge_token_registry_with_clean_tree,
    _nearest_token_color,
    _nearest_token_font_size,
    _normalize_token_color,
    _resolve_token_color,
    _snap_ir_overrides_to_tokens,
    _TokenRegistry,
)
from figma_flutter_agent.generator.ir.validate.viewport import (
    _clamp_viewport_bounds,
    _validate_viewport_bounds,
    _viewport_box_metrics,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    DesignTokens,
    ExtractedWidget,
    ScreenIr,
    WidgetIrKind,
    WidgetIrNode,
)

__all__ = [
    # graph
    "_walk_ir",
    "_validate_ir_graph_integrity",
    "_build_parent_map",
    "_viewport_size",
    "_has_stack_ancestor",
    "_stack_has_bounded_horizontal",
    "_stack_has_bounded_vertical",
    "stack_placement_bounded_for_ir",
    "_validate_stack_placement_bounds",
    "_index_ir_nodes",
    "_attach_ir_child_unique",
    "_resolve_ir_host_for_clean_child",
    "_ensure_ir_hosts_on_path",
    "_realign_ir_node_children_to_clean_tree",
    "realign_screen_ir_children_to_clean_tree",
    "ensure_ir_direct_children_match_clean",
    "sync_screen_ir_graph_to_clean_tree",
    "_align_ir_stack_children_to_clean_tree",
    "_ir_node_is_stack_host",
    "_is_stack_interactive",
    "_is_opaque_stack_occluder",
    "_ir_kind_for_clean_stub",
    # guards
    "_Bounds",
    "_is_scroll_like_host",
    "_flex_wrap_covers_parent_axis",
    "_validate_flex_child_slot",
    "_is_skip_control_text",
    "_validate_text_contrast",
    "_in_scroll_context",
    "_scroll_axes_for",
    "_ancestor_scroll_axes",
    "_needs_nested_scroll_constraints",
    "_apply_nested_scroll_guard",
    "_apply_row_text_flex_guard",
    "_node_box_size",
    "_apply_min_touch_target_guard",
    "_validate_asset_paths",
    "_node_bounds",
    "_bounds_overlap",
    "validate_render_safety",
    "_validate_stack_ghost_occlusion",
    "_input_bottom_edge",
    "_input_needs_keyboard_scroll_fix",
    "_nearest_column_scroll_host",
    "_apply_keyboard_scroll_guard",
    "_validate_keyboard_scroll_trap",
    # tokens
    "_TokenRegistry",
    "_normalize_token_color",
    "_build_token_registry",
    "_collect_clean_tree_token_colors",
    "_collect_clean_tree_font_sizes",
    "_merge_token_registry_with_clean_tree",
    "_resolve_token_color",
    "_color_rgb",
    "_nearest_token_color",
    "_nearest_token_font_size",
    "_snap_ir_overrides_to_tokens",
    # viewport
    "_viewport_box_metrics",
    "_clamp_viewport_bounds",
    "_validate_viewport_bounds",
    # orchestration
    "apply_ir_guards",
    "_apply_ir_guards_inplace",
    "validate_screen_ir",
    "validate_extracted_widget_ir",
    "validate_extracted_widgets",
    "_find_parent_ir",
]


def apply_ir_guards(
    screen_ir: ScreenIr,
    root: CleanDesignTreeNode,
    *,
    tokens: DesignTokens | None = None,
    preserve_placement: bool = False,
    allow_ir_guards_mutating_paint: bool = True,
) -> CleanDesignTreeNode:
    """Apply render-safety guards on a tree copy; return normalized clean tree (INV-2).

    The input ``root`` is never mutated; callers must use the returned tree for emit.
    """
    from figma_flutter_agent.generator.tree_copy import deep_copy_clean_tree

    working = deep_copy_clean_tree(root)
    _apply_ir_guards_inplace(
        screen_ir,
        working,
        tokens=tokens,
        preserve_placement=preserve_placement,
        allow_ir_guards_mutating_paint=allow_ir_guards_mutating_paint,
    )
    return working


def _apply_ir_guards_inplace(
    screen_ir: ScreenIr,
    root: CleanDesignTreeNode,
    *,
    tokens: DesignTokens | None = None,
    preserve_placement: bool = False,
    allow_ir_guards_mutating_paint: bool = True,
) -> None:
    """Mutate ``root`` in place for render safety (internal; use ``apply_ir_guards``)."""
    tree_by_id = index_clean_tree(root)
    parent_by_id = _build_parent_map(root)
    viewport = _viewport_size(root)
    root_id = screen_ir.root.figma_id
    token_registry = _build_token_registry(tokens) if tokens is not None else None
    if token_registry is not None:
        token_registry = _merge_token_registry_with_clean_tree(token_registry, root)

    realign_screen_ir_children_to_clean_tree(screen_ir, root)
    _align_ir_stack_children_to_clean_tree(screen_ir.root, tree_by_id=tree_by_id)

    for ir_node in _walk_ir(screen_ir.root):
        clean = tree_by_id.get(ir_node.figma_id)
        if clean is None:
            continue
        if ir_node.overrides is not None and token_registry is not None:
            ir_node.overrides = _snap_ir_overrides_to_tokens(
                ir_node.overrides,
                figma_id=ir_node.figma_id,
                registry=token_registry,
                soft_invalid=True,
            )
        _apply_nested_scroll_guard(
            clean,
            root_id=root_id,
            parent_by_id=parent_by_id,
            tree_by_id=tree_by_id,
        )
        if allow_ir_guards_mutating_paint and not preserve_placement:
            _apply_row_text_flex_guard(
                ir_node,
                clean,
                parent_by_id=parent_by_id,
                tree_by_id=tree_by_id,
            )
            _apply_min_touch_target_guard(clean)
        if viewport is not None:
            viewport_width, viewport_height = viewport
            _apply_keyboard_scroll_guard(
                clean,
                viewport_height=viewport_height,
                parent_by_id=parent_by_id,
                tree_by_id=tree_by_id,
            )

    from figma_flutter_agent.generator.ir.states import apply_screen_ir_states_and_rules

    apply_screen_ir_states_and_rules(
        screen_ir,
        root,
        viewport_width=viewport[0] if viewport is not None else None,
    )

    if viewport is not None and not preserve_placement:
        viewport_width, viewport_height = viewport
        root_frame_id = root.id
        from figma_flutter_agent.generator.background.detection import (
            artboard_bleed_placement_exempt,
        )

        for node_id, clean in tree_by_id.items():
            if parent_by_id.get(node_id) != root_frame_id:
                continue
            if artboard_bleed_placement_exempt(clean, root, root):
                continue
            if _clamp_viewport_bounds(
                clean,
                viewport_width=viewport_width,
                viewport_height=viewport_height,
                parent_by_id=parent_by_id,
                tree_by_id=tree_by_id,
            ):
                logger.warning(
                    "Clamped stackPlacement for {} to fit {:.0f}x{:.0f} viewport",
                    node_id,
                    viewport_width,
                    viewport_height,
                )


def _find_parent_ir(node: WidgetIrNode, figma_id: str) -> WidgetIrNode | None:
    for child in node.children:
        if child.figma_id == figma_id:
            return node
        found = _find_parent_ir(child, figma_id)
        if found is not None:
            return found
    return None


def validate_screen_ir(
    screen_ir: ScreenIr,
    root: CleanDesignTreeNode,
    *,
    extracted_widget_names: frozenset[str] | None = None,
    declared_extracted_widget_names: frozenset[str] | None = None,
    project_dir: Path | None = None,
    tokens: DesignTokens | None = None,
    apply_guards: bool = True,
    skip_presence_normalize: bool = False,
    layout_source: str | None = None,
    strict_invariants: bool = False,
    semantics: SemanticsSettings | None = None,
    strict_contrast: bool = False,
) -> CleanDesignTreeNode:
    """Validate IR; optionally normalize tree via guards.

    Returns:
        The clean tree to use for emit (guarded copy when ``apply_guards`` is true,
        otherwise the original ``root``).

    Raises:
        GenerationError: When IR references unknown nodes or unsafe render structure.
    """
    if apply_guards:
        root = apply_ir_guards(screen_ir, root, tokens=tokens)
    else:
        realign_screen_ir_children_to_clean_tree(screen_ir, root)

    declared_extracted = (
        declared_extracted_widget_names
        if declared_extracted_widget_names is not None
        else (extracted_widget_names or frozenset())
    )
    from figma_flutter_agent.generator.ir.presence import (
        expand_extracted_widget_names_for_validate,
        sanitize_screen_ir_llm_drift,
    )

    canonical_extracted = expand_extracted_widget_names_for_validate(
        declared_extracted,
        clean_tree=root,
        screen_ir=screen_ir,
    )

    sanitize_screen_ir_llm_drift(
        screen_ir,
        root,
        declared_extracted_widget_names=declared_extracted,
        canonical_extracted_widget_names=canonical_extracted,
        semantics=semantics,
    )
    realign_screen_ir_children_to_clean_tree(screen_ir, root)

    tree_by_id = index_clean_tree(root)
    parent_by_id = _build_parent_map(root)
    viewport = _viewport_size(root)
    omit = frozenset(screen_ir.omit_figma_ids)
    extracted = canonical_extracted

    _validate_ir_graph_integrity(screen_ir.root)
    if not apply_guards:
        _align_ir_stack_children_to_clean_tree(screen_ir.root, tree_by_id=tree_by_id)
    _validate_stack_ghost_occlusion(screen_ir.root, tree_by_id=tree_by_id)

    if screen_ir.root.figma_id not in tree_by_id:
        raise GenerationError(
            f"screenIr.root figmaId {screen_ir.root.figma_id!r} not in clean tree"
        )
    if screen_ir.root.figma_id in omit:
        raise GenerationError("screenIr.root cannot appear in omitFigmaIds")

    for rule in screen_ir.adaptive_rules:
        if rule.figma_id not in tree_by_id:
            raise GenerationError(
                f"screenIr adaptiveRules figmaId {rule.figma_id!r} not in clean tree"
            )
        if _find_parent_ir(screen_ir.root, rule.figma_id) is None:
            raise GenerationError(
                f"screenIr adaptiveRules figmaId {rule.figma_id!r} not present in screenIr graph"
            )

    for ir_node in _walk_ir(screen_ir.root):
        if ir_node.figma_id not in tree_by_id:
            raise GenerationError(f"screenIr figmaId {ir_node.figma_id!r} not in clean tree")
        if ir_node.figma_id in omit:
            raise GenerationError(f"screenIr node {ir_node.figma_id!r} is listed in omitFigmaIds")
        clean = tree_by_id[ir_node.figma_id]
        if ir_node.kind == WidgetIrKind.EXTRACTED:
            if ir_node.ref is None or not ir_node.ref.widget_name.strip():
                raise GenerationError(
                    f"screenIr node {ir_node.figma_id!r} kind=extracted requires ref.widgetName"
                )
            if extracted and ir_node.ref.widget_name not in extracted:
                raise GenerationError(
                    f"extracted widget {ir_node.ref.widget_name!r} not in extractedWidgets"
                )
            if ir_node.children:
                raise GenerationError(
                    f"screenIr node {ir_node.figma_id!r} kind=extracted must not have children"
                )
        child_ids = {child.id for child in clean.children}
        for ir_child in ir_node.children:
            if ir_child.figma_id not in child_ids:
                raise GenerationError(
                    f"screenIr child {ir_child.figma_id!r} is not a child of {ir_node.figma_id!r} "
                    "in cleanTree"
                )
        _validate_stack_placement_bounds(clean)
        parent_id = parent_by_id.get(ir_node.figma_id)
        if parent_id is not None:
            parent_clean = tree_by_id.get(parent_id)
            if parent_clean is not None:
                _validate_flex_child_slot(ir_node, clean, parent_clean)
        if strict_contrast or (semantics is not None and semantics.strict_a11y):
            _validate_text_contrast(
                clean,
                tree_by_id=tree_by_id,
                parent_by_id=parent_by_id,
            )
        if project_dir is not None:
            _validate_asset_paths(clean, project_dir)
        if viewport is not None:
            viewport_width, viewport_height = viewport
            _validate_viewport_bounds(
                clean,
                viewport_width=viewport_width,
                viewport_height=viewport_height,
                root_id=root.id,
                parent_by_id=parent_by_id,
                tree_by_id=tree_by_id,
            )
            _validate_keyboard_scroll_trap(
                clean,
                viewport_height=viewport_height,
                parent_by_id=parent_by_id,
                tree_by_id=tree_by_id,
            )

    if screen_ir.root.figma_id == root.id:
        from figma_flutter_agent.generator.ir.presence import validate_stack_visual_ir_coverage

        validate_stack_visual_ir_coverage(
            screen_ir,
            root,
            extracted_widget_names=extracted_widget_names,
            skip_presence_normalize=skip_presence_normalize,
        )
    from figma_flutter_agent.generator.geometry.invariants.reporting import (
        raise_on_hard_geometry_violations,
    )
    from figma_flutter_agent.generator.geometry.invariants.validate import (
        validate_geometry_invariants,
    )

    geometry_violations = validate_geometry_invariants(
        root,
        layout_source=layout_source,
        strict_invariants=strict_invariants,
    )
    raise_on_hard_geometry_violations(geometry_violations, context="ir_validate")
    return root


def validate_extracted_widget_ir(
    widget: ExtractedWidget,
    root: CleanDesignTreeNode,
    *,
    project_dir: Path | None = None,
    tokens: DesignTokens | None = None,
) -> None:
    """Raise when an extracted widget IR subtree is invalid against ``root``."""
    if widget.widget_ir is None:
        return
    tree_by_id = index_clean_tree(root)
    if widget.widget_ir.figma_id not in tree_by_id:
        logger.warning(
            "Skipping widgetIr validation for {}: figmaId {} absent from clean tree "
            "(likely true_subtree_pruning); rely on deterministic lib/widgets code",
            widget.widget_name,
            widget.widget_ir.figma_id,
        )
        return
    validate_screen_ir(
        ScreenIr(root=widget.widget_ir),
        root,
        extracted_widget_names=frozenset({widget.widget_name}),
        project_dir=project_dir,
        tokens=tokens,
    )


def validate_extracted_widgets(
    widgets: list[ExtractedWidget],
    root: CleanDesignTreeNode,
    *,
    project_dir: Path | None = None,
    tokens: DesignTokens | None = None,
) -> None:
    for widget in widgets:
        validate_extracted_widget_ir(widget, root, project_dir=project_dir, tokens=tokens)
