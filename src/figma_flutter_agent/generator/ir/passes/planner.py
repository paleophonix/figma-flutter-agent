"""Planner integration for IR layout passes."""

from __future__ import annotations

from dataclasses import replace

from figma_flutter_agent.generator.ir.passes import apply_ir_layout_passes
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.generator.planner.context import GenerationPlanContext
from figma_flutter_agent.schemas import CleanDesignTreeNode, FlutterGenerationResponse, ScreenIr


def apply_layout_passes_to_context(
    context: GenerationPlanContext,
) -> GenerationPlanContext:
    """Run dual-graph layout passes on the plan context before layout emit.

    Args:
        context: Active generation plan context.

    Returns:
        Context with synchronized clean trees and screen IR for all routes.
    """
    threshold = context.settings.agent.responsive.macro_height_threshold_px
    updated_ir, updated_clean = _run_passes_for_tree(
        context.clean_tree,
        screen_ir=_resolve_screen_ir(context),
        macro_height_threshold_px=threshold,
    )
    generation = context.generation
    if generation is not None:
        generation = generation.model_copy(update={"screen_ir": updated_ir})

    destination_trees: dict[str, CleanDesignTreeNode] = {}
    destination_generations: dict[str, FlutterGenerationResponse] = dict(
        context.destination_generations,
    )
    for route_name, destination_tree in context.destination_trees.items():
        destination_generation = context.destination_generations.get(route_name)
        dest_screen_ir = (
            destination_generation.screen_ir
            if destination_generation is not None and destination_generation.screen_ir is not None
            else default_screen_ir(destination_tree)
        )
        dest_updated_ir, dest_updated_clean = _run_passes_for_tree(
            destination_tree,
            screen_ir=dest_screen_ir,
            macro_height_threshold_px=threshold,
        )
        destination_trees[route_name] = dest_updated_clean
        if destination_generation is not None:
            destination_generations[route_name] = destination_generation.model_copy(
                update={"screen_ir": dest_updated_ir},
            )

    return replace(
        context,
        clean_tree=updated_clean,
        generation=generation,
        destination_trees={**context.destination_trees, **destination_trees},
        destination_generations=destination_generations,
    )


def apply_layout_passes_for_layout_emit(
    clean_tree: CleanDesignTreeNode,
    *,
    screen_ir: ScreenIr | None = None,
    macro_height_threshold_px: int = 900,
) -> CleanDesignTreeNode:
    """Run layout passes for deterministic layout-only emit paths.

    Args:
        clean_tree: Parsed clean design tree.
        screen_ir: Optional screen IR; defaults to identity blueprint.
        macro_height_threshold_px: Scroll host threshold in logical pixels.

    Returns:
        Updated clean tree synchronized with the IR pass output.
    """
    resolved_ir = screen_ir or default_screen_ir(clean_tree)
    _, updated_clean = _run_passes_for_tree(
        clean_tree,
        screen_ir=resolved_ir,
        macro_height_threshold_px=macro_height_threshold_px,
    )
    return updated_clean


def _run_passes_for_tree(
    clean_tree: CleanDesignTreeNode,
    *,
    screen_ir: ScreenIr,
    macro_height_threshold_px: int,
) -> tuple[ScreenIr, CleanDesignTreeNode]:
    return apply_ir_layout_passes(
        screen_ir,
        clean_tree,
        macro_height_threshold_px=macro_height_threshold_px,
        inject_root_scroll_host=True,
    )


def _resolve_screen_ir(context: GenerationPlanContext) -> ScreenIr:
    if context.generation is not None and context.generation.screen_ir is not None:
        return context.generation.screen_ir
    return default_screen_ir(context.clean_tree)
