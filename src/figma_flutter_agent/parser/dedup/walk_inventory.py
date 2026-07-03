"""Critical clean-tree walk inventory (04-P0-1)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

WalkStatus = Literal["migrated", "safe_snapshot", "explicit_path_guard", "pending"]

INVENTORY_JSON_REL = (
    "docs/refactor/26-06-06-compiler-refactor/generated/dedup-walk-inventory.json"
)


@dataclass(frozen=True, slots=True)
class WalkSiteRecord:
    """One inventoried clean-tree walk site."""

    module: str
    symbol: str
    phase: str
    status: WalkStatus
    mechanism: str
    note: str = ""


_WALK_SITES: tuple[WalkSiteRecord, ...] = (
    WalkSiteRecord(
        module="parser/dedup/prune.py",
        symbol="prune_extracted_subtree_nodes",
        phase="dedup_prune_extracted",
        status="migrated",
        mechanism="walk_clean_tree",
    ),
    WalkSiteRecord(
        module="parser/dedup/prune.py",
        symbol="prune_duplicated_cluster_subtrees",
        phase="dedup_prune_clusters",
        status="migrated",
        mechanism="walk_clean_tree_with_parent",
    ),
    WalkSiteRecord(
        module="parser/dedup/hydrate.py",
        symbol="hydrate_pruned_cluster_instances",
        phase="dedup_hydrate_collect",
        status="migrated",
        mechanism="walk_clean_tree",
    ),
    WalkSiteRecord(
        module="parser/dedup/clusters.py",
        symbol="assign_structural_clusters",
        phase="dedup_cluster_collect",
        status="migrated",
        mechanism="walk_clean_tree",
    ),
    WalkSiteRecord(
        module="parser/dedup/clusters.py",
        symbol="assign_component_clusters",
        phase="dedup_component_cluster",
        status="migrated",
        mechanism="walk_clean_tree",
    ),
    WalkSiteRecord(
        module="parser/dedup/signatures.py",
        symbol="descendant_text_fingerprint",
        phase="dedup_signature_text",
        status="migrated",
        mechanism="walk_clean_tree",
    ),
    WalkSiteRecord(
        module="parser/dedup/signatures.py",
        symbol="node_signature_payload",
        phase="dedup_signature_structural",
        status="safe_snapshot",
        mechanism="recursive_json_payload",
        note="Bounded by tree depth; cycle raises via parent walks first",
    ),
    WalkSiteRecord(
        module="generator/extraction/asset_index.py",
        symbol="build_asset_node_index",
        phase="asset_index",
        status="migrated",
        mechanism="walk_clean_tree",
    ),
    WalkSiteRecord(
        module="parser/boundaries/assets.py",
        symbol="asset_boundary_walks",
        phase="assets_boundary",
        status="pending",
        mechanism="audit_required",
        note="Migrate or document explicit path guard in follow-up PR",
    ),
)


def list_walk_sites() -> tuple[WalkSiteRecord, ...]:
    """Return the canonical walk inventory."""
    return _WALK_SITES


def inventory_to_json(records: tuple[WalkSiteRecord, ...] | None = None) -> str:
    """Serialize inventory deterministically."""
    items = records if records is not None else _WALK_SITES
    payload = [asdict(item) for item in items]
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def write_walk_inventory(*, path: Path | None = None) -> tuple[WalkSiteRecord, ...]:
    """Write machine-readable walk inventory JSON."""
    repo_root = Path(__file__).resolve().parents[4]
    target = path or (repo_root / INVENTORY_JSON_REL)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(inventory_to_json(), encoding="utf-8")
    return _WALK_SITES
