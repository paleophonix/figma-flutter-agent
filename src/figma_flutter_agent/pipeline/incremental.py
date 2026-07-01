"""Incremental sync helpers for the generation pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from figma_flutter_agent.config import Settings
from figma_flutter_agent.generator.ir.version import EMITTER_VERSION
from figma_flutter_agent.schemas import CleanDesignTreeNode, DesignTokens
from figma_flutter_agent.stages import SnapshotStageRequest, persist_generation_snapshot
from figma_flutter_agent.sync import (
    GenerationSnapshot,
    SnapshotLoadOutcome,
    hash_clean_tree,
    hash_file_contents,
    hash_tokens,
    load_snapshot,
    select_files_for_sync,
)
from figma_flutter_agent.sync.regions import (
    IncrementalFileBindings,
    RegionSyncState,
    build_incremental_bindings,
)


@dataclass(frozen=True)
class DesignHashState:
    """Hashes used for incremental sync decisions."""

    tree_hash: str
    colors_hash: str
    typography_hash: str
    spacing_hash: str


@dataclass(frozen=True)
class IncrementalContext:
    """Loaded incremental sync state for a pipeline run."""

    previous_snapshot: GenerationSnapshot | None
    tree_changed: bool
    tokens_changed: bool


def design_hashes(clean_tree: CleanDesignTreeNode, tokens: DesignTokens) -> DesignHashState:
    """Compute design-tree and token group hashes."""
    colors_hash, typography_hash, spacing_hash = hash_tokens(tokens)
    return DesignHashState(
        tree_hash=hash_clean_tree(clean_tree),
        colors_hash=colors_hash,
        typography_hash=typography_hash,
        spacing_hash=spacing_hash,
    )


def load_incremental_context(
    project_dir: Path,
    settings: Settings,
    *,
    resolved_sync: bool,
    hashes: DesignHashState,
    feature_name: str,
) -> tuple[IncrementalContext, list[str]]:
    """Load snapshot metadata and derive change flags.

    Returns:
        Tuple of incremental context and warning messages to append.
    """
    if not resolved_sync:
        return (
            IncrementalContext(previous_snapshot=None, tree_changed=True, tokens_changed=True),
            [],
        )

    outcome = load_snapshot(
        project_dir,
        feature_name,
        fail_on_corrupt=settings.agent.sync.fail_on_corrupt_snapshot,
    )
    warnings = _quarantine_warnings(outcome)
    previous = outcome.snapshot
    tree_changed = previous is None or previous.tree_hash != hashes.tree_hash
    tokens_changed = previous is None or (
        previous.colors_hash != hashes.colors_hash
        or previous.typography_hash != hashes.typography_hash
        or previous.spacing_hash != hashes.spacing_hash
    )
    return (
        IncrementalContext(
            previous_snapshot=previous,
            tree_changed=tree_changed,
            tokens_changed=tokens_changed,
        ),
        warnings,
    )


def _quarantine_warnings(outcome: SnapshotLoadOutcome) -> list[str]:
    if outcome.quarantined_path is None:
        return []
    return [
        "Corrupt sync snapshot was quarantined; incremental sync will treat this as a full regen. "
        f"See {outcome.quarantined_path}"
    ]


def select_planned_writes(
    *,
    resolved_sync: bool,
    previous_snapshot: GenerationSnapshot | None,
    file_key: str,
    node_id: str,
    hashes: DesignHashState,
    planned_files: dict[str, str],
    regenerate_templates: bool,
    settings: Settings | None = None,
    clean_tree: CleanDesignTreeNode | None = None,
    cluster_summary: dict[str, int] | None = None,
    feature_name: str | None = None,
    force_screen_regen: bool = False,
    project_dir: Path | None = None,
) -> dict[str, str]:
    """Return the subset of planned files that should be written this run."""
    if not resolved_sync:
        return planned_files

    region_state: RegionSyncState | None = None
    bindings: IncrementalFileBindings | None = None
    if clean_tree is not None and feature_name and settings is not None:
        region_state = RegionSyncState.from_tree(clean_tree)
        generation = settings.agent.generation
        bindings = build_incremental_bindings(
            clean_tree=clean_tree,
            cluster_summary=cluster_summary or {},
            feature_name=feature_name,
            planned_files=planned_files,
            cluster_min_count=generation.cluster_min_count,
            widget_suffix=settings.agent.naming.widget_suffix,
            enforce_cluster_widgets=generation.enforce_cluster_widgets,
            widget_extraction=generation.widget_extraction,
            architecture=settings.agent.flutter.architecture,
        )

    return select_files_for_sync(
        previous_snapshot,
        file_key=file_key,
        node_id=node_id,
        tree_hash=hashes.tree_hash,
        colors_hash=hashes.colors_hash,
        typography_hash=hashes.typography_hash,
        spacing_hash=hashes.spacing_hash,
        planned_files=planned_files,
        regenerate_templates=regenerate_templates,
        region_state=region_state,
        bindings=bindings,
        force_screen_regen=force_screen_regen,
        project_dir=project_dir,
    )


def should_skip_snapshot_persist(
    *,
    previous_snapshot: GenerationSnapshot | None,
    files_to_write: dict[str, str],
    hashes: DesignHashState,
    planned_files: dict[str, str],
    region_state: RegionSyncState | None = None,
) -> bool:
    """Return True when snapshot metadata on disk is already up to date."""
    if previous_snapshot is None:
        return False
    if files_to_write:
        return False
    planned_hashes = {path: hash_file_contents(content) for path, content in planned_files.items()}
    regions_unchanged = True
    if region_state is not None and previous_snapshot.layout_region_hash:
        regions_unchanged = (
            previous_snapshot.layout_region_hash == region_state.layout_region_hash
            and previous_snapshot.cluster_hashes == region_state.cluster_hashes
        )
    return (
        previous_snapshot.file_hashes == planned_hashes
        and previous_snapshot.tree_hash == hashes.tree_hash
        and previous_snapshot.colors_hash == hashes.colors_hash
        and previous_snapshot.typography_hash == hashes.typography_hash
        and previous_snapshot.spacing_hash == hashes.spacing_hash
        and previous_snapshot.emitter_version == EMITTER_VERSION
        and regions_unchanged
    )


def maybe_persist_snapshot(
    log: Any,
    *,
    project_dir: Path,
    resolved_sync: bool,
    file_key: str,
    node_id: str,
    feature_name: str,
    hashes: DesignHashState,
    planned_files: dict[str, str],
    files_to_write: dict[str, str],
    previous_snapshot: GenerationSnapshot | None,
    reference_image_hash: str | None,
    clean_tree: CleanDesignTreeNode | None = None,
) -> None:
    """Persist snapshot when sync is enabled and metadata changed."""
    if not resolved_sync:
        return
    region_state = RegionSyncState.from_tree(clean_tree) if clean_tree is not None else None
    if should_skip_snapshot_persist(
        previous_snapshot=previous_snapshot,
        files_to_write=files_to_write,
        hashes=hashes,
        planned_files=planned_files,
        region_state=region_state,
    ):
        log.info("Incremental sync: snapshot unchanged, skipping persist")
        return
    persist_generation_snapshot(
        SnapshotStageRequest(
            project_dir=project_dir,
            file_key=file_key,
            node_id=node_id,
            feature_name=feature_name,
            tree_hash=hashes.tree_hash,
            colors_hash=hashes.colors_hash,
            typography_hash=hashes.typography_hash,
            spacing_hash=hashes.spacing_hash,
            planned_files=planned_files,
            layout_region_hash=region_state.layout_region_hash if region_state else "",
            cluster_hashes=region_state.cluster_hashes if region_state else {},
            reference_image_hash=reference_image_hash,
            expected_snapshot_version=(
                previous_snapshot.version if previous_snapshot is not None else None
            ),
        )
    )
