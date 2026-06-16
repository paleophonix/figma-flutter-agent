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
    archetype_reconcile: bool = True,
) -> CleanDesignTreeNode:
    """Apply layout reconciliation passes once (stack, CTA, auth chrome, etc.)."""
    from figma_flutter_agent.parser.layout.reconcile_registry import (
        run_registered_reconcile_passes,
    )

    return run_registered_reconcile_passes(
        deep_copy_clean_tree(tree),
        archetype_reconcile=archetype_reconcile,
        allow_placement_clamp=allow_placement_clamp,
    )


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
    suppress_archetype_compensation: bool = False,
    archetype_reconcile: bool = False,
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
        suppress_archetype_compensation: When true, skip archetype-tier reconcile passes.
        archetype_reconcile: When true, run legacy archetype reconcile passes (opt-in).

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
            archetype_reconcile=archetype_reconcile and not suppress_archetype_compensation,
        )
        if preserve_placement:
            return reconciled
        return clamp_oversized_frame_widths_to_artboard(reconciled)

    working = run_cp1_normalize(
        tree,
        transform_fn=_transform,
        check_placement_truth=preserve_placement,
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
            allow_ir_guards_mutating_paint=not preserve_placement,
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
    from figma_flutter_agent.parser.layout.reconcile_registry import should_run_reconcile_pass

    if should_run_reconcile_pass(
        "reconcile_product_hero_photo_viewport_in_tree",
        archetype_reconcile=archetype_reconcile and not suppress_archetype_compensation,
    ):
        working = reconcile_product_hero_photo_viewport_in_tree(working)
    return working


def replan_geometry_after_layout_passes(
    tree: CleanDesignTreeNode,
    *,
    project_dir: Path | None = None,
) -> CleanDesignTreeNode:
    """Re-attach ``layout_slot`` after IR layout passes mutate the clean tree.

    Passes such as sectionize may insert compiler-synthesized nodes (for example
    ``band-*`` Y-band visual islands) after the initial normalize geometry plan.
    Emit requires every consumable node to carry a geometry ``layout_slot``.

    Args:
        tree: Clean tree after dual-graph layout passes.
        project_dir: Optional Flutter project root for baseline oracle seeding.

    Returns:
        Tree copy with geometry planner slots refreshed for the current structure.
    """
    from figma_flutter_agent.generator.geometry.planner import plan_geometry_tree

    return plan_geometry_tree(tree, project_dir=project_dir)


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
