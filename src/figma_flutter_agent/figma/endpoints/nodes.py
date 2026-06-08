"""Figma node endpoint methods."""

from __future__ import annotations

from typing import Any

from loguru import logger

from figma_flutter_agent.figma.limits import BATCH_SIZE
from figma_flutter_agent.figma.models import FigmaNodesResponse
from figma_flutter_agent.figma.nodes import merge_figma_nodes_batch


class NodesEndpoint:
    async def fetch_nodes(self, file_key: str, node_ids: list[str]) -> FigmaNodesResponse:
        """Fetch node subtrees for the given file key and node ids."""
        if not node_ids:
            return FigmaNodesResponse()

        merged_nodes: dict[str, Any] = {}
        dropped_node_ids: list[str] = []
        name: str | None = None
        styles: dict[str, dict[str, Any]] | None = None

        for index in range(0, len(node_ids), BATCH_SIZE):
            chunk = node_ids[index : index + BATCH_SIZE]
            ids = ",".join(chunk)
            response = await self._request(
                "GET",
                f"/v1/files/{file_key}/nodes",
                params={"ids": ids},
            )
            payload = response.json()
            if name is None:
                name = payload.get("name")
            batch_styles = payload.get("styles")
            if isinstance(batch_styles, dict):
                styles = {**(styles or {}), **batch_styles}
            dropped_node_ids.extend(
                merge_figma_nodes_batch(merged_nodes, payload.get("nodes"))
            )

        if dropped_node_ids:
            preview = ", ".join(dropped_node_ids[:8])
            suffix = "..." if len(dropped_node_ids) > 8 else ""
            logger.warning(
                "Figma nodes API returned null for {} node(s): {}{}",
                len(dropped_node_ids),
                preview,
                suffix,
            )

        return FigmaNodesResponse.model_validate(
            {"name": name, "nodes": merged_nodes, "styles": styles}
        )
