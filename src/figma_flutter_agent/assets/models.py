"""Asset export models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from figma_flutter_agent.schemas import AssetManifest

AssetKind = Literal["icon", "image", "illustration", "boundary_svg"]


@dataclass(frozen=True)
class AssetExportOutcome:
    """Outcome of exporting assets for a Figma document subtree."""

    manifest: AssetManifest
    exported_node_ids: frozenset[str]
    failed_node_ids: frozenset[str]
    rate_limited: bool
