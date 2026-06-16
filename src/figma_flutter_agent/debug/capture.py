"""Persist Flutter render snapshots under ``.debug/<project>/<feature>/`` (flat, latest-only)."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

from figma_flutter_agent.config import Settings
from figma_flutter_agent.debug.paths import (
    RENDERS_SUBDIR,
    debug_capture_artifact_path,
    debug_path_display,
    figma_reference_png_path,
    screen_capture_dir,
    screen_root,
)
from figma_flutter_agent.dev.view_render_plan import (
    load_clean_tree_from_debug,
    planned_for_capture_from_map,
)
from figma_flutter_agent.dev.view_capture_timeout import capture_settings_for_planned
from figma_flutter_agent.dev.warm_capture import capture_planned_in_warm_sandbox
from figma_flutter_agent.preview_capture import CaptureMode, resolve_capture_mode
from figma_flutter_agent.schemas import CleanDesignTreeNode
from figma_flutter_agent.validation.compare import compare_png_bytes
from figma_flutter_agent.validation.pixel.coordinates import (
    parse_flutter_mapper_payload,
)
from figma_flutter_agent.validation.pixel.heatmap import render_visual_diff_heatmap_png
from figma_flutter_agent.validation.pixel.models import VisualCompareResult
from figma_flutter_agent.validation.reference import load_cached_reference_png


@dataclass(frozen=True)
class DebugCaptureOutcome:
    """Result of a project-local debug capture session."""

    capture_dir: Path
    figma_reference_ok: bool
    flutter_capture_ok: bool
    diff_ok: bool
    changed_ratio: float | None
    warnings: tuple[str, ...]


def _write_png(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def prune_stale_render_sessions(project_dir: Path, feature_name: str) -> None:
    """Remove timestamped ``renders/<session>/`` folders; wizard keeps flat latest artifacts only."""
    renders_root = screen_root(project_dir, feature_name) / RENDERS_SUBDIR
    if renders_root.is_dir():
        shutil.rmtree(renders_root, ignore_errors=True)


def persist_latest_screen_capture(
    project_dir: Path,
    feature_name: str,
    *,
    capture_png: bytes | None = None,
    diff_heatmap_png: bytes | None = None,
    use_preview_artifact: bool = False,
    outcome: DebugCaptureOutcome | None = None,
) -> Path:
    """Overwrite flat capture artifacts under ``.debug/<project>/<feature>/``.

    Args:
        project_dir: Flutter project root.
        feature_name: Screen feature slug.
        capture_png: Flutter or browser preview PNG bytes.
        diff_heatmap_png: Optional pixel-diff heatmap PNG bytes.
        use_preview_artifact: When true, write ``preview_capture.png`` instead of ``capture.png``.
        outcome: Optional capture outcome for ``capture.json`` manifest.

    Returns:
        Per-screen debug root (same folder as ``raw.json``).
    """
    screen_dir = screen_capture_dir(project_dir, feature_name)
    screen_dir.mkdir(parents=True, exist_ok=True)
    prune_stale_render_sessions(project_dir, feature_name)

    if capture_png is not None:
        artifact = "preview_capture" if use_preview_artifact else "capture"
        _write_png(debug_capture_artifact_path(project_dir, feature_name, artifact), capture_png)

    if diff_heatmap_png is not None:
        _write_png(
            debug_capture_artifact_path(project_dir, feature_name, "diff_heatmap"),
            diff_heatmap_png,
        )

    if outcome is not None:
        _write_manifest(project_dir, feature_name=feature_name, outcome=outcome)

    return screen_dir


def _resolve_figma_png(
    project_dir: Path,
    feature_name: str,
    figma_reference_png: bytes | None,
) -> bytes | None:
    """Load Figma gold from ``reference/figma``; persist in-memory bytes there only."""
    ref_path = figma_reference_png_path(project_dir, feature_name)
    if ref_path.is_file():
        return ref_path.read_bytes()
    if figma_reference_png is not None:
        _write_png(ref_path, figma_reference_png)
        return figma_reference_png
    return load_cached_reference_png(project_dir, feature_name)


def _write_manifest(
    project_dir: Path,
    *,
    feature_name: str,
    outcome: DebugCaptureOutcome,
) -> None:
    figma_rel = debug_path_display(figma_reference_png_path(project_dir, feature_name), project_dir)
    manifest = {
        "featureName": feature_name,
        "capturedAt": datetime.now(tz=UTC).isoformat(),
        "figmaReferenceOk": outcome.figma_reference_ok,
        "flutterCaptureOk": outcome.flutter_capture_ok,
        "diffOk": outcome.diff_ok,
        "changedRatio": outcome.changed_ratio,
        "warnings": list(outcome.warnings),
        "artifacts": {
            "figmaReference": figma_rel,
            "capture": debug_capture_artifact_path(project_dir, feature_name, "capture").name,
            "diffHeatmap": debug_capture_artifact_path(
                project_dir, feature_name, "diff_heatmap"
            ).name,
        },
    }
    path = debug_capture_artifact_path(project_dir, feature_name, "manifest")
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


async def run_project_debug_capture(
    *,
    project_dir: Path,
    feature_name: str,
    settings: Settings,
    planned_files: dict[str, str],
    clean_tree: CleanDesignTreeNode | None = None,
    figma_reference_png: bytes | None = None,
) -> DebugCaptureOutcome | None:
    """Capture Flutter render and diff under ``.debug/capture`` (flat, feature-prefixed names).

    Figma reference PNG is **not** duplicated here; the canonical file lives under
    ``.debug/reference/figma/<feature>_figma.png``.

    Args:
        project_dir: Flutter project root.
        feature_name: Generated screen feature slug.
        settings: Resolved agent settings.
        planned_files: Final planned Dart map from the pipeline.
        clean_tree: Parsed clean tree for layout refresh and diff alignment.
        figma_reference_png: Optional in-memory Figma PNG from the pipeline.

    Returns:
        Outcome when capture ran, or ``None`` when ``dev.debug_capture`` is disabled.
    """
    if not settings.agent.dev.debug_capture:
        return None

    warnings: list[str] = []
    tree = clean_tree or load_clean_tree_from_debug(project_dir, feature_name)
    capture_root = screen_capture_dir(project_dir, feature_name)
    capture_root.mkdir(parents=True, exist_ok=True)

    figma_png = _resolve_figma_png(project_dir, feature_name, figma_reference_png)
    figma_ok = figma_png is not None
    if not figma_ok:
        warnings.append(
            "Figma reference PNG missing under .debug/<feature>/figma.png "
            f"for {feature_name!r}; enable validation.export_figma_reference or run live fetch"
        )

    planned = planned_for_capture_from_map(
        project_dir,
        feature_name=feature_name,
        planned_files=planned_files,
        settings=settings,
        clean_tree=tree,
    )
    capture_settings = capture_settings_for_planned(settings, planned)

    capture = capture_planned_in_warm_sandbox(
        planned,
        feature_name=feature_name,
        project_dir=project_dir,
        layout_tree=tree,
        settings=capture_settings,
    )
    if not capture.ok or capture.png is None:
        reason = capture.reason or "flutter render capture failed"
        warnings.append(reason)
        outcome = DebugCaptureOutcome(
            capture_dir=capture_root,
            figma_reference_ok=figma_ok,
            flutter_capture_ok=False,
            diff_ok=False,
            changed_ratio=None,
            warnings=tuple(warnings),
        )
        _write_manifest(project_dir, feature_name=feature_name, outcome=outcome)
        logger.warning("Debug capture for {}: Flutter render failed ({})", feature_name, reason)
        return outcome

    flutter_png = capture.png
    capture_mode = resolve_capture_mode(settings)
    if capture_mode is CaptureMode.PREVIEW:
        outcome = DebugCaptureOutcome(
            capture_dir=capture_root,
            figma_reference_ok=figma_ok,
            flutter_capture_ok=True,
            diff_ok=False,
            changed_ratio=None,
            warnings=tuple(warnings),
        )
        persist_latest_screen_capture(
            project_dir,
            feature_name,
            capture_png=flutter_png,
            use_preview_artifact=True,
            outcome=outcome,
        )
        preview_path = debug_capture_artifact_path(project_dir, feature_name, "preview_capture")
        logger.info(
            "Debug preview capture for {} → {}",
            feature_name,
            preview_path.as_posix(),
        )
        return outcome

    changed_ratio: float | None = None
    diff_ok = False
    heatmap_png: bytes | None = None
    if figma_ok and figma_png is not None:
        generation_cfg = settings.agent.generation
        compare_outcome = compare_png_bytes(
            figma_png,
            flutter_png,
            threshold=generation_cfg.llm_visual_refine_threshold,
            clean_tree=tree,
            flutter_mapper=parse_flutter_mapper_payload(capture.figma_key_rects),
            text_coordinate_tolerance=generation_cfg.text_coordinate_tolerance,
        )
        if isinstance(compare_outcome, VisualCompareResult):
            changed_ratio = compare_outcome.pixel.changed_ratio
        else:
            changed_ratio = compare_outcome.changed_ratio
        heatmap_png = render_visual_diff_heatmap_png(
            figma_png,
            flutter_png,
            clean_tree=tree,
        )
        diff_ok = True

    outcome = DebugCaptureOutcome(
        capture_dir=capture_root,
        figma_reference_ok=figma_ok,
        flutter_capture_ok=True,
        diff_ok=diff_ok,
        changed_ratio=changed_ratio,
        warnings=tuple(warnings),
    )
    persist_latest_screen_capture(
        project_dir,
        feature_name,
        capture_png=flutter_png,
        diff_heatmap_png=heatmap_png,
        outcome=outcome,
    )
    if changed_ratio is not None:
        logger.info(
            "Debug capture for {}: {:.2%} changed vs Figma → {}",
            feature_name,
            changed_ratio,
            capture_root.as_posix(),
        )
    else:
        logger.info("Debug capture for {} → {}", feature_name, capture_root.as_posix())
    return outcome
