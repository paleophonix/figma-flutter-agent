"""Canonical clean-tree normalization before deterministic or IR emit."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.generator.ir.validate import apply_ir_guards
from figma_flutter_agent.generator.tree_copy import deep_copy_clean_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode, DesignTokens, ScreenIr


def reconcile_layout_tree(
    tree: CleanDesignTreeNode,
    *,
    allow_placement_clamp: bool = True,
) -> CleanDesignTreeNode:
    """Apply layout reconciliation passes once (stack, CTA, auth chrome, etc.)."""
    from figma_flutter_agent.parser.layout import (
        reconcile_auth_button_icon_placements_in_tree,
        reconcile_centered_text_placements_in_tree,
        reconcile_consent_checkbox_rows_in_tree,
        reconcile_cta_footer_surfaces_in_tree,
        reconcile_duplicate_product_card_grids_in_tree,
        reconcile_grid_child_visual_order_in_tree,
        reconcile_logo_wordmark_top_in_tree,
        reconcile_payment_selection_state_in_tree,
        reconcile_playback_timestamp_row_in_tree,
        reconcile_promo_card_row_tops_in_tree,
        reconcile_stack_placements_in_tree,
        reconcile_title_subtitle_stacks_in_tree,
        reconcile_weekday_chip_row_in_tree,
    )

    working = deep_copy_clean_tree(tree)
    working = reconcile_stack_placements_in_tree(working, allow_clamp=allow_placement_clamp)
    from figma_flutter_agent.parser.render_bounds import reconcile_render_bounds_expansion_in_tree

    working = reconcile_render_bounds_expansion_in_tree(working)
    working = reconcile_auth_button_icon_placements_in_tree(working)
    working = reconcile_promo_card_row_tops_in_tree(working)
    working = reconcile_grid_child_visual_order_in_tree(working)
    working = reconcile_duplicate_product_card_grids_in_tree(working)
    working = reconcile_cta_footer_surfaces_in_tree(working)
    working = reconcile_logo_wordmark_top_in_tree(working)
    working = reconcile_title_subtitle_stacks_in_tree(working)
    working = reconcile_consent_checkbox_rows_in_tree(working)
    working = reconcile_payment_selection_state_in_tree(working)
    working = reconcile_weekday_chip_row_in_tree(working)
    working = reconcile_centered_text_placements_in_tree(working)
    working = reconcile_playback_timestamp_row_in_tree(working)
    return working


def normalize_clean_tree(
    tree: CleanDesignTreeNode,
    *,
    tokens: DesignTokens | None = None,
    project_dir: Path | None = None,
    screen_ir: ScreenIr | None = None,
    apply_render_safety: bool = True,
    use_geometry_planner: bool = True,
    strict_geometry_invariants: bool = False,
    preserve_placement: bool = False,
) -> CleanDesignTreeNode:
    """Return a canonical clean tree for both deterministic and IR emit paths.

    Args:
        tree: Parsed clean design tree (not mutated).
        tokens: Optional design tokens for guard token snapping.
        project_dir: Reserved for future asset gates during normalization.
        screen_ir: When set, render-safety guards use this IR instead of a
            structural blueprint so planner normalize stays dual-graph aligned.
        apply_render_safety: When true, run ``apply_ir_guards`` with a structural
            ``default_screen_ir`` blueprint so deterministic emit receives the
            same touch/scroll/clamp fixes as the IR path.
        use_geometry_planner: When true, attach ``layout_slot`` via geometry planner
            and validate translation-theory invariants before emit.
        strict_geometry_invariants: When true, treat context-dependent invariants
            (e.g. ``inv_ast_coverage``) as HARD.
        preserve_placement: When true, skip artboard/stack placement clamps.

    Returns:
        Normalized tree copy.
    """
    from figma_flutter_agent.generator.ir.tree import validate_unique_node_ids

    validate_unique_node_ids(tree)
    from figma_flutter_agent.generator.artboard import clamp_oversized_frame_widths_to_artboard
    from figma_flutter_agent.generator.geometry.invariants.checkpoints import run_cp1_normalize

    def _transform(source: CleanDesignTreeNode) -> CleanDesignTreeNode:
        reconciled = reconcile_layout_tree(
            source,
            allow_placement_clamp=not preserve_placement,
        )
        if preserve_placement:
            return reconciled
        return clamp_oversized_frame_widths_to_artboard(reconciled)

    working = run_cp1_normalize(
        tree,
        transform_fn=_transform,
    )
    if use_geometry_planner:
        from figma_flutter_agent.generator.geometry.invariants.reporting import (
            mark_degraded_nodes,
            raise_on_hard_geometry_violations,
        )
        from figma_flutter_agent.generator.geometry.invariants.validate import (
            validate_geometry_invariants,
        )
        from figma_flutter_agent.generator.geometry.planner import plan_geometry_tree

        working = plan_geometry_tree(working, project_dir=project_dir)
        violations = validate_geometry_invariants(
            working,
            require_layout_slots=True,
            strict_invariants=strict_geometry_invariants,
        )
        soft = raise_on_hard_geometry_violations(violations, context="normalize")
        if soft:
            working = mark_degraded_nodes(working, soft)
    if apply_render_safety:
        guard_ir = screen_ir if screen_ir is not None else default_screen_ir(working)
        working = apply_ir_guards(
            guard_ir,
            working,
            tokens=tokens,
            preserve_placement=preserve_placement,
        )
    if project_dir is not None:
        from figma_flutter_agent.parser.boundaries.assets import (
            resolve_discovered_vector_asset_keys,
            resolve_missing_image_asset_keys,
            resolve_pruned_cluster_instance_assets,
        )

        resolve_missing_image_asset_keys(working, project_dir)
        resolve_discovered_vector_asset_keys(working, project_dir)
        resolve_pruned_cluster_instance_assets(working, project_dir)
    from figma_flutter_agent.parser.layout import reconcile_product_hero_photo_viewport_in_tree

    working = reconcile_product_hero_photo_viewport_in_tree(working)
    return working


def clear_extracted_refs_for_inline_hosts(tree: CleanDesignTreeNode) -> CleanDesignTreeNode:
    """Strip ``extracted_widget_ref`` from nodes compiled inline by the layout emitter.

    Subtree pruning and LLM extracted-widget reconciliation may stamp widget
    stubs onto form-field hosts before ``render_layout_file``. Those refs must
    not reach deterministic layout emit.

    Args:
        tree: Parsed clean design tree (not mutated).

    Returns:
        Tree copy with inline-host extraction refs cleared.
    """
    from figma_flutter_agent.generator.tree_copy import deep_copy_clean_tree
    from figma_flutter_agent.parser.interaction import must_inline_extracted_widget_host

    def walk(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
        updated_children = [walk(child) for child in node.children]
        clear_ref = bool(node.extracted_widget_ref) and must_inline_extracted_widget_host(node)
        if not clear_ref and updated_children == node.children:
            return node
        updates: dict[str, object] = {}
        if clear_ref:
            updates["extracted_widget_ref"] = None
        if updated_children != node.children:
            updates["children"] = updated_children
        return node.model_copy(update=updates)

    return walk(deep_copy_clean_tree(tree))
