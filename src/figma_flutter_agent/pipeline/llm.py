"""LLM stage orchestration with deterministic fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from figma_flutter_agent.config import Settings
from figma_flutter_agent.errors import LlmError, format_error_for_log
from figma_flutter_agent.generator.paths import Architecture, screen_file_path
from figma_flutter_agent.generator.renderer import to_pascal_case
from figma_flutter_agent.parser.prototype import PrototypeNavigationPlan
from figma_flutter_agent.pipeline.deps import LlmClientFactory
from figma_flutter_agent.schemas import AssetManifest, CleanDesignTreeNode, DesignTokens
from figma_flutter_agent.stages import LlmStageRequest, LlmStageResult, run_llm_stage


@dataclass(frozen=True)
class LlmPipelineOutcome:
    """LLM stage output and effective settings for planning."""

    plan_settings: Settings
    llm_result: LlmStageResult
    llm_fallback_applied: bool
    fallback_warnings: tuple[str, ...] = ()

    @property
    def use_deterministic_screen(self) -> bool:
        return self.plan_settings.agent.generation.use_deterministic_screen


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
) -> LlmPipelineOutcome:
    """Run the LLM stage and apply deterministic fallback when configured.

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
    try:
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
            ),
        )
    except LlmError as exc:
        if (
            settings.agent.generation.llm_fallback_to_deterministic
            and not settings.agent.generation.use_deterministic_screen
        ):
            log.warning(
                "LLM generation failed; falling back to deterministic layout: {}",
                format_error_for_log(exc),
            )
            return LlmPipelineOutcome(
                plan_settings=settings.with_deterministic_screen(use_deterministic_screen=True),
                llm_result=LlmStageResult(),
                llm_fallback_applied=True,
                fallback_warnings=(
                    "LLM generation failed; using deterministic layout fallback. "
                    "Set generation.llm_fallback_to_deterministic: false to fail fast.",
                ),
            )
        raise

    plan_settings = settings
    llm_fallback_applied = False
    fallback_warnings: list[str] = []
    requires_llm_output = incremental.tree_changed or force_llm_regen
    if (
        llm_result.llm_attempted
        and not llm_result.generation
        and requires_llm_output
        and not settings.agent.generation.use_deterministic_screen
        and not llm_result.skipped_incremental
        and settings.agent.generation.llm_fallback_to_deterministic
    ):
        log.warning("LLM returned no screen output; falling back to deterministic layout")
        plan_settings = settings.with_deterministic_screen(use_deterministic_screen=True)
        llm_fallback_applied = True
        fallback_warnings.append(
            "LLM returned no screen output; using deterministic layout fallback. "
            "Set generation.llm_fallback_to_deterministic: false to fail fast."
        )

    return LlmPipelineOutcome(
        plan_settings=plan_settings,
        llm_result=llm_result,
        llm_fallback_applied=llm_fallback_applied,
        fallback_warnings=tuple(fallback_warnings),
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
    use_deterministic_screen: bool,
    architecture: Architecture = "feature_first",
) -> None:
    """Warn when LLM mode still plans a screen that only wraps the layout file."""
    if use_deterministic_screen:
        return
    screen_path = screen_file_path(feature_name, architecture=architecture)
    source = planned_files.get(screen_path, "")
    layout_class = f"{to_pascal_case(feature_name)}Layout"
    if layout_class in source and f"{layout_class}()" in source:
        warnings.append(
            "LLM mode produced a screen that delegates to "
            f"{layout_class} (same pattern as deterministic output). "
            "Check pipeline logs for deterministic fallback or LLM errors."
        )


def ensure_llm_output_or_raise(
    *,
    llm_result: LlmStageResult,
    tree_changed: bool,
    use_deterministic_screen: bool,
    llm_fallback_applied: bool,
    force_llm_regen: bool = False,
) -> None:
    """Fail when LLM mode produced no screen body after a refresh was requested."""
    requires_llm_output = tree_changed or force_llm_regen
    if (
        not llm_result.generation
        and requires_llm_output
        and not use_deterministic_screen
        and not llm_result.skipped_incremental
        and not llm_fallback_applied
    ):
        raise LlmError("Generation failed: no LLM output available")
