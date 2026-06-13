"""Canonical paths for ``.debug`` project artifacts (screen-centric layout v3)."""

from __future__ import annotations

import re
from pathlib import Path

FIGMA_DEBUG_DIR = ".debug"
LEGACY_FIGMA_DEBUG_DIR = ".figma_debug"
LEGACY_AGENT_DIR = ".figma-flutter"

# Legacy v2 domain folders (pre screen-centric layout).
RAW_DIR = "raw"
PROCESSED_DIR = "processed"
DART_DIR = "dart"
DART_BUG_DIR = "dart.bug"
IR_DIR = "ir"
REFERENCE_DIR = "reference"
FIGMA_REFERENCE_SUBDIR = f"{REFERENCE_DIR}/figma"
EMITTER_REFERENCE_SUBDIR = f"{REFERENCE_DIR}/emitter"
SEMANTICS_DIR = "semantics"
PROVENANCE_DIR = "provenance"
REPORTS_DIR = "reports"
FIDELITY_DIR = "fidelity"

# Screen-centric v3 layout.
PRIMARY_DIR = "primary"
SECONDARY_DIR = "secondary"
SHARED_DIR = "shared"

RAW_JSON = "raw.json"
PROCESSED_JSON = "processed.json"
PLAN_DART = "plan.dart"
SCREEN_DART = "screen.dart"
SCREEN_BUG_DART = "screen.bug.dart"
FIGMA_PNG = "figma.png"
FIGMA_JSON = "figma.json"
SEMANTICS_JSON = "semantics.json"
PROVENANCE_JSON = "provenance.json"
EMITTER_REF_DART = "emitter_ref.dart"
EMITTER_META_JSON = "emitter_meta.json"
FIDELITY_JSON = "fidelity.json"
AI_UX_JSON = "ai_ux.json"
ANIMATIONS_JSON = "animations.json"
DESIGN_COVERAGE_JSON = "design_coverage.json"
RUN_META_JSON = "run.meta.json"

SYNC_DIR = "sync"
SNAPSHOT_FILE_NAME = "snapshot.json"
DEBUG_CAPTURE_DIR = "capture"
CAPTURE_SANDBOX_SUBDIR = "sandbox"
LEGACY_CAPTURE_SANDBOX_DIR = "capture-sandbox"
RUN_LOGS_SUBDIR = "logs"
LAST_RUN_LOG_FILE = "last.log"
LEGACY_DART_ERRORS_SUBDIR = "dart-errors"
LEGACY_TERMINAL_SUBDIR = "terminal"
RENDERS_SUBDIR = "renders"
PERF_SUBDIR = "perf"
SECONDARY_CAPTURE_DIR = "capture"
SECONDARY_PERF_DIR = "perf"
WIZARD_STATE_FILE = "wizard-state.yml"
WORKSPACE_STATE_FILE = "workspace-state.yml"

ARTIFACT_LAYOUT_MARKER_V2 = ".artifact-layout-v2"
ARTIFACT_LAYOUT_MARKER = ".artifact-layout-v3"
ARTIFACT_LAYOUT_VERSION = 6

FIGMA_REFERENCE_REL = f"{FIGMA_DEBUG_DIR}/<feature>/{PRIMARY_DIR}/{FIGMA_PNG}"
EMITTER_REFERENCE_REL = f"{FIGMA_DEBUG_DIR}/<feature>/{SECONDARY_DIR}/{EMITTER_REF_DART}"

_PRIMARY_IR_STAGES = frozenset({"pre_emit"})
_IR_STAGE_FILENAMES: dict[str, str] = {
    "llm_parsed": "llm_parsed.json",
    "llm_validated": "llm_validated.json",
    "pre_emit": "pre_emit.json",
    "semantic_context": "semantic_context.json",
    "semantic_verdicts": "semantic_verdicts.json",
    "element_contracts": "element_contracts.json",
    "contract_emit_diff": "contract_emit_diff.json",
}
_STAGE_SAFE_RE = re.compile(r"[^\w.-]+")


def screen_debug_safe_feature(feature_name: str) -> str:
    """Sanitize a feature slug for ``.debug/<feature>/`` directory names."""
    return feature_name.replace("/", "_").replace("\\", "_").strip() or "screen"


def screen_root(project_dir: Path, feature_name: str) -> Path:
    """Return ``.debug/<feature>/`` for one screen."""
    return project_dir / FIGMA_DEBUG_DIR / screen_debug_safe_feature(feature_name)


def screen_primary_dir(project_dir: Path, feature_name: str) -> Path:
    """Return ``.debug/<feature>/primary/``."""
    return screen_root(project_dir, feature_name) / PRIMARY_DIR


def screen_secondary_dir(project_dir: Path, feature_name: str) -> Path:
    """Return ``.debug/<feature>/secondary/``."""
    return screen_root(project_dir, feature_name) / SECONDARY_DIR


def shared_debug_dir(project_dir: Path) -> Path:
    """Return ``.debug/shared/`` for project-wide dumps (full-file cache)."""
    return project_dir / FIGMA_DEBUG_DIR / SHARED_DIR


def layout_debug_filename(feature_name: str) -> str:
    """Return the legacy v2 raw/processed JSON basename."""
    return f"{feature_name}_layout.json"


def _ir_artifact_filename(stage: str) -> str:
    mapped = _IR_STAGE_FILENAMES.get(stage)
    if mapped is not None:
        return mapped
    safe = _STAGE_SAFE_RE.sub("_", stage.strip()).strip("_") or "snapshot"
    return f"{safe}.json"


def screen_ir_dump_path(project_dir: Path, feature_name: str, stage: str) -> Path:
    """Return the screen IR JSON snapshot path for ``feature_name`` and ``stage``.

    ``pre_emit`` lives in ``primary/``; all other stages live in ``secondary/``.
    """
    filename = _ir_artifact_filename(stage)
    if stage in _PRIMARY_IR_STAGES:
        return screen_primary_dir(project_dir, feature_name) / filename
    return screen_secondary_dir(project_dir, feature_name) / filename


def legacy_v2_screen_ir_dump_path(project_dir: Path, feature_name: str, stage: str) -> Path:
    """Return deprecated ``.debug/ir/<feature>_<stage>.json``."""
    return project_dir / FIGMA_DEBUG_DIR / IR_DIR / f"{feature_name}_{stage}.json"


def raw_dump_path(project_dir: Path, feature_name: str) -> Path:
    """Return the raw Figma REST dump path for ``feature_name``."""
    return screen_primary_dir(project_dir, feature_name) / RAW_JSON


def processed_dump_path(project_dir: Path, feature_name: str) -> Path:
    """Return the parsed clean-tree dump path for ``feature_name``."""
    return screen_primary_dir(project_dir, feature_name) / PROCESSED_JSON


def legacy_v2_raw_dump_path(project_dir: Path, feature_name: str) -> Path:
    """Return deprecated ``.debug/raw/<feature>_layout.json``."""
    return project_dir / FIGMA_DEBUG_DIR / RAW_DIR / layout_debug_filename(feature_name)


def legacy_v2_processed_dump_path(project_dir: Path, feature_name: str) -> Path:
    """Return deprecated ``.debug/processed/<feature>_layout.json``."""
    return (
        project_dir
        / FIGMA_DEBUG_DIR
        / PROCESSED_DIR
        / layout_debug_filename(feature_name)
    )


def figma_reference_dir(project_dir: Path, feature_name: str | None = None) -> Path:
    """Return the directory holding Figma PNG/JSON gold for a screen.

    When ``feature_name`` is omitted, returns the legacy flat ``reference/figma`` dir
    (migration source only).
    """
    if feature_name is not None:
        return screen_primary_dir(project_dir, feature_name)
    return project_dir / FIGMA_DEBUG_DIR / FIGMA_REFERENCE_SUBDIR


def figma_reference_png_path(project_dir: Path, feature_name: str) -> Path:
    """Return the on-disk path for a feature Figma reference PNG."""
    return screen_primary_dir(project_dir, feature_name) / FIGMA_PNG


def figma_reference_metadata_path(project_dir: Path, feature_name: str) -> Path:
    """Return the on-disk path for a feature Figma reference JSON metadata."""
    return screen_primary_dir(project_dir, feature_name) / FIGMA_JSON


def legacy_v2_figma_reference_png_path(project_dir: Path, feature_name: str) -> Path:
    """Return deprecated ``.debug/reference/figma/<feature>_figma.png``."""
    return (
        project_dir
        / FIGMA_DEBUG_DIR
        / FIGMA_REFERENCE_SUBDIR
        / f"{feature_name}_figma.png"
    )


def legacy_figma_reference_dir(project_dir: Path) -> Path:
    """Return deprecated ``.figma-flutter/reference`` (pre-consolidation)."""
    return project_dir / LEGACY_AGENT_DIR / REFERENCE_DIR


def sync_snapshot_path(project_dir: Path) -> Path:
    """Return incremental sync snapshot path under ``.debug/sync/``."""
    return project_dir / FIGMA_DEBUG_DIR / SYNC_DIR / SNAPSHOT_FILE_NAME


def legacy_sync_snapshot_path(project_dir: Path) -> Path:
    """Return deprecated ``.figma-flutter/snapshot.json``."""
    return project_dir / LEGACY_AGENT_DIR / SNAPSHOT_FILE_NAME


def capture_sandbox_dir(project_dir: Path) -> Path:
    """Return warm golden capture sandbox under ``.debug/capture/sandbox``."""
    return debug_capture_root(project_dir) / CAPTURE_SANDBOX_SUBDIR


def debug_capture_root(project_dir: Path) -> Path:
    """Return project-level ``.debug/capture/`` (sandbox only; per-screen capture is under ``secondary/capture``)."""
    return project_dir / FIGMA_DEBUG_DIR / DEBUG_CAPTURE_DIR


def screen_capture_dir(project_dir: Path, feature_name: str) -> Path:
    """Return ``.debug/<feature>/secondary/capture/``."""
    return screen_secondary_dir(project_dir, feature_name) / SECONDARY_CAPTURE_DIR


def debug_capture_safe_feature(feature_name: str) -> str:
    """Sanitize a feature slug for legacy flat capture filenames."""
    return screen_debug_safe_feature(feature_name)


def debug_capture_artifact_path(
    project_dir: Path,
    feature_name: str,
    artifact: str,
) -> Path:
    """Return a per-screen capture artifact under ``secondary/capture/``.

    Figma gold is canonical under ``primary/figma.png``, not duplicated here.
    """
    suffix_by_artifact = {
        "flutter_render": "flutter_render.png",
        "preview_capture": "preview_capture.png",
        "diff_heatmap": "diff_heatmap.png",
        "manifest": "capture.json",
    }
    suffix = suffix_by_artifact.get(artifact)
    if suffix is None:
        msg = f"Unknown debug capture artifact {artifact!r}"
        raise ValueError(msg)
    return screen_capture_dir(project_dir, feature_name) / suffix


def legacy_v2_debug_capture_artifact_path(
    project_dir: Path,
    feature_name: str,
    artifact: str,
) -> Path:
    """Return deprecated flat ``.debug/capture/<feature>_*.png`` paths."""
    suffix_by_artifact = {
        "flutter_render": "_flutter_render.png",
        "preview_capture": "_preview_capture.png",
        "diff_heatmap": "_diff_heatmap.png",
        "manifest": "_capture.json",
    }
    suffix = suffix_by_artifact.get(artifact)
    if suffix is None:
        msg = f"Unknown debug capture artifact {artifact!r}"
        raise ValueError(msg)
    safe_feature = debug_capture_safe_feature(feature_name)
    return debug_capture_root(project_dir) / f"{safe_feature}{suffix}"


def debug_capture_dir(project_dir: Path, feature_name: str) -> Path:
    """Return per-screen capture directory."""
    return screen_capture_dir(project_dir, feature_name)


def project_run_logs_dir(project_dir: Path) -> Path:
    """Return ``.debug/logs/`` for the latest pipeline subprocess + analyzer transcript."""
    return project_dir / FIGMA_DEBUG_DIR / RUN_LOGS_SUBDIR


def project_run_log_path(project_dir: Path) -> Path:
    """Return ``.debug/logs/last.log`` (cleared at each pipeline start)."""
    return project_run_logs_dir(project_dir) / LAST_RUN_LOG_FILE


def last_terminal_log_path(project_dir: Path) -> Path:
    """Deprecated alias for :func:`project_run_log_path`."""
    return project_run_log_path(project_dir)


def render_session_dir(
    project_dir: Path,
    log_stem: str,
    *,
    feature_name: str | None = None,
) -> Path:
    """Return combat-mode PNG session directory for one screen."""
    if feature_name is not None:
        return (
            screen_secondary_dir(project_dir, feature_name)
            / RENDERS_SUBDIR
            / log_stem
        )
    return project_dir / FIGMA_DEBUG_DIR / RENDERS_SUBDIR / log_stem


def screen_perf_dir(project_dir: Path, feature_name: str) -> Path:
    """Return ``.debug/<feature>/secondary/perf/``."""
    return screen_secondary_dir(project_dir, feature_name) / SECONDARY_PERF_DIR


def perf_dir(project_dir: Path) -> Path:
    """Deprecated project-level perf directory (v2); prefer :func:`screen_perf_dir`."""
    return project_dir / FIGMA_DEBUG_DIR / PERF_SUBDIR


def project_wizard_prefs_path(project_dir: Path) -> Path:
    """Return wizard prefs for one Flutter project."""
    return project_dir / FIGMA_DEBUG_DIR / WIZARD_STATE_FILE


def workspace_prefs_path(workspace_root: Path) -> Path:
    """Return workspace-level wizard prefs under ``workspace_root/.debug/``."""
    return workspace_root / FIGMA_DEBUG_DIR / WORKSPACE_STATE_FILE


def legacy_workspace_prefs_path(workspace_root: Path) -> Path:
    """Return deprecated ``.figma-flutter/workspace-state.yml``."""
    return workspace_root / LEGACY_AGENT_DIR / WORKSPACE_STATE_FILE


def semantics_report_path(project_dir: Path, feature_name: str) -> Path:
    """Return ``.debug/<feature>/primary/semantics.json``."""
    return screen_primary_dir(project_dir, feature_name) / SEMANTICS_JSON


def provenance_dump_path(project_dir: Path, feature_name: str) -> Path:
    """Return ``.debug/<feature>/secondary/provenance.json``."""
    return screen_secondary_dir(project_dir, feature_name) / PROVENANCE_JSON


def fidelity_report_path(project_dir: Path, feature_name: str) -> Path:
    """Return ``.debug/<feature>/secondary/fidelity.json``."""
    return screen_secondary_dir(project_dir, feature_name) / FIDELITY_JSON


def ai_ux_report_path(project_dir: Path, feature_name: str) -> Path:
    """Return ``.debug/<feature>/secondary/ai_ux.json``."""
    return screen_secondary_dir(project_dir, feature_name) / AI_UX_JSON


def animations_report_path(project_dir: Path, feature_name: str) -> Path:
    """Return ``.debug/<feature>/secondary/animations.json``."""
    return screen_secondary_dir(project_dir, feature_name) / ANIMATIONS_JSON


def design_coverage_report_path(project_dir: Path, feature_name: str) -> Path:
    """Return ``.debug/<feature>/secondary/design_coverage.json``."""
    return screen_secondary_dir(project_dir, feature_name) / DESIGN_COVERAGE_JSON


def emitter_reference_bundle_path(project_dir: Path, feature_name: str) -> Path:
    """Return the IR emitter golden bundle path for ``feature_name``."""
    return screen_secondary_dir(project_dir, feature_name) / EMITTER_REF_DART


def emitter_reference_metadata_path(project_dir: Path, feature_name: str) -> Path:
    """Return emitter reference metadata JSON beside ``emitter_ref.dart``."""
    return screen_secondary_dir(project_dir, feature_name) / EMITTER_META_JSON


def legacy_v2_emitter_reference_bundle_path(project_dir: Path, feature_name: str) -> Path:
    """Return deprecated ``.debug/reference/emitter/<feature>_screen.dart``."""
    return (
        project_dir
        / FIGMA_DEBUG_DIR
        / EMITTER_REFERENCE_SUBDIR
        / f"{feature_name}_screen.dart"
    )


def emitter_reference_layout_path(project_dir: Path, feature_name: str) -> Path:
    """Deprecated alias for the single-file emitter bundle path."""
    return emitter_reference_bundle_path(project_dir, feature_name)


def emitter_reference_dir(project_dir: Path) -> Path:
    """Return legacy flat ``.debug/reference/emitter`` (migration source only)."""
    return project_dir / FIGMA_DEBUG_DIR / EMITTER_REFERENCE_SUBDIR


def legacy_emitter_reference_bundle_path(project_dir: Path, feature_name: str) -> Path:
    """Return deprecated flat ``.debug/reference/<feature>_screen.dart``."""
    return project_dir / FIGMA_DEBUG_DIR / REFERENCE_DIR / f"{feature_name}_screen.dart"


def dart_bundle_path(project_dir: Path, feature_name: str) -> Path:
    """Return the debug Dart bundle path for ``feature_name``."""
    return dart_debug_snapshot_path(project_dir, feature_name, "final")


def dart_debug_snapshot_path(project_dir: Path, feature_name: str, snapshot: str) -> Path:
    """Return a debug Dart bundle path for ``feature_name``.

    Args:
        snapshot: ``plan`` (post-plan), ``final`` (pre-write), or ``bug`` (failed gate/analyze).
    """
    if snapshot == "bug":
        return screen_secondary_dir(project_dir, feature_name) / SCREEN_BUG_DART
    if snapshot == "plan":
        return screen_primary_dir(project_dir, feature_name) / PLAN_DART
    if snapshot == "final":
        return screen_primary_dir(project_dir, feature_name) / SCREEN_DART
    msg = f"Unknown dart debug snapshot {snapshot!r}; expected plan, final, or bug"
    raise ValueError(msg)


def legacy_v2_dart_debug_snapshot_path(
    project_dir: Path,
    feature_name: str,
    snapshot: str,
) -> Path:
    """Return deprecated v2 dart bundle paths under ``dart/`` and ``dart.bug/``."""
    if snapshot == "bug":
        return (
            project_dir
            / FIGMA_DEBUG_DIR
            / DART_BUG_DIR
            / f"{feature_name}_screen.dart"
        )
    if snapshot == "plan":
        return project_dir / FIGMA_DEBUG_DIR / DART_DIR / f"{feature_name}_plan.dart"
    if snapshot == "final":
        return project_dir / FIGMA_DEBUG_DIR / DART_DIR / f"{feature_name}_screen.dart"
    msg = f"Unknown dart debug snapshot {snapshot!r}; expected plan, final, or bug"
    raise ValueError(msg)


def full_file_dump_path(project_dir: Path, file_key: str) -> Path:
    """Return the full-file Figma dump path for ``file_key``."""
    return shared_debug_dir(project_dir) / f"full_file_{file_key}.json"


def legacy_full_file_dump_path(project_dir: Path, file_key: str) -> Path:
    """Return legacy full-file dump paths (``.debug/raw`` or debug root)."""
    return project_dir / FIGMA_DEBUG_DIR / RAW_DIR / f"full_file_{file_key}.json"


def legacy_raw_dump_path(project_dir: Path, node_id: str) -> Path:
    """Return the pre-layout raw dump path keyed by Figma node id."""
    return project_dir / FIGMA_DEBUG_DIR / f"raw_node_{node_id.replace(':', '_')}.json"


def resolve_full_file_dump(project_dir: Path, file_key: str) -> Path:
    """Resolve an existing full-file dump, preferring the ``shared/`` layout."""
    candidates = (
        full_file_dump_path(project_dir, file_key),
        legacy_full_file_dump_path(project_dir, file_key),
        project_dir / FIGMA_DEBUG_DIR / f"full_file_{file_key}.json",
    )
    for path in candidates:
        if path.is_file():
            return path
    preferred = candidates[0]
    msg = (
        f"Full file dump not found at {preferred.as_posix()}. "
        "Run `figma-flutter batch dump-file` first."
    )
    raise FileNotFoundError(msg)


def _first_existing_file(*candidates: Path) -> Path | None:
    for path in candidates:
        if path.is_file():
            return path
    return None


def resolve_raw_dump_path(project_dir: Path, feature_name: str) -> Path | None:
    """Return the first existing raw dump path (v3, then v2)."""
    return _first_existing_file(
        raw_dump_path(project_dir, feature_name),
        legacy_v2_raw_dump_path(project_dir, feature_name),
    )


def resolve_processed_dump_path(project_dir: Path, feature_name: str) -> Path | None:
    """Return the first existing processed dump path (v3, then v2)."""
    return _first_existing_file(
        processed_dump_path(project_dir, feature_name),
        legacy_v2_processed_dump_path(project_dir, feature_name),
    )


def resolve_screen_ir_dump_file(
    project_dir: Path,
    feature_name: str,
    stage: str,
) -> Path | None:
    """Return the first existing IR dump for ``stage`` (v3, then v2)."""
    return _first_existing_file(
        screen_ir_dump_path(project_dir, feature_name, stage),
        legacy_v2_screen_ir_dump_path(project_dir, feature_name, stage),
    )


def rename_screen_debug_artifacts(
    project_dir: Path,
    old_feature: str,
    new_feature: str,
) -> int:
    """Move on-disk ``.debug`` artifacts when a manifest feature slug changes.

    Returns:
        Number of files or directories moved on disk.
    """
    import shutil

    if old_feature == new_feature:
        return 0

    moved = 0
    old_root = screen_root(project_dir, old_feature)
    new_root = screen_root(project_dir, new_feature)
    if old_root.is_dir():
        if new_root.exists():
            for path in sorted(old_root.rglob("*")):
                if not path.is_file():
                    continue
                relative = path.relative_to(old_root)
                destination = new_root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.is_file():
                    destination.unlink()
                shutil.move(str(path), str(destination))
                moved += 1
            shutil.rmtree(old_root, ignore_errors=True)
        else:
            shutil.move(str(old_root), str(new_root))
            moved += 1

    # Legacy v2 shards when the screen folder did not exist yet.
    legacy_moves: list[tuple[Path, Path]] = []
    for resolver in (legacy_v2_raw_dump_path, legacy_v2_processed_dump_path):
        old_path = resolver(project_dir, old_feature)
        if old_path.is_file():
            legacy_moves.append((old_path, resolver(project_dir, new_feature)))

    for snapshot in ("plan", "final", "bug"):
        old_path = legacy_v2_dart_debug_snapshot_path(project_dir, old_feature, snapshot)
        if old_path.is_file():
            legacy_moves.append(
                (
                    old_path,
                    legacy_v2_dart_debug_snapshot_path(project_dir, new_feature, snapshot),
                ),
            )

    old_reference = legacy_v2_emitter_reference_bundle_path(project_dir, old_feature)
    if old_reference.is_file():
        legacy_moves.append(
            (
                old_reference,
                legacy_v2_emitter_reference_bundle_path(project_dir, new_feature),
            ),
        )

    ir_dir = project_dir / FIGMA_DEBUG_DIR / IR_DIR
    if ir_dir.is_dir():
        prefix = f"{old_feature}_"
        for old_ir in ir_dir.glob(f"{old_feature}_*.json"):
            suffix = old_ir.name[len(prefix) :]
            legacy_moves.append((old_ir, ir_dir / f"{new_feature}_{suffix}"))

    reports_dir = project_dir / FIGMA_DEBUG_DIR / REPORTS_DIR
    for suffix in ("_ai_ux.json",):
        old_report = reports_dir / f"{old_feature}{suffix}"
        if old_report.is_file():
            legacy_moves.append((old_report, reports_dir / f"{new_feature}{suffix}"))

    for source, destination in legacy_moves:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_file():
            destination.unlink()
        shutil.move(str(source), str(destination))
        moved += 1
    return moved


def resolve_screen_raw_dump(
    project_dir: Path,
    feature_name: str,
    node_id: str,
    *,
    explicit: Path | None = None,
) -> Path:
    """Resolve an existing per-screen raw dump path."""
    candidates: list[Path] = []
    if explicit is not None:
        candidates.append(explicit)
    candidates.extend(
        (
            raw_dump_path(project_dir, feature_name),
            legacy_v2_raw_dump_path(project_dir, feature_name),
            legacy_raw_dump_path(project_dir, node_id),
        )
    )
    for path in candidates:
        if path.is_file():
            return path
    return explicit or raw_dump_path(project_dir, feature_name)
