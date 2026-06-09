"""Golden capture validation package."""

from .capture import (
    GoldenCaptureHostSession,
    GoldenCaptureResult,
    _ensure_docker_golden_image,
    _resolve_host_capture_test,
    capture_planned_flutter_golden_png,
    capture_planned_flutter_golden_png_docker,
    capture_planned_flutter_golden_png_host,
)
from .logs import _clip_reason, _first_process_line, _log_process_output
from .paths import (
    _read_figma_key_rects,
    capture_test_relative_path,
    collect_planned_asset_paths,
    golden_figma_keys_relative_path,
    golden_png_relative_path,
    golden_test_relative_path,
)
from .project import (
    _copy_skeleton_project,
    _ensure_pubspec_asset_dirs,
    _ensure_pubspec_asset_directories_on_disk,
    _materialize_capture_workspace,
    _merge_pubspec_fonts_and_assets,
    _prepare_capture_workspace,
    _prepare_flutter_test_build_dir,
    _run_flutter_pub_get,
    _safe_temp_cleanup,
    _sync_fonts_folder,
    _sync_project_assets,
    _sync_referenced_assets,
    _sync_theme_lib,
)
from figma_flutter_agent.dev.flutter_sdk import resolve_flutter_executable
from figma_flutter_agent.validation.golden_runtime import resolve_golden_runtime

__all__ = [
    "GoldenCaptureHostSession",
    "GoldenCaptureResult",
    "capture_planned_flutter_golden_png",
    "capture_planned_flutter_golden_png_docker",
    "capture_planned_flutter_golden_png_host",
    "capture_test_relative_path",
    "collect_planned_asset_paths",
    "golden_figma_keys_relative_path",
    "golden_png_relative_path",
    "golden_test_relative_path",
]
