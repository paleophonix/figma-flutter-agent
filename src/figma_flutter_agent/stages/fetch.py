"""Figma fetch stage for the generation pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from figma_flutter_agent.errors import FlutterProjectError
from figma_flutter_agent.figma.connector import FigmaConnector
from figma_flutter_agent.parser.prototype import (
    PrototypeLink,
    collect_prototype_links,
    index_frames,
)
from figma_flutter_agent.parser.styles import build_style_paint_index, collect_style_node_ids


@dataclass
class FigmaFetchResult:
    """Raw Figma payload fetched for a target frame."""

    file_key: str
    node_id: str
    root: dict[str, Any]
    variables_payload: dict[str, Any] | None
    published_styles: dict[str, dict[str, Any]]
    components: dict[str, dict[str, Any]]
    published_variables_payload: dict[str, Any] | None = None
    image_fill_urls: dict[str, str] = field(default_factory=dict)
    component_sets: dict[str, dict[str, Any]] = field(default_factory=dict)
    style_paint_index: dict[str, dict[str, Any]] = field(default_factory=dict)
    prototype_links: list[PrototypeLink] = field(default_factory=list)
    frame_index: dict[str, dict[str, Any]] = field(default_factory=dict)


async def fetch_figma_frame(
    connector: FigmaConnector,
    *,
    file_key: str,
    node_id: str,
    project_dir: Path,
    verbose: bool = False,
) -> FigmaFetchResult:
    """Fetch Figma metadata and the target frame subtree.

    Args:
        connector: Active Figma API client.
        file_key: Figma file key.
        node_id: Target frame node id.
        project_dir: Flutter project used for optional debug dumps.
        verbose: Reserved for pipeline-level debug dump control.

    Returns:
        Parsed fetch payload for the parse stage.

    Raises:
        FlutterProjectError: When the target node is missing from the Figma file response.
    """
    import asyncio

    log = logger.bind(file_key=file_key, node_id=node_id, stage="fetch")
    log.info("Fetching Figma frame metadata")

    (
        nodes_response,
        variables_payload,
        published_variables_payload,
        image_fill_urls,
        published_styles,
        components,
        component_sets,
    ) = await asyncio.gather(
        connector.fetch_nodes(file_key, [node_id]),
        connector.fetch_variables(file_key),
        connector.fetch_published_variables(file_key),
        connector.fetch_image_fills(file_key),
        connector.fetch_styles(file_key),
        connector.fetch_components(file_key),
        connector.fetch_component_sets(file_key),
    )

    entry = nodes_response.nodes.get(node_id)
    if not entry or not entry.document:
        raise FlutterProjectError(
            f"Node {node_id} was not found in Figma file "
            "(deleted frame, wrong node-id, or no access). "
            "Update screens.yaml / --node-id or use --from-dump for offline runs."
        )

    root = entry.document
    prototype_links = collect_prototype_links(root)
    frame_index = index_frames(root)

    from figma_flutter_agent.parser.prototype import collect_missing_destination_ids

    missing_destination_ids = collect_missing_destination_ids(prototype_links, frame_index)
    if missing_destination_ids:
        extra_nodes_response = await connector.fetch_nodes(file_key, missing_destination_ids)
        for extra_entry in extra_nodes_response.nodes.values():
            if extra_entry.document:
                frame_index.update(index_frames(extra_entry.document))

    style_paint_index: dict[str, dict[str, Any]] = {}
    style_node_ids = collect_style_node_ids(published_styles)
    if style_node_ids:
        style_nodes_response = await connector.fetch_nodes(file_key, style_node_ids)
        style_paint_index = build_style_paint_index(
            published_styles,
            {
                style_node_id: style_entry.document
                for style_node_id, style_entry in style_nodes_response.nodes.items()
                if style_entry.document is not None
            },
        )

    if verbose:
        log.debug(
            "Fetch verbose flag set; raw/processed dumps are written after feature resolution in the pipeline"
        )

    log.info(
        "Fetch complete: prototype_links={} style_paints={} components={}",
        len(prototype_links),
        len(style_paint_index),
        len(components),
    )

    return FigmaFetchResult(
        file_key=file_key,
        node_id=node_id,
        root=root,
        variables_payload=variables_payload,
        published_variables_payload=published_variables_payload,
        image_fill_urls=image_fill_urls,
        published_styles=published_styles,
        components=components,
        component_sets=component_sets,
        style_paint_index=style_paint_index,
        prototype_links=prototype_links,
        frame_index=frame_index,
    )
