"""Diff engine for incremental sync."""

from __future__ import annotations

from figma_flutter_agent.generator.renderer_theme import expand_theme_bundle_writes
from figma_flutter_agent.sync.regions import (
    IncrementalFileBindings,
    RegionSyncState,
    changed_cluster_ids,
)
from figma_flutter_agent.sync.snapshot import GenerationSnapshot, hash_file_contents

_THEME_PREFIX = "lib/theme/"


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
) -> dict[str, str]:
    """Select files using layout-region and cluster hashes (spec §16 widget granularity)."""
    cluster_delta = changed_cluster_ids(snapshot.cluster_hashes, region_state.cluster_hashes)
    layout_changed = snapshot.layout_region_hash != region_state.layout_region_hash

    selected: dict[str, str] = {}
    for path, content in planned_files.items():
        if path.startswith(bindings.theme_prefix):
            if tokens_changed or snapshot.file_hashes.get(path) != hash_file_contents(content):
                selected[path] = content
            continue

        cluster_id = bindings.widget_files.get(path)
        if cluster_id is not None:
            if cluster_id in cluster_delta:
                selected[path] = content
            continue

        if bindings.layout_path is not None and path == bindings.layout_path:
            if layout_changed:
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

    Returns:
        Filtered mapping of relative file paths to generated contents.
    """
    if snapshot is None:
        return dict(planned_files)

    if snapshot.file_key != file_key or snapshot.node_id != node_id:
        return dict(planned_files)

    if regenerate_templates:
        return dict(planned_files)

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

    return expand_theme_bundle_writes(selected, planned_files)
