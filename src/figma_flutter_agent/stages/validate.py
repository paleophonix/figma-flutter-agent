"""Validate stage for generated Dart contracts."""

from __future__ import annotations

from dataclasses import dataclass, field

from figma_flutter_agent.generator.checks.validate import validate_generated_dart
from figma_flutter_agent.generator.widget_validation import validate_cluster_widget_extraction
from figma_flutter_agent.schemas import CleanDesignTreeNode


@dataclass
class ValidateStageRequest:
    """Inputs required to validate planned generated Dart files."""

    planned_files: dict[str, str]
    clean_trees: list[CleanDesignTreeNode]
    responsive_enabled: bool
    avoid_fixed_sizes: bool
    require_overlay_helpers: bool = False
    strict_accessibility_labels: bool = False
    cluster_summary: dict[str, int] | None = None
    cluster_min_count: int = 2
    widget_suffix: str = "Widget"
    enforce_cluster_widgets: bool = True
    fail_duplicate_clusters: bool = False
    require_responsive_shell: bool | None = None
    require_reflow: bool = False


@dataclass
class ValidateStageResult:
    """Output of the validation stage."""

    warnings: list[str] = field(default_factory=list)


def validate_planned_generation(request: ValidateStageRequest) -> ValidateStageResult:
    """Validate planned Dart files against accessibility and responsive contracts.

    Args:
        request: Planned files and parsed design trees to validate.

    Returns:
        Non-fatal validation warnings.

    Raises:
        GenerationError: When required accessibility or responsive contracts fail.
    """
    cluster_summary = request.cluster_summary or {}
    validate_cluster_widget_extraction(
        request.planned_files,
        request.clean_trees,
        cluster_summary,
        min_count=request.cluster_min_count,
        widget_suffix=request.widget_suffix,
        enforce_cluster_widgets=request.enforce_cluster_widgets,
        fail_duplicate_clusters=request.fail_duplicate_clusters,
    )
    warnings = validate_generated_dart(
        request.planned_files,
        request.clean_trees,
        responsive_enabled=request.responsive_enabled,
        avoid_fixed_sizes=request.avoid_fixed_sizes,
        require_overlay_helpers=request.require_overlay_helpers,
        strict_accessibility_labels=request.strict_accessibility_labels,
        require_responsive_shell=request.require_responsive_shell,
        require_reflow=request.require_reflow,
    )
    return ValidateStageResult(warnings=warnings)
