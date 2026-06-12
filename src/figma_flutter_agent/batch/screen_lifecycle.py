"""Purge and copy per-screen Flutter project artifacts (lib, assets, debug)."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from figma_flutter_agent.assets.collect import collect_exportable_nodes
from figma_flutter_agent.assets.screen_frame import (
    build_screen_frame_exclude_ids,
    node_id_from_asset_stem,
)
from figma_flutter_agent.batch.models import BatchManifest, ScreenEntry
from figma_flutter_agent.batch.run import _resolve_dump
from figma_flutter_agent.debug.fidelity import fidelity_report_path
from figma_flutter_agent.debug.paths import (
    FIGMA_DEBUG_DIR,
    dart_debug_snapshot_path,
    emitter_reference_bundle_path,
    processed_dump_path,
    raw_dump_path,
)
from figma_flutter_agent.debug.provenance import provenance_dump_path
from figma_flutter_agent.debug.semantics import semantics_report_path
from figma_flutter_agent.generator.paths import (
    Architecture,
    screen_file_path,
    state_file_path,
)
from figma_flutter_agent.validation.golden_capture.paths import (
    capture_test_relative_path,
    golden_figma_keys_relative_path,
    golden_png_relative_path,
    golden_test_relative_path,
)

_WIDGET_IMPORT_RE = re.compile(
    r"""import\s+['"](?:package:[^'"]+/widgets/|\.\./(?:\.\./)*widgets/)([^'"]+)\.dart['"]"""
)
_ASSET_KINDS_WITH_FILES = frozenset({"icon", "image", "illustration", "boundary_svg"})


@dataclass(frozen=True)
class ScreenArtifactSummary:
    """Counts of on-disk artifacts tied to one manifest screen."""

    lib_paths: tuple[Path, ...]
    widget_paths: tuple[Path, ...]
    asset_paths: tuple[Path, ...]
    debug_paths: tuple[Path, ...]
    test_paths: tuple[Path, ...]

    @property
    def total_files(self) -> int:
        return (
            len(self.lib_paths)
            + len(self.widget_paths)
            + len(self.asset_paths)
            + len(self.debug_paths)
            + len(self.test_paths)
        )


def resolve_project_architecture(project_dir: Path) -> Architecture:
    """Load ``flutter.architecture`` from the project agent config."""
    from figma_flutter_agent.config import load_settings
    from figma_flutter_agent.dev.project import ensure_project_config, is_flutter_project_root

    if not is_flutter_project_root(project_dir):
        return "feature_first"
    config_path = ensure_project_config(project_dir)
    return load_settings(config_path).agent.flutter.architecture


def collect_screen_artifacts(
    manifest: BatchManifest,
    feature: str,
    *,
    architecture: Architecture | None = None,
    remaining_features: frozenset[str] | None = None,
) -> ScreenArtifactSummary:
    """List lib, widget, asset, debug, and test paths owned by one screen slug.

    Args:
        manifest: Batch manifest for the Flutter project.
        feature: Screen feature slug to inspect.
        architecture: Optional layout architecture override.
        remaining_features: Other manifest slugs kept on disk; shared assets are retained.

    Returns:
        Grouped absolute paths that a purge or copy operation would touch.
    """
    screen = _find_screen(manifest, feature)
    project_dir = manifest.project_dir
    arch = architecture or resolve_project_architecture(project_dir)
    remaining = remaining_features
    if remaining is None:
        remaining = frozenset(
            item.feature for item in manifest.screens if item.feature != feature
        )
    return ScreenArtifactSummary(
        lib_paths=tuple(_collect_lib_paths(project_dir, feature, arch)),
        widget_paths=tuple(
            _collect_exclusive_widget_paths(project_dir, feature, arch, remaining)
        ),
        asset_paths=tuple(
            _collect_removable_asset_paths(manifest, screen, remaining_features=remaining)
        ),
        debug_paths=tuple(_collect_debug_paths(project_dir, feature)),
        test_paths=tuple(_collect_test_paths(project_dir, feature)),
    )


def purge_screen_artifacts(
    manifest: BatchManifest,
    feature: str,
    *,
    architecture: Architecture | None = None,
) -> ScreenArtifactSummary:
    """Delete lib, widgets, assets, debug, and test artifacts for one screen slug.

    Args:
        manifest: Batch manifest (screen may still be listed or already removed).
        feature: Feature slug to purge from disk.
        architecture: Optional layout architecture override.

    Returns:
        Summary of deleted paths for logging.
    """
    remaining = frozenset(
        item.feature for item in manifest.screens if item.feature != feature
    )
    summary = collect_screen_artifacts(
        manifest,
        feature,
        architecture=architecture,
        remaining_features=remaining,
    )
    deleted_dirs: set[Path] = set()
    for path in (
        *summary.lib_paths,
        *summary.widget_paths,
        *summary.asset_paths,
        *summary.debug_paths,
        *summary.test_paths,
    ):
        if not path.exists():
            continue
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
            deleted_dirs.add(path)
            continue
        path.unlink(missing_ok=True)
        deleted_dirs.add(path.parent)

    arch = architecture or resolve_project_architecture(manifest.project_dir)
    feature_dir = _feature_lib_directory(manifest.project_dir, feature, arch)
    if feature_dir is not None and feature_dir.is_dir() and not any(feature_dir.iterdir()):
        feature_dir.rmdir()

    _purge_sync_snapshot_for_feature(manifest.project_dir, feature)
    logger.info(
        "Purged screen {} artifacts ({} files)",
        feature,
        summary.total_files,
    )
    return summary


def copy_screen_to_project(
    source_manifest: BatchManifest,
    feature: str,
    target_project_dir: Path,
    *,
    architecture: Architecture | None = None,
    overwrite: bool = False,
) -> ScreenArtifactSummary:
    """Copy one screen and its artifacts into another Flutter project.

    Args:
        source_manifest: Manifest for the source Flutter project.
        feature: Feature slug to copy.
        target_project_dir: Destination Flutter project root.
        architecture: Optional layout architecture override for source paths.
        overwrite: When False, raise if the target already has the same slug or files.

    Returns:
        Summary of copied paths.

    Raises:
        ValueError: When the screen is missing, the target manifest already lists the slug,
            or ``overwrite`` is False and destination files exist.
        FileNotFoundError: When the target project has no ``screens.yaml``.
    """
    screen = _find_screen(source_manifest, feature)
    source_dir = source_manifest.project_dir
    arch = architecture or resolve_project_architecture(source_dir)
    summary = collect_screen_artifacts(
        source_manifest,
        feature,
        architecture=arch,
        remaining_features=frozenset(),
    )

    target_manifest_path = target_project_dir / "screens.yaml"
    if not target_manifest_path.is_file():
        msg = f"Target project has no screens.yaml at {target_manifest_path.as_posix()}"
        raise FileNotFoundError(msg)

    from figma_flutter_agent.batch.manifest import load_batch_manifest, write_batch_manifest

    target_manifest = load_batch_manifest(target_manifest_path)
    if any(item.feature == feature for item in target_manifest.screens):
        if not overwrite:
            msg = f"Target manifest already lists screen {feature!r}"
            raise ValueError(msg)
    else:
        dump_rel = raw_dump_path(target_project_dir, feature).relative_to(target_project_dir)
        new_entry = ScreenEntry(
            feature=screen.feature,
            node_id=screen.node_id,
            dump=target_project_dir / dump_rel,
            figma_url=screen.figma_url,
        )
        write_batch_manifest(
            target_manifest_path,
            BatchManifest(
                file_key=target_manifest.file_key or source_manifest.file_key,
                project_dir=target_project_dir,
                screens=target_manifest.screens + (new_entry,),
                figma_file_url=target_manifest.figma_file_url or source_manifest.figma_file_url,
            ),
        )

    for path in (
        *summary.lib_paths,
        *summary.widget_paths,
        *summary.asset_paths,
        *summary.debug_paths,
        *summary.test_paths,
    ):
        if not path.is_file():
            continue
        rel = path.relative_to(source_dir)
        destination = target_project_dir / rel
        if destination.is_file() and not overwrite:
            msg = f"Refusing to overwrite existing file {destination.as_posix()}"
            raise ValueError(msg)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)

    logger.info(
        "Copied screen {} to {} ({} files)",
        feature,
        target_project_dir.as_posix(),
        summary.total_files,
    )
    return summary


def format_purge_summary(feature: str, summary: ScreenArtifactSummary) -> str:
    """Return a short human-readable purge/copy summary."""
    return (
        f"{feature}: {summary.total_files} file(s) — "
        f"lib {len(summary.lib_paths)}, widgets {len(summary.widget_paths)}, "
        f"assets {len(summary.asset_paths)}, debug {len(summary.debug_paths)}, "
        f"tests {len(summary.test_paths)}"
    )


def _find_screen(manifest: BatchManifest, feature: str) -> ScreenEntry:
    for screen in manifest.screens:
        if screen.feature == feature:
            return screen
    msg = f"Screen {feature!r} is not in the manifest."
    raise ValueError(msg)


def _feature_lib_directory(
    project_dir: Path,
    feature: str,
    architecture: Architecture,
) -> Path | None:
    if architecture == "feature_first":
        return project_dir / "lib" / "features" / feature
    return None


def _collect_lib_paths(
    project_dir: Path,
    feature: str,
    architecture: Architecture,
) -> list[Path]:
    paths: list[Path] = []
    feature_dir = _feature_lib_directory(project_dir, feature, architecture)
    if feature_dir is not None and feature_dir.is_dir():
        paths.extend(sorted(path for path in feature_dir.rglob("*") if path.is_file()))
    for rel in (
        screen_file_path(feature, architecture=architecture),
        state_file_path(feature, architecture=architecture),
        f"lib/generated/{feature}_layout.dart",
    ):
        path = project_dir / rel
        if path.is_file() and path not in paths:
            paths.append(path)
    return paths


def _collect_debug_paths(project_dir: Path, feature: str) -> list[Path]:
    paths: list[Path] = []
    for resolver in (raw_dump_path, processed_dump_path, emitter_reference_bundle_path):
        path = resolver(project_dir, feature)
        if path.is_file():
            paths.append(path)

    for snapshot in ("plan", "final", "bug"):
        path = dart_debug_snapshot_path(project_dir, feature, snapshot)
        if path.is_file():
            paths.append(path)

    provenance_path = provenance_dump_path(project_dir, feature)
    if provenance_path.is_file():
        paths.append(provenance_path)

    semantics_path = project_dir / semantics_report_path(feature)
    if semantics_path.is_file():
        paths.append(semantics_path)

    fidelity_path = project_dir / fidelity_report_path(feature)
    if fidelity_path.is_file():
        paths.append(fidelity_path)

    debug_root = project_dir / FIGMA_DEBUG_DIR
    if debug_root.is_dir():
        for subdir, pattern in (
            ("ir", f"{feature}_*.json"),
            ("reports", f"{feature}_*.json"),
            ("reference/emitter", f"{feature}*"),
            ("reference/figma", f"{feature}*"),
            ("perf", f"*{feature}*"),
        ):
            target = debug_root / subdir
            if target.is_dir():
                paths.extend(sorted(target.glob(pattern)))

    deduped: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            deduped.append(path)
    return deduped


def _collect_test_paths(project_dir: Path, feature: str) -> list[Path]:
    paths: list[Path] = []
    for rel in (
        golden_test_relative_path(feature),
        capture_test_relative_path(feature),
        golden_png_relative_path(feature),
        golden_figma_keys_relative_path(feature),
    ):
        path = project_dir / rel
        if path.is_file():
            paths.append(path)
    return paths


def _collect_exclusive_widget_paths(
    project_dir: Path,
    feature: str,
    architecture: Architecture,
    remaining_features: frozenset[str],
) -> list[Path]:
    owned = _widget_paths_referenced_by_screen(project_dir, feature, architecture)
    if not owned:
        return []
    still_used: set[Path] = set()
    for other in remaining_features:
        still_used.update(
            _widget_paths_referenced_by_screen(project_dir, other, architecture)
        )
    return sorted(path for path in owned if path not in still_used)


def _widget_paths_referenced_by_screen(
    project_dir: Path,
    feature: str,
    architecture: Architecture,
) -> set[Path]:
    stems: set[str] = set()
    for rel in (
        screen_file_path(feature, architecture=architecture),
        f"lib/generated/{feature}_layout.dart",
    ):
        path = project_dir / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        stems.update(_WIDGET_IMPORT_RE.findall(text))
    return {
        (project_dir / "lib" / "widgets" / f"{stem}.dart").resolve()
        for stem in stems
        if (project_dir / "lib" / "widgets" / f"{stem}.dart").is_file()
    }


def _collect_removable_asset_paths(
    manifest: BatchManifest,
    screen: ScreenEntry,
    *,
    remaining_features: frozenset[str],
) -> list[Path]:
    screen_ids = _exportable_node_ids_for_screen(manifest.project_dir, screen)
    if not screen_ids:
        return []
    retained_ids: set[str] = set()
    for other in manifest.screens:
        if other.feature not in remaining_features:
            continue
        retained_ids.update(_exportable_node_ids_for_screen(manifest.project_dir, other))
    removable_ids = screen_ids - retained_ids
    return _asset_paths_for_node_ids(manifest.project_dir, removable_ids)


def _exportable_node_ids_for_screen(project_dir: Path, screen: ScreenEntry) -> set[str]:
    dump_path = _resolve_dump(screen, project_dir)
    if not dump_path.is_file():
        return set()
    root = json.loads(dump_path.read_text(encoding="utf-8"))
    exclude_ids = build_screen_frame_exclude_ids(screen.node_id)
    return {
        node_id
        for node_id, _, kind in collect_exportable_nodes(
            root,
            exclude_node_ids=set(exclude_ids),
        )
        if kind in _ASSET_KINDS_WITH_FILES
    }


def _asset_paths_for_node_ids(project_dir: Path, node_ids: set[str]) -> list[Path]:
    if not node_ids:
        return []
    paths: list[Path] = []
    for directory in ("icons", "images", "illustrations"):
        asset_dir = project_dir / "assets" / directory
        if not asset_dir.is_dir():
            continue
        for path in asset_dir.iterdir():
            if not path.is_file():
                continue
            node_id = node_id_from_asset_stem(path.stem)
            if node_id in node_ids:
                paths.append(path)
    return sorted(paths)


def _purge_sync_snapshot_for_feature(project_dir: Path, feature: str) -> None:
    from figma_flutter_agent.sync.snapshot import load_snapshot, snapshot_path

    outcome = load_snapshot(project_dir)
    snapshot = outcome.snapshot
    if snapshot is None or snapshot.feature_name != feature:
        return
    snapshot_path(project_dir).unlink(missing_ok=True)
