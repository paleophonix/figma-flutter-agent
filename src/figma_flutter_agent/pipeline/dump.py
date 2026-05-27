"""Load pipeline fetch state from cached Figma node dumps."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.parser.prototype import collect_prototype_links, index_frames
from figma_flutter_agent.stages.fetch import FigmaFetchResult


def load_fetch_result_from_dump(
    dump_path: Path,
    *,
    file_key: str,
    node_id: str,
) -> FigmaFetchResult:
    """Build a ``FigmaFetchResult`` from a cached raw layout dump file.

    Args:
        dump_path: Path to serialized Figma frame document JSON (``.figma_debug/raw/*``).
        file_key: Figma file key for metadata.
        node_id: Target node id (``page:frame``).

    Returns:
        Fetch result suitable for ``parse_figma_frame``.
    """
    root = json.loads(dump_path.read_text(encoding="utf-8"))
    if not isinstance(root, dict):
        msg = f"Dump at {dump_path} must contain a JSON object."
        raise ValueError(msg)
    return FigmaFetchResult(
        file_key=file_key,
        node_id=node_id,
        root=root,
        variables_payload=None,
        published_styles={},
        components={},
        component_sets={},
        prototype_links=collect_prototype_links(root),
        frame_index=index_frames(root),
    )
