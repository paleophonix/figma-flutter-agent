"""Map analyzer errors to scoped repair targets and APR prompt environment."""

from __future__ import annotations

from figma_flutter_agent.llm.repair_scope.environment import (
    build_repair_environment_context,
    format_analyze_errors_block,
    format_failed_attempts_history,
    format_focused_error_context,
    format_repair_attempt_record,
    format_unchanged_widget_names_block,
)
from figma_flutter_agent.llm.repair_scope.locations import (
    dedupe_analyze_errors,
    parse_analyze_error_locations,
    resolve_planned_relative_path,
)
from figma_flutter_agent.llm.repair_scope.models import (
    AnalyzeErrorLocation,
    RepairEnvironmentContext,
    RepairScope,
    RepairTarget,
)
from figma_flutter_agent.llm.repair_scope.paths import (
    expand_ast_reconcile_paths,
    repair_scope_planned_paths,
)
from figma_flutter_agent.llm.repair_scope.semantic import extract_semantic_hint
from figma_flutter_agent.llm.repair_scope.targets import (
    build_repair_scope,
    select_primary_repair_target,
)
