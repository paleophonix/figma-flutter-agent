"""Generate LLM output for prototype destination screens."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

from figma_flutter_agent.errors import LlmError
from figma_flutter_agent.llm.client import LlmClient
from figma_flutter_agent.parser.dedup import build_widget_extraction_hints
from figma_flutter_agent.parser.navigation import RouteDefinition, normalize_feature_name
from figma_flutter_agent.parser.tree import build_clean_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode, DesignTokens, FlutterGenerationResponse


def build_destination_trees(
    frame_index: dict[str, dict[str, Any]],
    destination_node_ids: set[str],
    *,
    published_styles: dict[str, dict[str, Any]] | None,
    components: dict[str, dict[str, Any]] | None,
    component_sets: dict[str, dict[str, Any]] | None = None,
    style_paint_index: dict[str, dict[str, Any]] | None = None,
) -> tuple[dict[str, CleanDesignTreeNode], dict[str, list[str]]]:
    """Build clean trees and widget hints for destination prototype frames."""
    trees: dict[str, CleanDesignTreeNode] = {}
    widget_hints: dict[str, list[str]] = {}
    for node_id in destination_node_ids:
        frame = frame_index.get(node_id)
        if not isinstance(frame, dict):
            continue
        feature_name = normalize_feature_name(str(frame.get("name") or node_id))
        tree, _, dedup_result, cluster_summary = build_clean_tree(
            frame,
            published_styles=published_styles,
            components=components,
            component_sets=component_sets,
            style_paint_index=style_paint_index,
        )
        trees[feature_name] = tree
        widget_hints[feature_name] = build_widget_extraction_hints(dedup_result, cluster_summary)
    return trees, widget_hints


async def _generate_destination_screen(
    llm: LlmClient,
    *,
    destination_tree: CleanDesignTreeNode,
    tokens: DesignTokens,
    feature_name: str,
    asset_manifest: list[dict[str, str]],
    widget_hints: list[str],
    navigation_hints: list[str],
    routing_enabled: bool,
    theme_variant: str = "material_3",
    use_screen_ir: bool = False,
    require_screen_ir: bool = False,
    project_dir: Path | None = None,
) -> FlutterGenerationResponse:
    return await llm.generate_async(
        destination_tree,
        tokens,
        feature_name=feature_name,
        asset_manifest=asset_manifest,
        widget_hints=widget_hints,
        navigation_hints=navigation_hints,
        routing_enabled=routing_enabled,
        theme_variant=theme_variant,
        use_screen_ir=use_screen_ir,
        require_screen_ir=require_screen_ir,
        project_dir=project_dir,
    )


async def generate_destination_screens(
    llm: LlmClient,
    *,
    routes: list[RouteDefinition],
    current_feature: str,
    frame_index: dict[str, dict[str, Any]],
    tokens: DesignTokens,
    asset_manifest: list[dict[str, str]],
    navigation_hints: list[str],
    published_styles: dict[str, dict[str, Any]] | None,
    components: dict[str, dict[str, Any]] | None,
    component_sets: dict[str, dict[str, Any]] | None = None,
    routing_enabled: bool,
    theme_variant: str = "material_3",
    destination_trees: dict[str, CleanDesignTreeNode] | None = None,
    destination_widget_hints: dict[str, list[str]] | None = None,
    style_paint_index: dict[str, dict[str, Any]] | None = None,
    allow_stubs: bool = False,
    use_screen_ir: bool = False,
    require_screen_ir: bool = False,
    project_dir: Path | None = None,
) -> tuple[dict[str, FlutterGenerationResponse], list[str]]:
    """Generate LLM screen output for prototype destination frames.

    Args:
        llm: Configured LLM client.
        routes: Planned navigation routes.
        current_feature: Primary feature name that was already generated.
        frame_index: Indexed Figma frame nodes keyed by node id.
        tokens: Shared design tokens for all screens.
        asset_manifest: Exported asset metadata for prompt context.
        navigation_hints: Prototype navigation hints for prompt context.
        published_styles: Published Figma styles map.
        components: Published Figma components map.
        routing_enabled: Whether routing integration is active.
        destination_trees: Pre-built clean trees keyed by feature name.
        destination_widget_hints: Pre-built widget hints keyed by feature name.
        style_paint_index: Published style paint lookup for fallback tree building.

    Returns:
        Tuple of generated responses keyed by feature name and warning messages.
    """
    responses: dict[str, FlutterGenerationResponse] = {}
    warnings: list[str] = []

    for route in routes:
        if route.name == current_feature or not route.node_id:
            continue

        if destination_trees is not None and route.name in destination_trees:
            destination_tree = destination_trees[route.name]
            widget_hints = (destination_widget_hints or {}).get(route.name, [])
        else:
            destination_frame = frame_index.get(route.node_id)
            if destination_frame is None:
                continue
            destination_tree, _, dedup_result, cluster_summary = build_clean_tree(
                destination_frame,
                published_styles=published_styles,
                components=components,
                component_sets=component_sets,
                style_paint_index=style_paint_index,
            )
            widget_hints = build_widget_extraction_hints(dedup_result, cluster_summary)

        try:
            response = await _generate_destination_screen(
                llm,
                destination_tree=destination_tree,
                tokens=tokens,
                feature_name=route.name,
                asset_manifest=asset_manifest,
                widget_hints=widget_hints,
                navigation_hints=navigation_hints,
                routing_enabled=routing_enabled,
                theme_variant=theme_variant,
                use_screen_ir=use_screen_ir,
                require_screen_ir=require_screen_ir,
                project_dir=project_dir,
            )
        except LlmError:
            if not allow_stubs:
                raise
            logger.exception("Destination screen generation failed for {}", route.name)
            warnings.append(
                f"Destination screen generation failed for '{route.name}'; using placeholder stub"
            )
            continue

        responses[route.name] = response

    return responses, warnings
