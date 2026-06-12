"""LLM stage orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from figma_flutter_agent.config import Settings
from figma_flutter_agent.errors import LlmError
from figma_flutter_agent.generator.paths import Architecture, screen_file_path
from figma_flutter_agent.generator.layout.common import to_pascal_case
from figma_flutter_agent.parser.prototype import PrototypeNavigationPlan
from figma_flutter_agent.pipeline.deps import LlmClientFactory
from figma_flutter_agent.schemas import (
    AssetManifest,
    CleanDesignTreeNode,
    DesignTokens,
    FlutterGenerationResponse,
)
from figma_flutter_agent.stages import LlmStageRequest, LlmStageResult, run_llm_stage


@dataclass(frozen=True)
class LlmPipelineOutcome:
    """LLM stage output and effective settings for planning."""

    plan_settings: Settings
    llm_result: LlmStageResult
    fallback_warnings: tuple[str, ...] = ()


def load_cached_ir_llm_outcome(
    log: Any,
    *,
    settings: Settings,
    project_dir: Path,
    resolved_feature: str,
    clean_tree: CleanDesignTreeNode,
    tokens: DesignTokens,
    from_ir_path: Path | None = None,
) -> LlmPipelineOutcome:
    """Skip LLM and load ``FlutterGenerationResponse`` from ``.debug/ir``.

    Args:
        log: Bound logger for info/warnings.
        settings: Active pipeline settings.
        project_dir: Flutter project root.
        resolved_feature: Screen feature slug for default IR filenames.
        clean_tree: Parsed tree used to validate/normalize IR before plan.
        tokens: Design tokens for IR asset/token guards.
        from_ir_path: Optional explicit IR JSON file or directory.

    Returns:
        Outcome with ``generation.screen_ir`` populated for the planner.
    """
    from figma_flutter_agent.debug.ir_load import (
        load_generation_from_ir_dump,
        resolve_screen_ir_dump_path,
    )
    ir_path = resolve_screen_ir_dump_path(
        project_dir,
        resolved_feature,
        explicit_path=from_ir_path,
    )
    generation = load_generation_from_ir_dump(ir_path)
    extracted = frozenset(widget.widget_name for widget in generation.extracted_widgets)
    generation = _normalize_cached_ir_generation(
        generation,
        clean_tree=clean_tree,
        extracted_names=extracted,
        project_dir=project_dir,
        tokens=tokens,
    )
    log.info("Loaded cached screen IR from {}", ir_path.as_posix())
    from figma_flutter_agent.pipeline.warning_policy import (
        cached_ir_user_warning,
        quiet_expected_warnings,
    )

    cached_warning = cached_ir_user_warning(
        f"Skipped LLM IR generation; using cached snapshot {ir_path.name}",
        settings=settings,
    )
    if cached_warning is None and quiet_expected_warnings(settings):
        log.info("Using cached screen IR snapshot {} (LLM skipped)", ir_path.name)
    return LlmPipelineOutcome(
        plan_settings=settings,
        llm_result=LlmStageResult(
            generation=generation,
            warnings=(cached_warning,) if cached_warning else (),
        ),
    )


def _normalize_cached_ir_generation(
    generation: FlutterGenerationResponse,
    *,
    clean_tree: CleanDesignTreeNode,
    extracted_names: frozenset[str],
    project_dir: Path,
    tokens: DesignTokens,
) -> FlutterGenerationResponse:
    from figma_flutter_agent.generator.ir.presence import normalize_screen_ir_presence
    from figma_flutter_agent.generator.ir.validate import (
        validate_extracted_widgets,
        validate_screen_ir,
    )

    if generation.screen_ir is None:
        return generation
    screen_ir = normalize_screen_ir_presence(
        generation.screen_ir,
        clean_tree,
        extracted_widget_names=extracted_names,
    )
    if screen_ir is not generation.screen_ir:
        generation = generation.model_copy(update={"screen_ir": screen_ir})
    validate_screen_ir(
        generation.screen_ir,
        clean_tree,
        extracted_widget_names=extracted_names,
        declared_extracted_widget_names=extracted_names,
        project_dir=project_dir,
        tokens=tokens,
    )
    if generation.extracted_widgets:
        validate_extracted_widgets(
            generation.extracted_widgets,
            clean_tree,
            project_dir=project_dir,
            tokens=tokens,
        )
    return generation


async def execute_llm_stage(
    log: Any,
    *,
    settings: Settings,
    dry_run: bool,
    resolved_sync: bool,
    incremental: Any,
    clean_tree: CleanDesignTreeNode,
    tokens: DesignTokens,
    resolved_feature: str,
    asset_manifest: AssetManifest,
    widget_hints: list[str],
    navigation_hints: list[str],
    routing_on: bool,
    navigation_plan: PrototypeNavigationPlan,
    frame_index: dict[str, dict[str, Any]],
    published_styles: dict[str, dict[str, Any]],
    components: dict[str, dict[str, Any]],
    component_sets: dict[str, dict[str, Any]],
    destination_trees: dict[str, CleanDesignTreeNode],
    destination_widget_hints: dict[str, list[str]],
    style_paint_index: dict[str, dict[str, Any]],
    force_llm_regen: bool,
    llm_client_factory: LlmClientFactory | None = None,
    figma_reference_png: bytes | None = None,
    project_dir: Path | None = None,
) -> LlmPipelineOutcome:
    """Run the LLM stage.

    Args:
        log: Bound logger for warnings.
        incremental: Object with ``tree_changed``, ``tokens_changed``,
            ``previous_snapshot_exists`` attributes (``IncrementalContext``-like).
        Other args: Forwarded to ``LlmStageRequest``.

    Returns:
        Effective settings and LLM stage result for planning.

    Raises:
        LlmError: When LLM fails and fallback is disabled.
    """
    llm_result = await run_llm_stage(
        LlmStageRequest(
            settings=settings,
            dry_run=dry_run,
            resolved_sync=resolved_sync,
            tree_changed=incremental.tree_changed,
            tokens_changed=incremental.tokens_changed,
            previous_snapshot_exists=incremental.previous_snapshot is not None,
            clean_tree=clean_tree,
            tokens=tokens,
            resolved_feature=resolved_feature,
            asset_manifest=asset_manifest,
            widget_hints=widget_hints,
            navigation_hints=navigation_hints,
            routing_on=routing_on,
            navigation_plan=navigation_plan,
            frame_index=frame_index,
            published_styles=published_styles,
            components=components,
            component_sets=component_sets,
            destination_trees=destination_trees,
            destination_widget_hints=destination_widget_hints,
            style_paint_index=style_paint_index,
            force_llm_regen=force_llm_regen,
            llm_client_factory=llm_client_factory,
            figma_reference_png=figma_reference_png,
            project_dir=project_dir,
        ),
    )
    requires_llm_output = incremental.tree_changed or force_llm_regen
    if (
        llm_result.llm_attempted
        and not llm_result.generation
        and requires_llm_output
        and not llm_result.skipped_incremental
    ):
        raise LlmError("Generation failed: no LLM output available")

    return LlmPipelineOutcome(
        plan_settings=settings,
        llm_result=llm_result,
    )


def append_llm_skip_warnings(
    warnings: list[str],
    *,
    llm_result: LlmStageResult,
    tokens_changed: bool,
) -> None:
    """Append user-facing warnings when the LLM stage was skipped."""
    if not llm_result.skipped_incremental:
        return
    if tokens_changed:
        warnings.append(
            "LLM screen skipped: design tree unchanged but tokens changed (theme-only sync). "
            "Use --force-llm-regen or enable generation.regen_llm_on_token_change."
        )
    else:
        warnings.append(
            "LLM generation skipped during incremental sync (unchanged design tree). "
            "Use --force-llm-regen to refresh screen output."
        )


def warn_if_llm_screen_delegates_to_layout(
    warnings: list[str],
    *,
    planned_files: dict[str, str],
    feature_name: str,
    architecture: Architecture = "feature_first",
    skip_when_expected: bool = False,
) -> None:
    """Warn when LLM mode still plans a screen that only wraps the layout file."""
    if skip_when_expected:
        return
    screen_path = screen_file_path(feature_name, architecture=architecture)
    source = planned_files.get(screen_path, "")
    layout_class = f"{to_pascal_case(feature_name)}Layout"
    if layout_class in source and f"{layout_class}()" in source:
        warnings.append(
            "LLM mode produced a screen that delegates to "
            f"{layout_class} (same pattern as deterministic output). "
            "Check pipeline logs for LLM or IR emitter errors."
        )


def ensure_llm_output_or_raise(
    *,
    llm_result: LlmStageResult,
    tree_changed: bool,
    force_llm_regen: bool = False,
) -> None:
    """Fail when LLM mode produced no screen body after a refresh was requested."""
    requires_llm_output = tree_changed or force_llm_regen
    if (
        not llm_result.generation
        and requires_llm_output
        and not llm_result.skipped_incremental
    ):
        raise LlmError("Generation failed: no LLM output available")
