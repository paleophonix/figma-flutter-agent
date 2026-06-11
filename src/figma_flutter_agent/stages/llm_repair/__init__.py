"""LLM repair stage package."""

# Re-export external dependencies used by loop.py so monkeypatch can target this module
from figma_flutter_agent.generator.dart.project_validation import analyze_planned_dart_files
from figma_flutter_agent.generator.planned.reconcile import (
    reconcile_planned_dart_files,
    repair_planned_format_parse_failures,
)

from .loop import (
    _rollback_repair_to_baseline,
    _should_run_repair,
    run_analyze_repair_loop,
)
from .models import (
    LlmRepairStageRequest,
    LlmRepairStageResult,
)
from .replan import (
    _materialize_generation_for_replan,
    replan_planned_files,
)
from .snapshot import (
    _apply_extracted_widget_reference_fixup,
    _errors_suggest_extracted_widget_drift,
    _GenerationSnapshot,
    _repair_generation_unchanged,
    _restore_generation,
    _screen_ir_fingerprint,
    _snapshot_generation,
    _widget_ir_fingerprint,
)
from .syntax import (
    CRITICAL_SYNTAX_BROKEN_TAG,
    _critical_syntax_broken_directive,
    _format_failure_paths_from_outcome,
    _is_syntax_level_analyze_failure,
    _planned_files_have_delimiter_syntax_errors,
    _repair_patch_has_duplicate_required_this,
    _rollback_planned_files_to_snapshot,
    _syntax_error_count,
    _syntax_repair_stalled,
    rollback_file_on_syntax_error,
)

__all__ = [
    "LlmRepairStageRequest",
    "LlmRepairStageResult",
    "replan_planned_files",
    "rollback_file_on_syntax_error",
    "run_analyze_repair_loop",
]
