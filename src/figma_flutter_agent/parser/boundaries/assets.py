"""Asset lookup and export planning for render boundaries."""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from figma_flutter_agent.schemas import AssetManifest, CleanDesignTreeNode


def render_boundary_asset_path(node_id: str) -> str:
    """Relative Flutter asset path reserved for a render-boundary SVG export."""
    safe_id = node_id.replace(":", "_")
    return f"assets/illustrations/render_boundary_{safe_id}.svg"


def discover_asset_path_for_node(project_dir: Path, node_id: str) -> str | None:
    """Find an on-disk SVG/PNG export for a Figma node id (any filename suffix)."""
    suffix = node_id.replace(":", "_")
    for folder in ("icons", "illustrations", "images"):
        asset_dir = project_dir / "assets" / folder
        if not asset_dir.is_dir():
            continue
        for pattern in (
            f"*_{suffix}.svg",
            f"*_{suffix}.png",
            f"render_boundary_{suffix}.svg",
        ):
            matches = sorted(asset_dir.glob(pattern))
            if matches:
                return f"assets/{folder}/{matches[0].name}"
    return None


def resolve_pruned_cluster_instance_assets(
    tree: CleanDesignTreeNode,
    project_dir: Path,
    manifest: AssetManifest | None = None,
) -> None:
    """Attach per-instance vector exports onto pruned duplicate cluster nodes."""
    manifest_paths: dict[str, str] = {}
    if manifest is not None:
        for entry in manifest.entries:
            if entry.kind in {"icon", "illustration", "image"}:
                manifest_paths.setdefault(entry.node_id, entry.asset_path)

    def candidate_paths(node_id: str) -> list[str]:
        paths: list[str] = []
        manifest_path = manifest_paths.get(node_id)
        if manifest_path:
            paths.append(manifest_path)
        discovered = discover_asset_path_for_node(project_dir, node_id)
        if discovered and discovered not in paths:
            paths.append(discovered)
        return paths

    def walk(node: CleanDesignTreeNode) -> None:
        if node.cluster_id and not node.children:
            resolved: str | None = None
            for node_id in node.flatten_figma_node_ids or ():
                for candidate in candidate_paths(node_id):
                    if (project_dir / Path(candidate)).is_file():
                        resolved = candidate.replace("\\", "/")
                        break
                if resolved is not None:
                    break
            if resolved is None:
                for candidate in candidate_paths(node.id):
                    if (project_dir / Path(candidate)).is_file():
                        resolved = candidate.replace("\\", "/")
                        break
            if resolved is not None:
                node.vector_asset_key = resolved
        for child in node.children:
            walk(child)

    walk(tree)


def resolve_render_boundary_asset_keys(
    tree: CleanDesignTreeNode,
    project_dir: Path,
    manifest: AssetManifest | None = None,
    *,
    strict: bool = False,
) -> list[str]:
    """Map render-boundary nodes to existing exports; return ids still missing on disk."""
    manifest_paths: dict[str, str] = {}
    if manifest is not None:
        for entry in manifest.entries:
            manifest_paths.setdefault(entry.node_id, entry.asset_path)

    unresolved: list[str] = []

    def walk(node: CleanDesignTreeNode) -> None:
        if not node.render_boundary:
            for child in node.children:
                walk(child)
            return
        candidates: list[str] = []
        manifest_path = manifest_paths.get(node.id)
        if manifest_path:
            candidates.append(manifest_path)
        reserved = render_boundary_asset_path(node.id)
        if reserved not in candidates:
            candidates.append(reserved)
        discovered = discover_asset_path_for_node(project_dir, node.id)
        if discovered and discovered not in candidates:
            candidates.append(discovered)
        for candidate in candidates:
            if (project_dir / Path(candidate)).is_file():
                node.vector_asset_key = candidate.replace("\\", "/")
                break
        else:
            unresolved.append(node.id)
        for child in node.children:
            walk(child)

    walk(tree)
    if unresolved:
        if strict:
            from figma_flutter_agent.errors import GenerationError

            raise GenerationError(
                "Render-boundary asset(s) missing on disk: "
                + ", ".join(sorted(unresolved))
            )
        logger.warning(
            "Render-boundary asset(s) missing on disk ({}); emit may use placeholder",
            ", ".join(sorted(unresolved)),
        )
    return unresolved


def collect_render_boundary_asset_plan(
    root: CleanDesignTreeNode,
) -> tuple[frozenset[str], frozenset[str]]:
    """Return boundary export ids and flattened descendant ids excluded from per-vector export."""
    export_ids: set[str] = set()
    exclude_ids: set[str] = set()

    def walk(node: CleanDesignTreeNode) -> None:
        if node.render_boundary:
            export_ids.add(node.id)
            for flattened_id in node.flatten_figma_node_ids or ():
                exclude_ids.add(flattened_id)
        for child in node.children:
            walk(child)

    walk(root)
    return frozenset(export_ids), frozenset(exclude_ids)
