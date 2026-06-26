"""Canonical paths for ``.debug`` screen artifacts (project-scoped layout v9).

Screen artifacts live under ``<agent_repo>/.debug/<project>/<feature>/``.
Warm capture sandbox lives under ``<workspace>/.sandbox/``. Flutter project roots
keep ``wizard-state.yml`` and ``pubspec_resolve.sha256`` only.
"""

from __future__ import annotations

import re
from pathlib import Path

from loguru import logger

from figma_flutter_agent.config import agent_repo_root

FIGMA_DEBUG_DIR = ".debug"
SCREEN_DEBUG_SUBDIR = "screen"
AGENT_DEBUG_SUBDIR = "agent"
AGENT_TRACE_SUBDIR = "trace"
AGENT_REPAIR_SUBDIR = "repair"
LEGACY_FIGMA_DEBUG_DIR = ".figma_debug"
LEGACY_AGENT_DIR = ".figma-flutter"
FIGMA_FLUTTER_META_DIR = ".figma-flutter"
LAYOUT_VERSION_FILE = "layout-version"
PUBSPEC_RESOLVE_STAMP_FILE = "pubspec_resolve.sha256"
CAPTURE_SANDBOX_META_DIR = "capture-sandbox"

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
CAPTURE_PNG = "capture.png"
CAPTURE_MANIFEST_JSON = "capture.json"
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
DART_ERRORS_JSON = "dart-errors.json"
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
ARTIFACT_LAYOUT_VERSION = 12
WORKSPACE_SANDBOX_DIR = ".sandbox"

FIGMA_REFERENCE_REL = f"{FIGMA_DEBUG_DIR}/<project>/<feature>/{FIGMA_PNG}"
EMITTER_REFERENCE_REL = f"{FIGMA_DEBUG_DIR}/<project>/<feature>/{EMITTER_REF_DART}"
_IR_STAGE_FILENAMES: dict[str, str] = {
    "llm_parsed": "llm_parsed.json",
    "compare_ir_1": "ir_1.json",
    "compare_ir_2": "ir_2.json",
    "compare_ir_3": "ir_3.json",
    "llm_validated": "llm_validated.json",
    "pre_emit": "pre_emit.json",
    "semantic_context": "semantic_context.json",
    "semantic_verdicts": "semantic_verdicts.json",
    "element_contracts": "element_contracts.json",
    "contract_emit_diff": "contract_emit_diff.json",
}
_STAGE_SAFE_RE = re.compile(r"[^\w.-]+")
_PROJECT_LABEL_RE = re.compile(r"[^\w.-]+")


def screen_debug_safe_feature(feature_name: str) -> str:
    """Sanitize a feature slug for ``.debug/<project>/<feature>/`` directory names."""
    return feature_name.replace("/", "_").replace("\\", "_").strip() or "screen"


def screen_debug_safe_project(project_dir: Path) -> str:
    """Sanitize Flutter project folder name for ``.debug/<project>/`` (e.g. ``limbo``, ``ataev``)."""
    return screen_debug_safe_feature(project_dir.name) or "project"


def legacy_combined_project_label(project_dir: Path) -> str:
    """Deprecated v9 label ``<parent>_<folder>`` (e.g. ``sandbox_limbo``) for migration fallback."""
    resolved = project_dir.resolve()
    parts = resolved.parts[-2:] if len(resolved.parts) >= 2 else resolved.parts[-1:]
    label = "_".join(_PROJECT_LABEL_RE.sub("_", part).strip("_") for part in parts if part)
    return label or "project"


def agent_debug_root() -> Path:
    """Return the agent-repo ``.debug`` root for all screen artifacts."""
    return agent_repo_root() / FIGMA_DEBUG_DIR


def screen_debug_root() -> Path:
    """Return ``<agent_repo>/.debug/screen`` for generate pipeline artifacts."""
    return agent_debug_root() / SCREEN_DEBUG_SUBDIR


def agent_artifact_root() -> Path:
    """Return ``<agent_repo>/.debug/agent`` for repair/trace artifacts."""
    return agent_debug_root() / AGENT_DEBUG_SUBDIR


def agent_feature_root(project_dir: Path, feature_name: str) -> Path:
    """Return ``.debug/agent/<project>/<feature>/`` for one repair case."""
    return (
        agent_artifact_root()
        / screen_debug_safe_project(project_dir)
        / screen_debug_safe_feature(feature_name)
    )


def agent_trace_root(project_dir: Path, feature_name: str) -> Path:
    """Return overwrite-friendly repair trace dir for one screen."""
    return agent_feature_root(project_dir, feature_name) / AGENT_TRACE_SUBDIR


def agent_repair_export_root(project_dir: Path, feature_name: str) -> Path:
    """Return exported repair workspace artifacts for one screen."""
    return agent_feature_root(project_dir, feature_name) / AGENT_REPAIR_SUBDIR


def legacy_project_debug_root(project_dir: Path) -> Path:
    """Return deprecated per-project ``<project>/.debug`` (migration source only)."""
    return project_dir / FIGMA_DEBUG_DIR


def legacy_project_screen_root(project_dir: Path, feature_name: str) -> Path:
    """Return deprecated ``<project>/.debug/<feature>/`` (migration source only)."""
    return legacy_project_debug_root(project_dir) / screen_debug_safe_feature(feature_name)


def debug_path_display(path: Path, project_dir: Path | None = None) -> str:
    """Return a stable relative path for debug artifacts (agent-repo or project root).

    Args:
        path: Absolute or relative debug artifact path.
        project_dir: Optional Flutter project root for legacy relative display.

    Returns:
        Posix path relative to ``project_dir`` or the agent repo, else absolute posix.
    """
    resolved = path.expanduser().resolve()
    roots: list[Path] = []
    if project_dir is not None:
        roots.append(project_dir.expanduser().resolve())
    roots.append(agent_repo_root().resolve())
    for root in roots:
        try:
            return resolved.relative_to(root).as_posix()
        except ValueError:
            continue
    return resolved.as_posix()


def project_debug_root(project_dir: Path) -> Path:
    """Return ``<agent_repo>/.debug/screen/<project>/`` for one Flutter project."""
    return screen_debug_root() / screen_debug_safe_project(project_dir)


def project_debug_root_candidates(project_dir: Path) -> list[Path]:
    """Return candidate project debug roots (v12 screen/, then legacy flat ``.debug/<project>/``)."""
    agent_debug = agent_debug_root()
    labels: list[str] = []
    for label in (
        screen_debug_safe_project(project_dir),
        legacy_combined_project_label(project_dir),
    ):
        if label and label not in labels:
            labels.append(label)
    candidates: list[Path] = []
    for label in labels:
        candidates.append(screen_debug_root() / label)
        candidates.append(agent_debug / label)
    return candidates


def legacy_flat_agent_screen_root(feature_name: str) -> Path:
    """Return deprecated ``<agent_repo>/.debug/<feature>/`` (v8 flat layout)."""
    return agent_debug_root() / screen_debug_safe_feature(feature_name)


def screen_root(project_dir: Path, feature_name: str) -> Path:
    """Return ``<agent_repo>/.debug/screen/<project>/<feature>/`` for one screen."""
    return project_debug_root(project_dir) / screen_debug_safe_feature(feature_name)


def _path_is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def resolve_flutter_workspace_root(project_dir: Path) -> Path:
    """Return the Flutter workspace root that owns ``project_dir``.

    Precedence: ``FIGMA_FLUTTER_PROJECT_DIR`` when it contains the project,
    nearest ancestor with ``workspace-state.yml``, else a multi-app parent directory.

    Args:
        project_dir: Resolved Flutter project root or path under a workspace.

    Returns:
        Workspace directory (for example ``apps/``).
    """
    from figma_flutter_agent.dev.project import (
        discover_flutter_projects,
        env_configured_workspace_root,
        is_flutter_project_root,
    )

    project = project_dir.expanduser().resolve()
    configured = env_configured_workspace_root()
    if configured is not None:
        workspace = configured.resolve()
        if project == workspace or _path_is_under(project, workspace):
            return workspace

    cursor = project
    while True:
        if (cursor / WORKSPACE_STATE_FILE).is_file():
            return cursor
        if cursor.parent == cursor:
            break
        cursor = cursor.parent

    parent = project.parent
    if is_flutter_project_root(project):
        if parent.is_dir():
            siblings = discover_flutter_projects(parent)
            if len(siblings) > 1 and project in siblings:
                return parent
        return project
    return project


def project_meta_dir(project_dir: Path) -> Path:
    """Return deprecated ``<project>/.figma-flutter/`` (legacy migration source only)."""
    return project_dir / FIGMA_FLUTTER_META_DIR


def legacy_project_meta_layout_marker_path(project_dir: Path) -> Path:
    """Return deprecated layout marker under ``<project>/.figma-flutter/``."""
    return project_meta_dir(project_dir) / LAYOUT_VERSION_FILE


def project_layout_marker_path(project_dir: Path) -> Path:
    """Return the layout migration version stamp under agent ``.debug/<project>/``."""
    return project_debug_root(project_dir) / LAYOUT_VERSION_FILE


def legacy_project_layout_marker_path(project_dir: Path) -> Path:
    """Return deprecated v3 layout marker under ``.debug/``."""
    return project_dir / FIGMA_DEBUG_DIR / ARTIFACT_LAYOUT_MARKER


def legacy_project_layout_marker_v2_path(project_dir: Path) -> Path:
    """Return deprecated v2 layout marker under ``.debug/``."""
    return project_dir / FIGMA_DEBUG_DIR / ARTIFACT_LAYOUT_MARKER_V2


def pubspec_resolve_stamp_path(project_dir: Path) -> Path:
    """Return the pubspec resolve digest stamp at the Flutter project root."""
    return project_dir / PUBSPEC_RESOLVE_STAMP_FILE


def legacy_pubspec_resolve_stamp_path(project_dir: Path) -> Path:
    """Return deprecated pubspec stamp under ``.debug/``."""
    return project_dir / FIGMA_DEBUG_DIR / PUBSPEC_RESOLVE_STAMP_FILE


def screen_primary_dir(project_dir: Path, feature_name: str) -> Path:
    """Deprecated alias for :func:`screen_root` (v3 ``primary/`` removed in v4)."""
    return screen_root(project_dir, feature_name)


def screen_secondary_dir(project_dir: Path, feature_name: str) -> Path:
    """Deprecated alias for :func:`screen_root` (v3 ``secondary/`` removed in v4)."""
    return screen_root(project_dir, feature_name)


def shared_debug_dir(project_dir: Path) -> Path:
    """Return ``<agent>/.debug/<project>/shared/`` for full-file batch dumps."""
    return project_debug_root(project_dir) / SHARED_DIR


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
    """Return the flat per-screen IR JSON path for ``feature_name`` and ``stage``."""
    filename = _ir_artifact_filename(stage)
    return screen_root(project_dir, feature_name) / filename


def compare_ir_artifact_path(project_dir: Path, feature_name: str, index: int) -> Path:
    """Return ``.debug/screen/<project>/<feature>/ir_<index>.json`` for wizard compare."""
    if index not in {1, 2, 3}:
        msg = f"compare IR index must be 1, 2, or 3; got {index!r}"
        raise ValueError(msg)
    stage = f"compare_ir_{index}"
    return screen_ir_dump_path(project_dir, feature_name, stage)


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


def legacy_figma_debug_v2_raw_dump_path(project_dir: Path, feature_name: str) -> Path:
    """Return deprecated ``.figma_debug/raw/<feature>_layout.json``."""
    return project_dir / LEGACY_FIGMA_DEBUG_DIR / RAW_DIR / layout_debug_filename(feature_name)


def legacy_v2_processed_dump_path(project_dir: Path, feature_name: str) -> Path:
    """Return deprecated ``.debug/processed/<feature>_layout.json``."""
    return project_dir / FIGMA_DEBUG_DIR / PROCESSED_DIR / layout_debug_filename(feature_name)


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
    return project_dir / FIGMA_DEBUG_DIR / FIGMA_REFERENCE_SUBDIR / f"{feature_name}_figma.png"


def legacy_figma_reference_dir(project_dir: Path) -> Path:
    """Return deprecated ``.figma-flutter/reference`` (pre-consolidation)."""
    return project_dir / LEGACY_AGENT_DIR / REFERENCE_DIR


def sync_snapshot_path(project_dir: Path, feature_name: str) -> Path:
    """Return per-screen incremental sync snapshot at ``.debug/<feature>/snapshot.json``."""
    return screen_root(project_dir, feature_name) / SNAPSHOT_FILE_NAME


def legacy_project_sync_snapshot_path(project_dir: Path) -> Path:
    """Return deprecated project-wide snapshot under ``.debug/sync/``."""
    return project_dir / FIGMA_DEBUG_DIR / SYNC_DIR / SNAPSHOT_FILE_NAME


def legacy_sync_snapshot_path(project_dir: Path) -> Path:
    """Return deprecated ``.figma-flutter/snapshot.json``."""
    return project_dir / LEGACY_AGENT_DIR / SNAPSHOT_FILE_NAME


def capture_sandbox_dir(project_dir: Path) -> Path:
    """Return warm capture sandbox at ``<workspace>/.sandbox/``."""
    return resolve_flutter_workspace_root(project_dir) / WORKSPACE_SANDBOX_DIR


def legacy_agent_capture_sandbox_dir(project_dir: Path) -> Path:
    """Deprecated ``<agent>/.debug/<project>/capture/sandbox`` warm sandbox path."""
    return project_debug_root(project_dir) / DEBUG_CAPTURE_DIR / CAPTURE_SANDBOX_SUBDIR


def legacy_capture_sandbox_meta_dir(project_dir: Path) -> Path:
    """Deprecated ``<project>/.figma-flutter/capture-sandbox`` warm sandbox path."""
    return project_meta_dir(project_dir) / CAPTURE_SANDBOX_META_DIR


def debug_capture_root(project_dir: Path) -> Path:
    """Deprecated alias for :func:`capture_sandbox_dir` parent (warm capture only)."""
    return capture_sandbox_dir(project_dir).parent


def screen_capture_dir(project_dir: Path, feature_name: str) -> Path:
    """Return flat per-screen capture directory (same as :func:`screen_root`)."""
    return screen_root(project_dir, feature_name)


def debug_capture_safe_feature(feature_name: str) -> str:
    """Sanitize a feature slug for legacy flat capture filenames."""
    return screen_debug_safe_feature(feature_name)


def debug_capture_artifact_path(
    project_dir: Path,
    feature_name: str,
    artifact: str,
) -> Path:
    """Return a per-screen capture artifact under ``secondary/capture/``.

    Figma gold is canonical under ``.debug/<project>/<feature>/figma.png``, not duplicated here.
    """
    suffix_by_artifact = {
        "capture": CAPTURE_PNG,
        "flutter_render": CAPTURE_PNG,
        "preview_capture": "preview_capture.png",
        "diff_heatmap": "diff_heatmap.png",
        "manifest": CAPTURE_MANIFEST_JSON,
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


def legacy_project_run_logs_dir(project_dir: Path) -> Path:
    """Return deprecated ``.debug/logs/`` directory."""
    return project_dir / FIGMA_DEBUG_DIR / RUN_LOGS_SUBDIR


def project_run_log_path(project_dir: Path, feature_name: str) -> Path:
    """Return per-screen run transcript at ``.debug/<feature>/last.log``."""
    return screen_root(project_dir, feature_name) / LAST_RUN_LOG_FILE


def dart_errors_json_path(project_dir: Path, feature_name: str) -> Path:
    """Return structured Dart analyzer failures at ``.debug/<feature>/dart-errors.json``."""
    return screen_root(project_dir, feature_name) / DART_ERRORS_JSON


def legacy_project_run_log_path(project_dir: Path) -> Path:
    """Return deprecated project-wide ``.debug/logs/last.log``."""
    return legacy_project_run_logs_dir(project_dir) / LAST_RUN_LOG_FILE


def last_terminal_log_path(project_dir: Path, feature_name: str) -> Path:
    """Deprecated alias for :func:`project_run_log_path`."""
    return project_run_log_path(project_dir, feature_name)


def render_session_dir(
    project_dir: Path,
    log_stem: str,
    *,
    feature_name: str | None = None,
) -> Path:
    """Return combat-mode PNG session directory for one screen."""
    if feature_name is not None:
        return screen_root(project_dir, feature_name) / RENDERS_SUBDIR / log_stem
    _ = project_dir
    return agent_debug_root() / RENDERS_SUBDIR / log_stem


def screen_perf_dir(project_dir: Path, feature_name: str) -> Path:
    """Return ``.debug/<feature>/perf/``."""
    return screen_root(project_dir, feature_name) / SECONDARY_PERF_DIR


def perf_dir(project_dir: Path) -> Path:
    """Deprecated project-level perf directory (v2); prefer :func:`screen_perf_dir`."""
    return project_dir / FIGMA_DEBUG_DIR / PERF_SUBDIR


def project_wizard_prefs_path(project_dir: Path) -> Path:
    """Return wizard prefs at the Flutter project root."""
    return project_dir / WIZARD_STATE_FILE


def legacy_project_wizard_prefs_path(project_dir: Path) -> Path:
    """Return deprecated wizard prefs under ``.debug/``."""
    return project_dir / FIGMA_DEBUG_DIR / WIZARD_STATE_FILE


def workspace_prefs_path(workspace_root: Path) -> Path:
    """Return workspace-level wizard prefs at the workspace root."""
    return workspace_root / WORKSPACE_STATE_FILE


def legacy_workspace_prefs_path(workspace_root: Path) -> Path:
    """Return deprecated workspace prefs under ``workspace_root/.debug/``."""
    return workspace_root / FIGMA_DEBUG_DIR / WORKSPACE_STATE_FILE


def legacy_workspace_agent_prefs_path(workspace_root: Path) -> Path:
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
    return project_dir / FIGMA_DEBUG_DIR / EMITTER_REFERENCE_SUBDIR / f"{feature_name}_screen.dart"


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
        return screen_root(project_dir, feature_name) / SCREEN_BUG_DART
    if snapshot == "plan":
        return screen_root(project_dir, feature_name) / PLAN_DART
    if snapshot == "final":
        return screen_root(project_dir, feature_name) / SCREEN_DART
    msg = f"Unknown dart debug snapshot {snapshot!r}; expected plan, final, or bug"
    raise ValueError(msg)


def legacy_v2_dart_debug_snapshot_path(
    project_dir: Path,
    feature_name: str,
    snapshot: str,
) -> Path:
    """Return deprecated v2 dart bundle paths under ``dart/`` and ``dart.bug/``."""
    if snapshot == "bug":
        return project_dir / FIGMA_DEBUG_DIR / DART_BUG_DIR / f"{feature_name}_screen.dart"
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


def _log_legacy_debug_path_used(resolver: str, path: Path) -> None:
    """Log when a legacy debug artifact path is selected instead of v9 canonical."""
    logger.info(
        "legacy_debug_path_used resolver={} path={}",
        resolver,
        path.as_posix(),
    )


def _first_existing_file(
    *candidates: Path,
    resolver: str | None = None,
) -> Path | None:
    for index, path in enumerate(candidates):
        if path.is_file():
            if resolver is not None and index > 0:
                _log_legacy_debug_path_used(resolver, path)
            return path
    return None


def _screen_raw_dump_candidate_paths(
    project_dir: Path,
    feature_name: str,
    node_id: str,
    *,
    explicit: Path | None = None,
) -> list[Path]:
    """Ordered raw-dump search paths from canonical v9 through legacy layouts."""
    safe_feature = screen_debug_safe_feature(feature_name)
    candidates: list[Path] = []
    if explicit is not None:
        candidates.append(explicit)
    for project_root in project_debug_root_candidates(project_dir):
        candidates.append(project_root / safe_feature / RAW_JSON)
    candidates.extend(
        (
            legacy_flat_agent_screen_root(feature_name) / RAW_JSON,
            legacy_project_screen_root(project_dir, feature_name) / RAW_JSON,
            legacy_v2_raw_dump_path(project_dir, feature_name),
            legacy_figma_debug_v2_raw_dump_path(project_dir, feature_name),
        )
    )
    if node_id:
        candidates.append(legacy_raw_dump_path(project_dir, node_id))

    seen: set[Path] = set()
    ordered: list[Path] = []
    for path in candidates:
        resolved = path.expanduser().resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        ordered.append(path)
    return ordered


def resolve_unique_agent_feature_dump(feature_name: str) -> Path | None:
    """Return ``.debug/<project>/<feature>/raw.json`` when exactly one exists under agent ``.debug``."""
    safe_feature = screen_debug_safe_feature(feature_name)
    matches = sorted(agent_debug_root().glob(f"*/{safe_feature}/{RAW_JSON}"))
    if len(matches) == 1:
        return matches[0]
    return None


def resolve_unique_agent_feature_ir_dump(feature_name: str, stage: str) -> Path | None:
    """Return one IR JSON under ``.debug/*/feature/`` when unambiguous for ``stage``."""
    safe_feature = screen_debug_safe_feature(feature_name)
    filename = _ir_artifact_filename(stage)
    matches = sorted(agent_debug_root().glob(f"*/{safe_feature}/{filename}"))
    if len(matches) == 1:
        return matches[0]
    return None


def resolve_raw_dump_path(project_dir: Path, feature_name: str) -> Path | None:
    """Return the first existing raw dump path (v9, short project label, then legacy)."""
    for path in _screen_raw_dump_candidate_paths(project_dir, feature_name, node_id=""):
        if path.is_file():
            return path
    return resolve_unique_agent_feature_dump(feature_name)


def resolve_processed_dump_path(project_dir: Path, feature_name: str) -> Path | None:
    """Return the first existing processed dump path (v9, v8 flat, project v4, then v2)."""
    legacy_project = legacy_project_screen_root(project_dir, feature_name) / PROCESSED_JSON
    return _first_existing_file(
        processed_dump_path(project_dir, feature_name),
        legacy_flat_agent_screen_root(feature_name) / PROCESSED_JSON,
        legacy_project,
        legacy_v2_processed_dump_path(project_dir, feature_name),
        resolver="resolve_processed_dump_path",
    )


def resolve_screen_ir_dump_file(
    project_dir: Path,
    feature_name: str,
    stage: str,
) -> Path | None:
    """Return the first existing IR dump for ``stage`` (v9, short project label, then legacy)."""
    filename = _ir_artifact_filename(stage)
    safe_feature = screen_debug_safe_feature(feature_name)
    legacy_project = legacy_project_screen_root(project_dir, feature_name) / filename
    candidates: list[Path] = []
    for project_root in project_debug_root_candidates(project_dir):
        candidates.append(project_root / safe_feature / filename)
    candidates.extend(
        (
            legacy_flat_agent_screen_root(feature_name) / filename,
            legacy_project,
            legacy_v2_screen_ir_dump_path(project_dir, feature_name, stage),
        )
    )
    seen: set[Path] = set()
    for path in candidates:
        resolved = path.expanduser().resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.is_file():
            return resolved
    return resolve_unique_agent_feature_ir_dump(feature_name, stage)


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
    for path in _screen_raw_dump_candidate_paths(
        project_dir,
        feature_name,
        node_id,
        explicit=explicit,
    ):
        if path.is_file():
            return path
    unique = resolve_unique_agent_feature_dump(feature_name)
    if unique is not None:
        return unique
    return raw_dump_path(project_dir, feature_name)
