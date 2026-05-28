"""LLM generation stage for the generation pipeline."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from loguru import logger

from figma_flutter_agent.config import Settings
from figma_flutter_agent.errors import LlmError
from figma_flutter_agent.generator.destinations import generate_destination_screens
from figma_flutter_agent.llm.client import LlmClient
from figma_flutter_agent.observability.llm_trace import set_llm_stage
from figma_flutter_agent.parser.prototype import PrototypeNavigationPlan
from figma_flutter_agent.schemas import (
    AssetManifest,
    CleanDesignTreeNode,
    DesignTokens,
    FlutterGenerationResponse,
)


@dataclass
class LlmStageRequest:
    """Inputs required to run primary and destination LLM generation."""

    settings: Settings
    dry_run: bool
    resolved_sync: bool
    tree_changed: bool
    tokens_changed: bool
    previous_snapshot_exists: bool
    clean_tree: CleanDesignTreeNode
    tokens: DesignTokens
    resolved_feature: str
    asset_manifest: AssetManifest
    widget_hints: list[str]
    navigation_hints: list[str]
    routing_on: bool
    navigation_plan: PrototypeNavigationPlan
    frame_index: dict[str, dict[str, object]]
    published_styles: dict[str, dict[str, object]]
    components: dict[str, dict[str, object]]
    component_sets: dict[str, dict[str, object]]
    destination_trees: dict[str, CleanDesignTreeNode]
    destination_widget_hints: dict[str, list[str]]
    style_paint_index: dict[str, dict[str, object]]
    force_llm_regen: bool = False
    llm_client_factory: Callable[[Settings], LlmClient] | None = None
    figma_reference_png: bytes | None = None


@dataclass
class LlmStageResult:
    """Output of the LLM generation stage."""

    generation: FlutterGenerationResponse | None = None
    destination_generations: dict[str, FlutterGenerationResponse] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    skipped_incremental: bool = False
    llm_attempted: bool = False


def _needs_llm(request: LlmStageRequest) -> bool:
    if request.dry_run:
        return False
    if not request.resolved_sync or not request.previous_snapshot_exists:
        return True
    if request.tree_changed or request.force_llm_regen:
        return True
    return request.tokens_changed and request.settings.agent.generation.regen_llm_on_token_change


async def run_llm_stage(request: LlmStageRequest) -> LlmStageResult:
    """Generate primary and destination screen output via the configured LLM.

    Args:
        request: Parsed design data and runtime settings for LLM calls.

    Returns:
        Primary generation, optional destination generations, and non-fatal warnings.

    Raises:
        LlmError: When LLM generation fails outside dry-run mode.
    """
    result = LlmStageResult()
    log = logger.bind(stage="llm", feature_name=request.resolved_feature)
    if request.dry_run:
        return result

    if request.settings.agent.generation.use_deterministic_screen:
        return result

    skip_due_to_unchanged_tree = (
        request.resolved_sync
        and request.previous_snapshot_exists
        and not request.tree_changed
        and not request.force_llm_regen
    )
    if skip_due_to_unchanged_tree:
        if request.tokens_changed and request.settings.agent.generation.regen_llm_on_token_change:
            log.info(
                "Incremental sync: design tokens changed; regenerating LLM screen "
                "(generation.regen_llm_on_token_change=true)."
            )
        else:
            if request.tokens_changed:
                log.warning(
                    "Incremental sync: design tree unchanged; skipping LLM and updating theme files only. "
                    "Enable generation.regen_llm_on_token_change or use --force-llm-regen."
                )
            else:
                log.warning(
                    "Incremental sync: LLM generation skipped because the design tree hash is unchanged. "
                    "Use --force-llm-regen to force regeneration."
                )
            result.skipped_incremental = True
            return result

    if not _needs_llm(request):
        return result

    llm_api_key = request.settings.llm_api_key()
    if not llm_api_key:
        if not request.settings.agent.generation.use_deterministic_screen:
            env_name = request.settings.llm_api_key_env_name()
            raise LlmError(
                "LLM API key is missing, but deterministic generation is disabled. "
                f"Set {env_name} (provider {request.settings.resolved_llm_provider()!r}) "
                "or enable generation.use_deterministic_screen."
            )
        return result

    result.llm_attempted = True
    set_llm_stage("generate")
    if request.llm_client_factory is not None:
        client_factory = request.llm_client_factory
    else:
        from figma_flutter_agent.pipeline.deps import default_pipeline_dependencies

        client_factory = default_pipeline_dependencies().create_llm_client
    llm_client = client_factory(request.settings)
    reasoning = request.settings.resolved_llm_reasoning()
    log.info(
        "Using LLM provider {} with model {} (temperature={}, repair_temperature={}, top_p={}, reasoning={})",
        request.settings.resolved_llm_provider(),
        request.settings.resolved_llm_generate_model(),
        request.settings.resolved_llm_generate_temperature(),
        request.settings.resolved_llm_repair_temperature(),
        request.settings.llm_top_p,
        reasoning.openrouter_payload() if reasoning.is_active() else None,
    )
    if request.figma_reference_png is not None:
        log.info(
            "Attached Figma reference PNG to LLM request ({} bytes)",
            len(request.figma_reference_png),
        )

    asset_entries = [entry.model_dump() for entry in request.asset_manifest.entries]
    try:
        result.generation = await llm_client.generate_async(
            request.clean_tree,
            request.tokens,
            feature_name=request.resolved_feature,
            asset_manifest=asset_entries,
            widget_hints=request.widget_hints,
            navigation_hints=request.navigation_hints,
            routing_enabled=request.routing_on,
            theme_variant=request.settings.agent.theme.variant,
            figma_reference_png=request.figma_reference_png,
        )
    except LlmError:
        if not request.dry_run:
            raise
        result.warnings.append("LLM generation failed; dry-run continues with empty screen output.")
        return result

    routing_cfg = request.settings.agent.routing
    if (
        result.generation is not None
        and request.routing_on
        and routing_cfg.generate_destinations
        and len(request.navigation_plan.routes) > 1
    ):
        destination_generations, destination_warnings = await generate_destination_screens(
            llm_client,
            routes=request.navigation_plan.routes,
            current_feature=request.resolved_feature,
            frame_index=request.frame_index,
            tokens=request.tokens,
            asset_manifest=asset_entries,
            navigation_hints=request.navigation_hints,
            published_styles=request.published_styles,
            components=request.components,
            component_sets=request.component_sets,
            routing_enabled=request.routing_on,
            theme_variant=request.settings.agent.theme.variant,
            destination_trees=request.destination_trees,
            destination_widget_hints=request.destination_widget_hints,
            style_paint_index=request.style_paint_index,
            allow_stubs=request.settings.agent.generation.allow_destination_stubs,
        )
        result.destination_generations = destination_generations
        result.warnings.extend(destination_warnings)

    return result
