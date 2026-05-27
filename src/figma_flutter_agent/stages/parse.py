"""Parse stage for the generation pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field

from loguru import logger

from figma_flutter_agent.generator.destinations import build_destination_trees
from figma_flutter_agent.parser.dedup import DedupResult
from figma_flutter_agent.parser.prototype import PrototypeLink
from figma_flutter_agent.parser.tokens import build_design_tokens
from figma_flutter_agent.parser.tree import build_clean_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode, DesignTokens
from figma_flutter_agent.stages.fetch import FigmaFetchResult


@dataclass
class FigmaParseResult:
    """Structured design data parsed from a fetched Figma frame."""

    tokens: DesignTokens
    clean_tree: CleanDesignTreeNode
    absolute_ratio: float
    dedup_result: DedupResult
    cluster_summary: dict[str, int]
    destination_trees: dict[str, CleanDesignTreeNode] = field(default_factory=dict)
    destination_widget_hints: dict[str, list[str]] = field(default_factory=dict)


def parse_figma_frame(
    fetch: FigmaFetchResult,
    *,
    prototype_links: list[PrototypeLink] | None = None,
) -> FigmaParseResult:
    """Parse tokens and clean trees from a fetch result.

    Args:
        fetch: ``FigmaFetchResult`` or compatible object with root/style metadata.
        prototype_links: Optional prototype links when not present on ``fetch``.

    Returns:
        Parsed tokens, clean tree, and destination metadata.
    """
    log = logger.bind(file_key=fetch.file_key, node_id=fetch.node_id, stage="parse")
    log.debug("Parsing Figma frame {}", fetch.root.get("name"))
    links = prototype_links if prototype_links is not None else fetch.prototype_links
    tokens = build_design_tokens(fetch.root, fetch.variables_payload)
    clean_tree, absolute_ratio, dedup_result, cluster_summary = build_clean_tree(
        fetch.root,
        published_styles=fetch.published_styles,
        components=fetch.components,
        component_sets=fetch.component_sets,
        style_paint_index=fetch.style_paint_index,
    )
    destination_node_ids = {link.destination_node_id for link in links}
    destination_trees, destination_widget_hints = build_destination_trees(
        fetch.frame_index,
        destination_node_ids,
        published_styles=fetch.published_styles,
        components=fetch.components,
        component_sets=fetch.component_sets,
        style_paint_index=fetch.style_paint_index,
    )
    return FigmaParseResult(
        tokens=tokens,
        clean_tree=clean_tree,
        absolute_ratio=absolute_ratio,
        dedup_result=dedup_result,
        cluster_summary=cluster_summary,
        destination_trees=destination_trees,
        destination_widget_hints=destination_widget_hints,
    )
