"""Node and cluster region hashes for incremental sync (spec §16)."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field

from figma_flutter_agent.generator.paths import Architecture, screen_file_path
from figma_flutter_agent.generator.widget_extractor import (
    collect_cluster_widget_specs,
)
from figma_flutter_agent.parser.dedup.signatures import structural_signature
from figma_flutter_agent.schemas import CleanDesignTreeNode


def _hash_payload(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def subtree_hash(node: CleanDesignTreeNode) -> str:
    """Return a stable hash for a clean-tree subtree rooted at ``node``."""
    return structural_signature(node)


def collect_subtree_hashes(root: CleanDesignTreeNode) -> dict[str, str]:
    """Map every node id in the tree to its subtree content hash."""
    hashes: dict[str, str] = {}

    def walk(node: CleanDesignTreeNode) -> None:
        hashes[node.id] = subtree_hash(node)
        for child in node.children:
            walk(child)

    walk(root)
    return hashes


def _collapsed_layout_payload(node: CleanDesignTreeNode) -> dict[str, object]:
    """Serialize a node for layout-region hashing (cluster subtrees collapsed to refs)."""
    if node.cluster_id:
        return {"clusterRef": node.cluster_id}
    return {
        "type": node.type.value,
        "name": node.name,
        "text": node.text,
        "spacing": node.spacing,
        "padding": node.padding.model_dump(),
        "sizing": node.sizing.model_dump(by_alias=True),
        "alignment": node.alignment.model_dump(),
        "scrollAxis": node.scroll_axis,
        "gridColumnCount": node.grid_column_count,
        "children": [_collapsed_layout_payload(child) for child in node.children],
    }


def layout_region_hash(root: CleanDesignTreeNode) -> str:
    """Hash the layout shell tree with extracted widgets replaced by cluster references."""
    return _hash_payload(_collapsed_layout_payload(root))


def compute_cluster_hashes(
    root: CleanDesignTreeNode,
    subtree_hashes: dict[str, str],
) -> dict[str, str]:
    """Aggregate per-node subtree hashes into one hash per ``cluster_id``."""
    members: dict[str, list[str]] = defaultdict(list)

    def walk(node: CleanDesignTreeNode) -> None:
        if node.cluster_id:
            members[node.cluster_id].append(subtree_hashes[node.id])
        for child in node.children:
            walk(child)

    walk(root)
    return {
        cluster_id: _hash_payload(sorted(node_hashes))
        for cluster_id, node_hashes in members.items()
    }


@dataclass(frozen=True)
class RegionSyncState:
    """Region hashes computed from the current clean design tree."""

    subtree_hashes: dict[str, str]
    layout_region_hash: str
    cluster_hashes: dict[str, str]

    @classmethod
    def from_tree(cls, root: CleanDesignTreeNode) -> RegionSyncState:
        """Build region sync state for a clean design tree root."""
        subtree_hashes = collect_subtree_hashes(root)
        return cls(
            subtree_hashes=subtree_hashes,
            layout_region_hash=layout_region_hash(root),
            cluster_hashes=compute_cluster_hashes(root, subtree_hashes),
        )


@dataclass(frozen=True)
class IncrementalFileBindings:
    """Maps generated file paths to layout regions for incremental writes."""

    widget_files: dict[str, str] = field(default_factory=dict)
    layout_path: str | None = None
    screen_paths: frozenset[str] = frozenset()
    theme_prefix: str = "lib/theme/"


def build_incremental_bindings(
    *,
    clean_tree: CleanDesignTreeNode,
    cluster_summary: dict[str, int],
    feature_name: str,
    planned_files: dict[str, str],
    cluster_min_count: int,
    widget_suffix: str,
    enforce_cluster_widgets: bool,
    architecture: Architecture = "feature_first",
) -> IncrementalFileBindings:
    """Derive which planned paths map to cluster widgets vs layout shell.

    Args:
        clean_tree: Parsed design tree root.
        cluster_summary: Structural and component cluster counts.
        feature_name: Resolved snake_case feature name.
        planned_files: All paths that would be written on a full run.
        cluster_min_count: Minimum cluster size for widget extraction.
        widget_suffix: Widget class suffix from agent naming config.
        enforce_cluster_widgets: Whether cluster widget files are generated.
        architecture: Project layout architecture for resolving screen paths.

    Returns:
        File path bindings for region-aware incremental sync.
    """
    widget_files: dict[str, str] = {}
    if enforce_cluster_widgets and cluster_summary:
        specs = collect_cluster_widget_specs(
            clean_tree,
            cluster_summary,
            min_count=cluster_min_count,
            widget_suffix=widget_suffix,
        )
        widget_files = {f"lib/widgets/{spec.file_name}.dart": spec.cluster_id for spec in specs}

    layout_candidate = f"lib/generated/{feature_name}_layout.dart"
    layout_path: str | None = layout_candidate if layout_candidate in planned_files else None

    primary_screen = screen_file_path(feature_name, architecture=architecture)
    screen_paths = frozenset({primary_screen}) if primary_screen in planned_files else frozenset()

    return IncrementalFileBindings(
        widget_files=widget_files,
        layout_path=layout_path,
        screen_paths=frozenset(screen_paths),
    )


def changed_cluster_ids(
    previous: dict[str, str],
    current: dict[str, str],
) -> set[str]:
    """Return cluster ids whose aggregated subtree hash changed."""
    all_ids = set(previous) | set(current)
    return {
        cluster_id for cluster_id in all_ids if previous.get(cluster_id) != current.get(cluster_id)
    }
