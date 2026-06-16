"""Diff engine for incremental sync."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.generator.ir.version import EMITTER_VERSION
from figma_flutter_agent.generator.renderer_theme import expand_theme_bundle_writes
from figma_flutter_agent.sync.regions import (
    IncrementalFileBindings,
    RegionSyncState,
    changed_cluster_ids,
)
from figma_flutter_agent.sync.snapshot import GenerationSnapshot, hash_file_contents

_THEME_PREFIX = "lib/theme/"


def _read_disk_file_hash(project_dir: Path, rel_path: str) -> str | None:
    """Return the content hash for a project file, or ``None`` when absent/unreadable."""
    disk_path = project_dir / Path(rel_path)
    if not disk_path.is_file():
        return None
    try:
        return hash_file_contents(disk_path.read_text(encoding="utf-8"))
    except OSError:
        return None


def _apply_disk_planned_drift(
    selected: dict[str, str],
    planned_files: dict[str, str],
    project_dir: Path | None,
    *,
    snapshot: GenerationSnapshot | None = None,
) -> dict[str, str]:
    """Force writes when on-disk project files diverge from planned emit.

    Snapshot metadata can match planned content while the Flutter project tree
    still holds a stale fossil (partial write, manual edit, or debug deploy).
    Only applies when incremental selection skipped the path but the snapshot
    already records the planned hash (fossil on disk).
    """
    if project_dir is None:
        return selected
    updated = dict(selected)
    for path, content in planned_files.items():
        if path in selected:
            continue
        planned_hash = hash_file_contents(content)
        if snapshot is not None and snapshot.file_hashes.get(path) != planned_hash:
            continue
        disk_hash = _read_disk_file_hash(project_dir, path)
        if disk_hash is None or disk_hash == planned_hash:
            continue
        updated[path] = content
    return updated


def _token_hashes_changed(
    snapshot: GenerationSnapshot,
    *,
    colors_hash: str,
    typography_hash: str,
    spacing_hash: str,
) -> bool:
    return (
        snapshot.colors_hash != colors_hash
        or snapshot.typography_hash != typography_hash
        or snapshot.spacing_hash != spacing_hash
    )


def _select_by_file_hash(
    snapshot: GenerationSnapshot,
    planned_files: dict[str, str],
) -> dict[str, str]:
    selected: dict[str, str] = {}
    for path, content in planned_files.items():
        new_hash = hash_file_contents(content)
        if snapshot.file_hashes.get(path) != new_hash:
            selected[path] = content
    return selected


def _select_by_regions(
    snapshot: GenerationSnapshot,
    *,
    planned_files: dict[str, str],
    region_state: RegionSyncState,
    bindings: IncrementalFileBindings,
    tokens_changed: bool,
    tree_hash: str,
) -> dict[str, str]:
    """Select files using layout-region and cluster hashes (spec §16 widget granularity)."""
    cluster_delta = changed_cluster_ids(
        snapshot.cluster_hashes, region_state.cluster_hashes
    )
    layout_changed = snapshot.layout_region_hash != region_state.layout_region_hash

    selected: dict[str, str] = {}
    for path, content in planned_files.items():
        if path.startswith(bindings.theme_prefix):
            if tokens_changed or snapshot.file_hashes.get(path) != hash_file_contents(
                content
            ):
                selected[path] = content
            continue

        cluster_id = bindings.widget_files.get(path)
        if cluster_id is not None:
            if cluster_id in cluster_delta:
                selected[path] = content
            continue

        if bindings.layout_path is not None and path == bindings.layout_path:
            new_hash = hash_file_contents(content)
            emitter_only_layout_drift = (
                snapshot.tree_hash == tree_hash
                and snapshot.file_hashes.get(path) != new_hash
            )
            emitter_version_drift = snapshot.emitter_version != EMITTER_VERSION
            if layout_changed or emitter_only_layout_drift or emitter_version_drift:
                selected[path] = content
            continue

        if path in bindings.screen_paths:
            new_hash = hash_file_contents(content)
            if layout_changed or snapshot.file_hashes.get(path) != new_hash:
                selected[path] = content
            continue

        new_hash = hash_file_contents(content)
        if snapshot.file_hashes.get(path) != new_hash:
            selected[path] = content

    return selected


def select_files_for_sync(
    snapshot: GenerationSnapshot | None,
    *,
    file_key: str,
    node_id: str,
    tree_hash: str,
    colors_hash: str,
    typography_hash: str,
    spacing_hash: str,
    planned_files: dict[str, str],
    regenerate_templates: bool = False,
    region_state: RegionSyncState | None = None,
    bindings: IncrementalFileBindings | None = None,
    force_screen_regen: bool = False,
    project_dir: Path | None = None,
) -> dict[str, str]:
    """Select generated files that should be written during incremental sync.

    When ``region_state`` and ``bindings`` are provided and the snapshot stores
    ``layout_region_hash`` / ``cluster_hashes``, only cluster widget files whose
    subtrees changed and layout/screen files whose shell tree changed are selected.
    Otherwise falls back to per-file content hashes.

    Args:
        snapshot: Previous snapshot, if any.
        file_key: Current Figma file key.
        node_id: Current Figma node id.
        tree_hash: Hash of the current clean design tree.
        colors_hash: Hash of current color tokens.
        typography_hash: Hash of current typography tokens.
        spacing_hash: Hash of current spacing tokens.
        planned_files: All files that would be written on a full run.
        regenerate_templates: When True, rewrite every planned file.
        region_state: Optional per-region hashes from the current clean tree.
        bindings: Optional mapping of planned paths to cluster/layout regions.
        force_screen_regen: When True, always rewrite bound screen shell files.
        project_dir: Flutter project root; when set, also rewrite files whose on-disk
            content hash differs from the planned emit.

    Returns:
        Filtered mapping of relative file paths to generated contents.
    """
    if snapshot is None:
        return _apply_disk_planned_drift(
            dict(planned_files), planned_files, project_dir, snapshot=None
        )

    if snapshot.file_key != file_key or snapshot.node_id != node_id:
        return _apply_disk_planned_drift(
            dict(planned_files), planned_files, project_dir, snapshot=snapshot
        )

    if regenerate_templates:
        return _apply_disk_planned_drift(
            dict(planned_files), planned_files, project_dir, snapshot=snapshot
        )

    tokens_changed = _token_hashes_changed(
        snapshot,
        colors_hash=colors_hash,
        typography_hash=typography_hash,
        spacing_hash=spacing_hash,
    )

    use_regions = (
        region_state is not None
        and bindings is not None
        and bool(snapshot.layout_region_hash or snapshot.cluster_hashes)
    )
    if use_regions:
        assert region_state is not None
        assert bindings is not None
        selected = _select_by_regions(
            snapshot,
            planned_files=planned_files,
            region_state=region_state,
            bindings=bindings,
            tokens_changed=tokens_changed,
            tree_hash=tree_hash,
        )
    else:
        selected = _select_by_file_hash(snapshot, planned_files)

    tree_unchanged = snapshot.tree_hash == tree_hash
    if tree_unchanged and tokens_changed:
        for path, content in planned_files.items():
            if path.startswith(_THEME_PREFIX):
                selected[path] = content

    if force_screen_regen and bindings is not None:
        for path in bindings.screen_paths:
            if path in planned_files:
                selected[path] = planned_files[path]

    selected = _apply_disk_planned_drift(
        selected, planned_files, project_dir, snapshot=snapshot
    )
    return expand_theme_bundle_writes(selected, planned_files)
