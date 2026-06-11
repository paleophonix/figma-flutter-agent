"""Post-generation Dart validation package."""

from figma_flutter_agent.tools.process_run import run_subprocess  # re-export for mock patching

from .analyze import (
    PlannedAnalyzeWorkspace,
    ProjectAnalyzeResult,
    _analyze_failure_details,
    _analyze_has_errors,
    _build_analyze_command,
    _dart_analyze_timeout_sec,
    _dart_paths,
    _run_scoped_dart_analyze,
    _timeout_analyze_result,
    _validate_dart_project_inner,
    validate_dart_project,
)
from .errors import (
    collect_analyze_error_lines,
    normalize_analyzer_errors_for_fingerprint,
    parse_analyze_errors,
    parse_format_errors,
    parse_format_failed_paths,
    summarize_analyze_diagnostics,
)
from .format import (
    _dart_format_file_targets,
    _delimiter_gate_format_failure,
    _filter_dart_format_targets_by_size,
    _filter_minified_layout_format_targets,
    _partition_format_targets_by_delimiters,
    _run_dart_format_after_batch_timeout,
    _run_dart_format_batch,
    _run_dart_format_on_files,
    _run_dart_format_per_file_sequential,
    _run_dart_format_single_file,
    _run_dart_format_targets,
)
from .format_limits import (
    _dart_format_batch_size_summary,
    _dart_format_batch_timeout,
    _dart_format_per_file_timeout,
    _dart_format_single_file_timeout,
    _dart_format_timeout_allows_skip,
    _dart_source_is_minified,
    _dart_source_passes_delimiter_gate,
    _partition_format_targets_by_size,
    _relative_dart_path,
)
from .format_recovery import _recover_project_format_failures
from .planned import (
    PlannedAnalyzeOutcome,
    _filter_errors_for_paths,
    _planned_delimiter_error_messages,
    _repair_or_fallback_planned_delimiter_errors,
    _widget_planned_paths,
    gate_planned_dart_syntax,
)
from .planned_analyze import analyze_planned_dart_files, validate_planned_dart_files
from .toolchain import (
    _dart_format_target_detail,
    _read_package_name,
    _resolve_dart_executable,
    _run_flutter_pub_get,
    _strip_windows_zone_identifier_noise,
    _toolchain_executables,
    _validate_package_imports,
    align_skeleton_pubspec_package_name,
)

__all__ = [
    # analyze
    "PlannedAnalyzeWorkspace",
    "ProjectAnalyzeResult",
    "_analyze_failure_details",
    "_analyze_has_errors",
    "_build_analyze_command",
    "_dart_analyze_timeout_sec",
    "_dart_paths",
    "_run_scoped_dart_analyze",
    "_timeout_analyze_result",
    "_validate_dart_project_inner",
    "validate_dart_project",
    # errors
    "collect_analyze_error_lines",
    "normalize_analyzer_errors_for_fingerprint",
    "parse_analyze_errors",
    "parse_format_errors",
    "parse_format_failed_paths",
    "summarize_analyze_diagnostics",
    # format
    "_dart_format_batch_size_summary",
    "_dart_format_batch_timeout",
    "_dart_format_file_targets",
    "_dart_format_per_file_timeout",
    "_dart_format_single_file_timeout",
    "_dart_format_timeout_allows_skip",
    "_dart_source_is_minified",
    "_dart_source_passes_delimiter_gate",
    "_delimiter_gate_format_failure",
    "_filter_dart_format_targets_by_size",
    "_filter_minified_layout_format_targets",
    "_partition_format_targets_by_delimiters",
    "_partition_format_targets_by_size",
    "_recover_project_format_failures",
    "_relative_dart_path",
    "_run_dart_format_after_batch_timeout",
    "_run_dart_format_batch",
    "_run_dart_format_on_files",
    "_run_dart_format_per_file_sequential",
    "_run_dart_format_single_file",
    "_run_dart_format_targets",
    # planned
    "PlannedAnalyzeOutcome",
    "_filter_errors_for_paths",
    "_planned_delimiter_error_messages",
    "_repair_or_fallback_planned_delimiter_errors",
    "_widget_planned_paths",
    "analyze_planned_dart_files",
    "gate_planned_dart_syntax",
    "validate_planned_dart_files",
    # toolchain
    "_dart_format_target_detail",
    "_read_package_name",
    "_resolve_dart_executable",
    "_run_flutter_pub_get",
    "_strip_windows_zone_identifier_noise",
    "_toolchain_executables",
    "_validate_package_imports",
    "align_skeleton_pubspec_package_name",
]
