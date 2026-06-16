"""Flutter test project setup and sync for golden capture."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import subprocess
import tempfile
import time
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger
from ruamel.yaml import YAML

from figma_flutter_agent.fixtures.assets import sync_fixture_vector_assets
from figma_flutter_agent.generator.writing.core import DartWriter
from figma_flutter_agent.schemas import CleanDesignTreeNode
from figma_flutter_agent.tools.process_run import FLUTTER_PUB_GET_TIMEOUT_SEC
from figma_flutter_agent.validation.golden_capture.logs import _clip_reason
from figma_flutter_agent.validation.golden_capture.paths import collect_planned_asset_paths
from figma_flutter_agent.validation.golden_capture_enrich import (
    enrich_planned_from_project,
    sync_flutter_test_config,
)

if TYPE_CHECKING:
    from figma_flutter_agent.validation.golden_capture.result import GoldenCaptureResult
    from figma_flutter_agent.validation.golden_capture.warm_runtime import (
        GoldenCaptureTimings,
    )

_FLUTTER_SKELETON = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "flutter_skeleton"
_SKELETON_VERSION = "1"
_FLUTTER_VERSION_SNIPPET: str | None = None
_FLUTTER_TEST_BUILD_SUBDIR = "unit_test_assets"
_WRITE_PROBE_NAME = ".figma_flutter_write_probe"
_BUILD_DIR_CLEAR_RETRIES = 3
_BUILD_DIR_CLEAR_BACKOFF_SEC = 0.25


def _handle_rmtree_readonly(func, path: str, exc_info) -> None:
    """Clear read-only flags on Windows before retrying ``shutil.rmtree``."""
    exc = exc_info[1]
    if not isinstance(exc, OSError) or exc.errno not in {1, 13}:
        raise exc
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _flutter_test_build_probe_dir(project_dir: Path) -> Path:
    """Return the Flutter widget-test asset bundle directory under ``build/``."""
    return project_dir / "build" / _FLUTTER_TEST_BUILD_SUBDIR


def _is_flutter_test_build_dir_writable(project_dir: Path) -> bool:
    """Return True when ``flutter test`` can create/write ``build/unit_test_assets``."""
    probe_dir = _flutter_test_build_probe_dir(project_dir)
    if probe_dir.is_file():
        return False
    try:
        probe_dir.mkdir(parents=True, exist_ok=True)
        probe_file = probe_dir / _WRITE_PROBE_NAME
        probe_file.write_text("ok", encoding="utf-8")
        probe_file.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _ensure_flutter_test_build_dir_hygienic(project_dir: Path) -> bool:
    """Repair stale Flutter test build output. Returns False when still blocked."""
    unit_assets = _flutter_test_build_probe_dir(project_dir)
    if unit_assets.is_file():
        logger.warning("Removing stale file blocking flutter test build: {}", unit_assets)
        try:
            unit_assets.unlink()
        except OSError as exc:
            logger.warning("Could not remove stale build file {}: {}", unit_assets, exc)
    if _is_flutter_test_build_dir_writable(project_dir):
        return True
    logger.warning(
        "Flutter test build dir not writable under {}; clearing build before capture",
        project_dir / "build",
    )
    if not _prepare_flutter_test_build_dir(project_dir):
        return False
    return _is_flutter_test_build_dir_writable(project_dir)


def force_rebootstrap_capture_sandbox(
    capture_dir: Path,
    *,
    flutter: str,
    timings: GoldenCaptureTimings | None = None,
) -> GoldenCaptureResult | None:
    """Wipe and recopy a warm capture sandbox after unrecoverable build corruption.

    Args:
        capture_dir: Persistent warm sandbox root.
        flutter: Resolved Flutter executable.
        timings: Optional timing bucket.

    Returns:
        ``GoldenCaptureResult`` on bootstrap failure, else ``None``.
    """
    capture_dir.parent.mkdir(parents=True, exist_ok=True)
    if capture_dir.is_dir():
        try:
            shutil.rmtree(capture_dir, onerror=_handle_rmtree_readonly)
        except OSError as exc:
            return GoldenCaptureResult(
                reason=_clip_reason(
                    "capture sandbox is locked and cannot be rebuilt "
                    f"({exc}); close other flutter/dart processes and retry View"
                ),
            )
    _copy_skeleton_project(capture_dir)
    _write_skeleton_fingerprint_stamp(capture_dir)
    logger.info("Rebootstrapped warm capture sandbox at {}", capture_dir.as_posix())
    return _run_flutter_pub_get(capture_dir, flutter, timings=timings)


def _pubspec_cache_stamp(workspace: Path) -> Path:
    """Return the on-disk pub get fingerprint stamp path."""
    return workspace / ".dart_tool" / "figma_flutter_agent" / "pubspec.hash"


def _flutter_version_snippet(flutter: str) -> str:
    """Return a stable Flutter SDK version string for pub get cache keys."""
    global _FLUTTER_VERSION_SNIPPET
    if _FLUTTER_VERSION_SNIPPET is not None:
        return _FLUTTER_VERSION_SNIPPET
    try:
        result = subprocess.run(
            [flutter, "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
        first_line = (result.stdout or result.stderr or "").splitlines()
        _FLUTTER_VERSION_SNIPPET = first_line[0] if first_line else "unknown"
    except (OSError, subprocess.TimeoutExpired):
        _FLUTTER_VERSION_SNIPPET = "unknown"
    return _FLUTTER_VERSION_SNIPPET


def _skeleton_fingerprint_stamp(workspace: Path) -> Path:
    """Return on-disk stamp for the Flutter skeleton generation fingerprint."""
    return workspace / ".dart_tool" / "figma_flutter_agent" / "skeleton.fingerprint"


def _compute_skeleton_fingerprint() -> str:
    """Hash skeleton template inputs that require sandbox resync when changed."""
    digest = hashlib.sha256()
    digest.update(_SKELETON_VERSION.encode("utf-8"))
    digest.update(b"\0")
    skeleton_pubspec = _FLUTTER_SKELETON / "pubspec.yaml"
    if skeleton_pubspec.is_file():
        digest.update(skeleton_pubspec.read_bytes())
    return digest.hexdigest()


def _write_skeleton_fingerprint_stamp(workspace: Path) -> None:
    stamp = _skeleton_fingerprint_stamp(workspace)
    stamp.parent.mkdir(parents=True, exist_ok=True)
    stamp.write_text(_compute_skeleton_fingerprint(), encoding="utf-8")


def _sandbox_needs_skeleton_resync(capture_dir: Path) -> bool:
    """Return True when the warm sandbox must be recopied from the skeleton template."""
    if not (capture_dir / "pubspec.yaml").is_file():
        return True
    stamp = _skeleton_fingerprint_stamp(capture_dir)
    if not stamp.is_file():
        return True
    return stamp.read_text(encoding="utf-8").strip() != _compute_skeleton_fingerprint()


def _compute_pubspec_cache_key(workspace: Path, flutter: str) -> str:
    """Hash pubspec inputs that invalidate ``flutter pub get``."""
    digest = hashlib.sha256()
    digest.update(_SKELETON_VERSION.encode("utf-8"))
    digest.update(b"\0")
    digest.update(_flutter_version_snippet(flutter).encode("utf-8"))
    digest.update(b"\0")
    for name in ("pubspec.yaml", "pubspec.lock"):
        path = workspace / name
        if path.is_file():
            digest.update(name.encode("utf-8"))
            digest.update(path.read_bytes())
            digest.update(b"\0")
    skeleton_pubspec = _FLUTTER_SKELETON / "pubspec.yaml"
    if skeleton_pubspec.is_file():
        digest.update(b"skeleton")
        digest.update(skeleton_pubspec.read_bytes())
    return digest.hexdigest()


def _copy_skeleton_project(target_dir: Path) -> None:
    """Copy the Flutter skeleton without stale tool artifacts."""
    shutil.copytree(
        _FLUTTER_SKELETON,
        target_dir,
        ignore=shutil.ignore_patterns(".dart_tool", "build"),
    )


def _sync_fonts_folder(project_dir: Path, source_project: Path) -> None:
    """Copy bundled fonts from the target app into the capture workspace."""
    from figma_flutter_agent.fonts.local import ensure_project_fonts_dir

    ensure_project_fonts_dir(source_project)
    source = source_project / "assets" / "fonts"
    if not source.is_dir():
        return
    font_files = [path for path in source.iterdir() if path.is_file()]
    if not font_files:
        return
    destination = project_dir / "assets" / "fonts"
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    logger.info(
        "Golden capture: copied {} font file(s) from {}",
        len(font_files),
        source_project,
    )


def _merge_pubspec_package_name(project_dir: Path, source_project: Path) -> bool:
    """Align capture sandbox ``name`` with the target Flutter app for ``package:`` imports.

    Args:
        project_dir: Isolated capture workspace (skeleton or warm sandbox).
        source_project: Customer Flutter project root.

    Returns:
        ``True`` when the on-disk pubspec ``name`` field changed.
    """
    source_pubspec = source_project / "pubspec.yaml"
    target_pubspec = project_dir / "pubspec.yaml"
    if not source_pubspec.is_file() or not target_pubspec.is_file():
        return False
    yaml = YAML()
    source_data = yaml.load(source_pubspec.read_text(encoding="utf-8"))
    target_data = yaml.load(target_pubspec.read_text(encoding="utf-8"))
    if not isinstance(source_data, dict) or not isinstance(target_data, dict):
        return False
    source_name = source_data.get("name")
    if not isinstance(source_name, str) or not source_name.strip():
        return False
    normalized = source_name.strip()
    previous = target_data.get("name")
    if isinstance(previous, str) and previous.strip() == normalized:
        return False
    target_data["name"] = normalized
    yaml.dump(target_data, target_pubspec.open("w", encoding="utf-8"))
    logger.info(
        "Golden capture: aligned pubspec package name to {} in {}",
        normalized,
        project_dir.as_posix(),
    )
    return True


def _merge_pubspec_fonts_and_assets(project_dir: Path, source_project: Path) -> None:
    """Merge ``name``, ``flutter: fonts/assets`` from the target app into capture ``pubspec.yaml``."""
    _merge_pubspec_package_name(project_dir, source_project)
    source_pubspec = source_project / "pubspec.yaml"
    target_pubspec = project_dir / "pubspec.yaml"
    if not source_pubspec.is_file() or not target_pubspec.is_file():
        return
    yaml = YAML()
    source_data = yaml.load(source_pubspec.read_text(encoding="utf-8"))
    target_data = yaml.load(target_pubspec.read_text(encoding="utf-8"))
    if not isinstance(source_data, dict) or not isinstance(target_data, dict):
        return
    source_flutter = source_data.get("flutter")
    if not isinstance(source_flutter, dict):
        return
    target_flutter = target_data.setdefault("flutter", {})
    if not isinstance(target_flutter, dict):
        return
    if source_flutter.get("fonts"):
        from figma_flutter_agent.generator.pubspec import _filter_font_families_on_disk
        from figma_flutter_agent.schemas import FontPubspecAsset, FontPubspecFamily

        merged_families: list[FontPubspecFamily] = []
        for entry in source_flutter["fonts"]:
            if not isinstance(entry, dict):
                continue
            family_name = entry.get("family")
            font_rows = entry.get("fonts")
            if not isinstance(family_name, str) or not isinstance(font_rows, list):
                continue
            fonts = []
            for row in font_rows:
                if not isinstance(row, dict):
                    continue
                asset = row.get("asset")
                weight = row.get("weight")
                if not isinstance(asset, str) or not isinstance(weight, int):
                    continue
                style = row.get("style")
                fonts.append(
                    FontPubspecAsset(
                        asset=asset,
                        weight=weight,
                        style=style if isinstance(style, str) else None,
                    )
                )
            if fonts:
                merged_families.append(FontPubspecFamily(family=family_name, fonts=fonts))
        kept = _filter_font_families_on_disk(project_dir, merged_families)
        if kept:
            target_flutter["fonts"] = [
                {
                    "family": family.family,
                    "fonts": [
                        {
                            "asset": font.asset,
                            "weight": font.weight,
                            **({"style": font.style} if font.style else {}),
                        }
                        for font in family.fonts
                    ],
                }
                for family in kept
            ]
        else:
            target_flutter.pop("fonts", None)
    source_assets = source_flutter.get("assets")
    if isinstance(source_assets, list):
        target_assets = target_flutter.setdefault("assets", [])
        if not isinstance(target_assets, list):
            target_assets = []
            target_flutter["assets"] = target_assets
        existing_assets = {str(item) for item in target_assets}
        for item in source_assets:
            normalized = str(item).replace("\\", "/")
            if normalized not in existing_assets:
                target_assets.append(item)
                existing_assets.add(normalized)
    yaml.dump(target_data, target_pubspec.open("w", encoding="utf-8"))


def _ensure_pubspec_asset_dirs(project_dir: Path, asset_paths: set[str]) -> None:
    """Register ``assets/<subdir>/`` in capture ``pubspec.yaml`` for synced files."""
    dirs: set[str] = set()
    for asset_key in asset_paths:
        normalized = asset_key.replace("\\", "/")
        parts = Path(normalized).parts
        if len(parts) >= 2 and parts[0] == "assets":
            dirs.add(f"assets/{parts[1]}/")
    if not dirs:
        return
    pubspec_path = project_dir / "pubspec.yaml"
    if not pubspec_path.is_file():
        return
    yaml = YAML()
    data = yaml.load(pubspec_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return
    flutter_section = data.setdefault("flutter", {})
    if not isinstance(flutter_section, dict):
        return
    assets = flutter_section.setdefault("assets", [])
    if not isinstance(assets, list):
        assets = []
        flutter_section["assets"] = assets
    existing = {str(item).replace("\\", "/") for item in assets}
    for asset_dir in sorted(dirs):
        if asset_dir not in existing:
            assets.append(asset_dir)
            existing.add(asset_dir)
    yaml.dump(data, pubspec_path.open("w", encoding="utf-8"))


def _ensure_pubspec_asset_directories_on_disk(project_dir: Path) -> None:
    """Create asset folder entries declared in ``pubspec.yaml`` (Flutter requires them to exist)."""
    pubspec_path = project_dir / "pubspec.yaml"
    if not pubspec_path.is_file():
        return
    yaml = YAML()
    data = yaml.load(pubspec_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return
    flutter_section = data.get("flutter")
    if not isinstance(flutter_section, dict):
        return
    assets = flutter_section.get("assets")
    if not isinstance(assets, list):
        return
    for item in assets:
        normalized = str(item).replace("\\", "/")
        if not normalized.endswith("/"):
            continue
        (project_dir / normalized.rstrip("/")).mkdir(parents=True, exist_ok=True)


def _sync_referenced_assets(
    project_dir: Path,
    source_project: Path,
    asset_paths: set[str],
) -> None:
    """Copy only assets referenced by the planned screen (not the whole ``assets/`` tree)."""
    for asset_key in sorted(asset_paths):
        normalized = asset_key.replace("\\", "/")
        if not normalized.startswith("assets/"):
            continue
        source = source_project / Path(normalized)
        if not source.is_file():
            logger.debug("Golden capture: asset missing on disk: {}", normalized)
            continue
        destination = project_dir / Path(normalized)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _sync_theme_lib(project_dir: Path, source_project: Path, planned: Mapping[str, str]) -> None:
    """Copy ``lib/theme`` when planned Dart references theme tokens (e.g. ``AppBreakpoints``)."""
    needs_theme = any("theme/" in content for content in planned.values())
    if not needs_theme:
        return
    source = source_project / "lib" / "theme"
    if not source.is_dir():
        logger.warning(
            "Golden capture: planned files reference theme/ but {} is missing",
            source.as_posix(),
        )
        return
    destination = project_dir / "lib" / "theme"
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    logger.info(
        "Golden capture: copied theme lib ({} file(s))",
        sum(1 for path in destination.rglob("*") if path.is_file()),
    )


def _sync_project_assets(
    project_dir: Path,
    source_project: Path,
    *,
    planned: Mapping[str, str] | None = None,
    layout_tree: CleanDesignTreeNode | None = None,
) -> None:
    """Copy fonts, pubspec asset trees, and referenced files from the target app."""
    _sync_fonts_folder(project_dir, source_project)
    _merge_pubspec_fonts_and_assets(project_dir, source_project)
    sync_flutter_test_config(project_dir, source_project)
    _ensure_pubspec_asset_directories_on_disk(project_dir)
    if planned is None:
        return
    _sync_theme_lib(project_dir, source_project, planned)
    asset_paths = collect_planned_asset_paths(planned, layout_tree)
    _sync_referenced_assets(project_dir, source_project, asset_paths)
    _ensure_pubspec_asset_dirs(project_dir, asset_paths)
    _ensure_pubspec_asset_directories_on_disk(project_dir)
    if asset_paths:
        logger.info(
            "Golden capture: synced {} referenced asset file(s) (not full assets/ tree)",
            len(asset_paths),
        )


def _safe_temp_cleanup(tmp_handle: tempfile.TemporaryDirectory[str] | None) -> None:
    if tmp_handle is None:
        return
    try:
        tmp_handle.cleanup()
    except (OSError, RecursionError) as exc:
        logger.debug("Golden capture temp cleanup fallback ({}): {}", exc, tmp_handle.name)
        shutil.rmtree(tmp_handle.name, ignore_errors=True)


def _prepare_flutter_test_build_dir(project_dir: Path) -> bool:
    """Drop stale Flutter build output so ``flutter test`` rebuilds the asset bundle.

    Returns:
        True when the build directory is absent or was removed successfully.
    """
    build_dir = project_dir / "build"
    if not build_dir.exists():
        return True
    last_exc: OSError | None = None
    for attempt in range(_BUILD_DIR_CLEAR_RETRIES):
        try:
            shutil.rmtree(build_dir, onerror=_handle_rmtree_readonly)
            return True
        except OSError as exc:
            last_exc = exc
            if attempt + 1 >= _BUILD_DIR_CLEAR_RETRIES:
                break
            time.sleep(_BUILD_DIR_CLEAR_BACKOFF_SEC * (attempt + 1))
    logger.warning("Could not remove {} before golden test: {}", build_dir, last_exc)
    return not build_dir.exists()


def _run_flutter_pub_get(
    project_dir: Path,
    flutter: str,
    *,
    timings: GoldenCaptureTimings | None = None,
) -> GoldenCaptureResult | None:
    """Resolve packages before ``flutter test``. Returns failure or None."""
    import time

    from figma_flutter_agent.errors import GenerationError
    from figma_flutter_agent.generator.codegen import run_pub_get
    from figma_flutter_agent.validation.golden_capture.result import (
        GoldenCaptureResult,  # noqa: PLC0415
    )

    stamp_path = _pubspec_cache_stamp(project_dir)
    expected = _compute_pubspec_cache_key(project_dir, flutter)
    if stamp_path.is_file() and stamp_path.read_text(encoding="utf-8").strip() == expected:
        logger.info("Golden capture: pub get skipped (unchanged pubspec fingerprint)")
        if timings is not None:
            timings.add("pubGet", 0.0)
        return None

    t0 = time.monotonic()
    try:
        run_pub_get(project_dir)
    except GenerationError as exc:
        message = str(exc)
        if "timed out" in message:
            return GoldenCaptureResult(
                reason=_clip_reason(
                    f"flutter pub get timed out after {FLUTTER_PUB_GET_TIMEOUT_SEC:.0f}s"
                ),
            )
        return GoldenCaptureResult(reason=_clip_reason("flutter pub get failed before golden test"))
    stamp_path.parent.mkdir(parents=True, exist_ok=True)
    stamp_path.write_text(expected, encoding="utf-8")
    if timings is not None:
        timings.add("pubGet", time.monotonic() - t0)
    return None


def _prepare_capture_workspace() -> tuple[Path, tempfile.TemporaryDirectory[str]]:
    """Return an empty isolated capture root (skeleton only)."""
    tmp = tempfile.TemporaryDirectory(prefix="figma-flutter-golden-")
    capture_dir = Path(tmp.name) / "golden_capture"
    _copy_skeleton_project(capture_dir)
    return capture_dir, tmp


def _write_planned_for_golden_capture(
    capture_dir: Path,
    planned: Mapping[str, str],
    *,
    layout_tree: CleanDesignTreeNode | None,
) -> dict[str, str]:
    """Flush in-memory planned Dart into an on-disk Flutter tree (no asset tree copy)."""
    capture_planned = enrich_planned_from_project(dict(planned), capture_dir)
    writer = DartWriter(capture_dir, enable_backup=True)
    writer.write_files(capture_planned)
    if layout_tree is not None:
        sync_fixture_vector_assets(capture_dir, layout_tree, overwrite=False)
    return capture_planned


def _materialize_capture_workspace(
    capture_dir: Path,
    planned: dict[str, str],
    *,
    enable_backup: bool,
    layout_tree: CleanDesignTreeNode | None,
    project_dir: Path | None,
) -> dict[str, str]:
    """Enrich planned Dart, write files, and sync fonts/assets into an isolated sandbox."""
    capture_planned = dict(planned)
    if project_dir is not None and project_dir.is_dir():
        capture_planned = enrich_planned_from_project(capture_planned, project_dir)
    writer = DartWriter(capture_dir, enable_backup=enable_backup)
    writer.write_files(capture_planned)
    if layout_tree is not None:
        sync_fixture_vector_assets(capture_dir, layout_tree)
    if project_dir is not None and project_dir.is_dir():
        _sync_project_assets(
            capture_dir,
            project_dir,
            planned=capture_planned,
            layout_tree=layout_tree,
        )
    return capture_planned
