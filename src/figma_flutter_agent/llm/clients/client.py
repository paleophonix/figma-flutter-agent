"""BaseLlmClient ABC — shared prompt assembly and response validation."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from functools import partial
from pathlib import Path
from typing import Any

from loguru import logger

from figma_flutter_agent.errors import LlmError, format_error_for_log
from figma_flutter_agent.llm.capabilities import (
    LlmProvider,
    log_structured_output_fallback,
)
from figma_flutter_agent.llm.clients.protocol import _provider_api_label
from figma_flutter_agent.llm.clients.response import ResponseMixin
from figma_flutter_agent.llm.clients.retry import RetryMixin
from figma_flutter_agent.llm.cpi_supervisor import (
    build_cpi_supervisor_context,
    build_cpi_supervisor_user_payload,
)
from figma_flutter_agent.llm.payload_format import format_labeled_user_payload
from figma_flutter_agent.llm.payload_slim import dump_clean_tree_for_llm, dump_tokens_for_llm
from figma_flutter_agent.llm.prompts import (
    REFERENCE_USER_PREAMBLE,
    VISUAL_REFINE_USER_PREAMBLE,
    build_repair_system_prompt,
    build_system_prompt,
    build_visual_refine_system_prompt,
    render_cpi_supervisor_prompt,
)
from figma_flutter_agent.llm.reasoning import (
    DEFAULT_LLM_MAX_OUTPUT_TOKENS,
    LlmReasoningSettings,
    resolve_max_output_tokens,
    should_fallback_without_reasoning,
)
from figma_flutter_agent.llm.refine_context import (
    RefineAttemptSummary,
    RefineFocus,
    build_canvas_size,
    build_foreground_layout_anchors,
)
from figma_flutter_agent.llm.repair import (
    build_repair_user_payload,
    build_visual_refine_user_payload,
)
from figma_flutter_agent.llm.repair_apply import apply_repair_patches
from figma_flutter_agent.llm.repair_scope import build_repair_scope
from figma_flutter_agent.llm.schema import (
    StructuredOutputSpec,
    cpi_supervisor_output_spec,
    repair_patch_output_spec,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    DesignTokens,
    FlutterGenerationResponse,
    NodeType,
    RepairCpiSupervisorResponse,
)
from figma_flutter_agent.validation.pixel.models import DiffBandRegion

_LLM_DEFAULT_MAX_RETRIES = 3
_LLM_HTTP_TIMEOUT_SEC = 180.0
_LLM_HTTP_CONNECT_TIMEOUT_SEC = 30.0

__all__ = [
    "BaseLlmClient",
    "_LLM_DEFAULT_MAX_RETRIES",
    "_LLM_HTTP_TIMEOUT_SEC",
    "_LLM_HTTP_CONNECT_TIMEOUT_SEC",
]


class BaseLlmClient(RetryMixin, ResponseMixin, ABC):
    """Shared prompt assembly and response validation for LLM providers."""

    def __init__(
        self,
        model: str,
        *,
        provider: LlmProvider,
        strict_json_schema: bool,
        temperature: float | None = None,
        top_p: float | None = None,
        reasoning: LlmReasoningSettings | None = None,
        max_retries: int = _LLM_DEFAULT_MAX_RETRIES,
        max_output_tokens: int = DEFAULT_LLM_MAX_OUTPUT_TOKENS,
    ) -> None:
        self._model = model
        self._provider = provider
        self._strict_json_schema = strict_json_schema
        self._temperature = temperature
        self._top_p = top_p
        self._reasoning_settings = reasoning or LlmReasoningSettings()
        self._reasoning_suppressed = False
        self._max_retries = max_retries
        self._max_output_tokens_base = max_output_tokens
        self._max_output_tokens_override: int | None = None

    def _effective_max_output_tokens(self) -> int:
        return resolve_max_output_tokens(
            base=self._max_output_tokens_base,
            reasoning=self._reasoning_settings,
            include_reasoning=self._include_reasoning(),
            override=self._max_output_tokens_override,
        )

    def _include_reasoning(self) -> bool:
        """Return True when reasoning kwargs should be attached to the next request."""
        return not self._reasoning_suppressed and self._reasoning_settings.is_active()

    def _suppress_reasoning_after_rejection(self, exc: LlmError) -> None:
        """Disable reasoning for the rest of this client session after provider rejection."""
        logger.warning(
            "LLM reasoning parameters rejected by {}; "
            "falling back to provider defaults for this session: {}",
            _provider_api_label(self._provider),
            format_error_for_log(exc),
        )
        self._reasoning_suppressed = True

    def _should_retry_without_reasoning(self, exc: LlmError) -> bool:
        """Return True when a failed request should be retried without reasoning kwargs."""
        return self._include_reasoning() and should_fallback_without_reasoning(
            status_code=exc.status_code,
            message=str(exc),
        )

    def _openai_llm_error(self, exc: Exception) -> LlmError:
        """Wrap OpenAI-compatible SDK errors as ``LlmError``."""
        status_code = getattr(exc, "status_code", None)
        return LlmError(
            f"{_provider_api_label(self._provider)} API error (model={self._model}): {exc}",
            status_code=status_code,
        )

    def _sampling_kwargs(self) -> dict[str, float]:
        """Return provider sampling overrides configured for this client."""
        kwargs: dict[str, float] = {}
        if self._temperature is not None:
            kwargs["temperature"] = self._temperature
        if self._top_p is not None:
            kwargs["top_p"] = self._top_p
        return kwargs

    def _warn_non_strict_structured_output(self) -> None:
        if not self._strict_json_schema:
            log_structured_output_fallback(provider=self._provider, model=self._model)

    def _resolved_analytics_span_name(self, override: str | None) -> str | None:
        if override is not None:
            return override
        from figma_flutter_agent.observability.llm_trace import current_llm_trace_context

        trace = current_llm_trace_context()
        if trace is None:
            return None
        return trace.span_name

    def _emit_llm_analytics(
        self,
        *,
        latency_sec: float,
        system_prompt: str,
        user_prompt: str,
        output_text: str | None,
        is_error: bool,
        error_message: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_cost_usd: float | None = None,
        input_cost_usd: float | None = None,
        output_cost_usd: float | None = None,
        analytics_span_name: str | None = None,
    ) -> None:
        from figma_flutter_agent.observability.llm_trace import current_llm_trace_context
        from figma_flutter_agent.observability.posthog_llm import capture_ai_generation

        span_name = self._resolved_analytics_span_name(analytics_span_name)
        if span_name is None:
            return
        from figma_flutter_agent.observability.llm_trace import (
            repair_pipeline_posthog_from_recorder,
        )

        if span_name.startswith("repair.") and repair_pipeline_posthog_from_recorder():
            return
        trace = current_llm_trace_context()
        if trace is None:
            return
        capture_ai_generation(
            settings=trace.settings,
            trace_id=trace.run_id,
            span_name=span_name,
            provider=self._provider,
            model=self._model,
            latency_sec=latency_sec,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output_text=output_text,
            is_error=is_error,
            error_message=error_message,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_cost_usd=total_cost_usd,
            input_cost_usd=input_cost_usd,
            output_cost_usd=output_cost_usd,
            parent_span_id=trace.root_span_id,
        )
        from figma_flutter_agent.observability.prometheus_metrics import record_llm_request

        record_llm_request(span_name, latency_sec=latency_sec, is_error=is_error)

    def _generation_prompts(
        self,
        clean_tree: CleanDesignTreeNode,
        tokens: DesignTokens,
        *,
        feature_name: str,
        asset_manifest: list[dict[str, str]],
        widget_hints: list[str] | None,
        navigation_hints: list[str] | None,
        routing_enabled: bool,
        theme_variant: str,
        figma_reference_png: bytes | None,
        use_screen_ir: bool,
        project_dir: Path | None = None,
    ) -> tuple[str, str]:
        prompt = self._build_user_prompt(
            clean_tree,
            tokens,
            feature_name=feature_name,
            asset_manifest=asset_manifest,
            widget_hints=widget_hints,
            navigation_hints=navigation_hints,
            use_screen_ir=use_screen_ir,
            project_dir=project_dir,
        )
        system_prompt = build_system_prompt(
            routing_enabled=routing_enabled,
            theme_variant=theme_variant,
            figma_reference_attached=figma_reference_png is not None,
            stack_root=clean_tree.type == NodeType.STACK,
            use_screen_ir=use_screen_ir,
        )
        logger.bind(feature_name=feature_name, stage="llm_generate").info(
            "LLM generate prompt size user_chars={} system_chars={} figma_png_bytes={} est_input_tokens={}",
            len(prompt),
            len(system_prompt),
            len(figma_reference_png) if figma_reference_png is not None else 0,
            (len(prompt) + len(system_prompt) + (len(figma_reference_png) * 4 // 3 if figma_reference_png else 0))
            // 4,
        )
        return prompt, system_prompt

    def _execute_cpi_supervisor(
        self,
        *,
        feature_name: str,
        analyze_errors: list[str],
        clean_tree: CleanDesignTreeNode,
        failed_attempts_history: list[str],
    ) -> RepairCpiSupervisorResponse:
        context = build_cpi_supervisor_context(
            failed_attempts_history=failed_attempts_history,
            analyze_errors=analyze_errors,
            clean_tree=clean_tree,
        )
        system_prompt = render_cpi_supervisor_prompt(context)
        prompt = build_cpi_supervisor_user_payload(feature_name=feature_name)
        output_spec = cpi_supervisor_output_spec(strict=self._strict_json_schema)
        raw_text = self._request_generation(
            prompt,
            system_prompt=system_prompt,
            figma_reference_png=None,
            output_spec=output_spec,
            analytics_span_name="repair_cpi_supervisor",
        )
        response = self._parse_cpi_supervisor_response(raw_text)
        logger.bind(model=self._model, provider=self._provider).info(
            "CPI supervisor pattern interrupt ({} chars)",
            len(response.pattern_interrupt_directive),
        )
        return response

    async def cpi_supervisor_async(
        self,
        clean_tree: CleanDesignTreeNode,
        *,
        feature_name: str,
        analyze_errors: list[str],
        failed_attempts_history: list[str],
    ) -> RepairCpiSupervisorResponse:
        """Run the metacognitive CPI supervisor when repair stagnates."""

        async def _attempt() -> RepairCpiSupervisorResponse:
            return await asyncio.to_thread(
                self._execute_cpi_supervisor,
                feature_name=feature_name,
                analyze_errors=analyze_errors,
                clean_tree=clean_tree,
                failed_attempts_history=failed_attempts_history,
            )

        return await self._run_with_retry_async(_attempt)

    def _repair_prompts(
        self,
        *,
        feature_name: str,
        scope,
        analyze_errors: list[str],
        planned_files: dict[str, str] | None,
        clean_tree,
        failed_attempts_history: list[str] | None,
        cpi_supervisor_directive: str | None = None,
        repair_system_prompt: str | None = None,
        escalation_level: int = 1,
        current_generation: FlutterGenerationResponse | None = None,
        geometry_feedback: str | None = None,
        use_screen_ir: bool = False,
    ) -> tuple[str, str]:
        from figma_flutter_agent.llm.repair_scope import (
            build_repair_environment_context,
            dedupe_analyze_errors,
        )

        unique_errors = dedupe_analyze_errors(analyze_errors)
        prompt = build_repair_user_payload(
            feature_name=feature_name,
            scope=scope,
            analyze_errors=unique_errors,
            escalation_level=escalation_level,
            current_generation=current_generation,
            geometry_feedback=geometry_feedback,
            use_screen_ir=use_screen_ir,
        )
        env_context = build_repair_environment_context(
            scope=scope,
            planned_files=planned_files or {},
            analyze_errors=unique_errors,
            clean_tree=clean_tree,
            failed_attempts_history=failed_attempts_history,
            cpi_supervisor_directive=cpi_supervisor_directive,
            escalation_level=escalation_level,
        )
        if repair_system_prompt is not None:
            system_prompt = repair_system_prompt
        else:
            system_prompt = build_repair_system_prompt(
                env_context,
                use_screen_ir=use_screen_ir,
            )
        return prompt, system_prompt

    def _resolve_repair_scope(
        self,
        *,
        feature_name: str,
        planned_files: dict[str, str] | None,
        current_generation: FlutterGenerationResponse,
        analyze_errors: list[str],
        architecture: str,
        escalation_level: int = 1,
        use_screen_ir: bool = False,
    ):
        if planned_files:
            return build_repair_scope(
                feature_name=feature_name,
                planned_files=planned_files,
                current_generation=current_generation,
                analyze_errors=analyze_errors,
                architecture=architecture,
                escalation_level=escalation_level,
                use_screen_ir=use_screen_ir,
            )
        from figma_flutter_agent.llm.repair_scope import RepairScope, RepairTarget

        return RepairScope(
            targets=(
                RepairTarget(
                    target="screenCode",
                    widget_name=None,
                    code=current_generation.screen_code,
                    planned_path="",
                    errors=tuple(analyze_errors),
                    planned_excerpt="",
                ),
            )
        )

    def _execute_repair(
        self,
        *,
        feature_name: str,
        current_generation: FlutterGenerationResponse,
        analyze_errors: list[str],
        planned_files: dict[str, str] | None,
        architecture: str,
        figma_reference_png: bytes | None,
        clean_tree,
        failed_attempts_history: list[str] | None,
        cpi_supervisor_directive: str | None = None,
        repair_system_prompt: str | None = None,
        escalation_level: int = 1,
        geometry_feedback: str | None = None,
        use_screen_ir: bool = False,
        require_screen_ir: bool = False,
        project_dir: Path | None = None,
        tokens: DesignTokens | None = None,
    ) -> FlutterGenerationResponse:
        scope = self._resolve_repair_scope(
            feature_name=feature_name,
            planned_files=planned_files,
            current_generation=current_generation,
            analyze_errors=analyze_errors,
            architecture=architecture,
            escalation_level=escalation_level,
            use_screen_ir=use_screen_ir,
        )
        target_summary = ", ".join(
            f"{target.target}"
            + (f"({target.widget_name})" if target.widget_name else "")
            + f"@{target.planned_path}"
            for target in scope.targets
        )
        logger.bind(model=self._model, provider=self._provider).info(
            "LLM repair scope: {} target(s): {}",
            len(scope.targets),
            target_summary or "(none)",
        )
        prompt, system_prompt = self._repair_prompts(
            feature_name=feature_name,
            scope=scope,
            analyze_errors=analyze_errors,
            planned_files=planned_files,
            clean_tree=clean_tree,
            failed_attempts_history=failed_attempts_history,
            cpi_supervisor_directive=cpi_supervisor_directive,
            repair_system_prompt=repair_system_prompt,
            escalation_level=escalation_level,
            current_generation=current_generation,
            geometry_feedback=geometry_feedback,
            use_screen_ir=use_screen_ir,
        )
        output_spec = repair_patch_output_spec(strict=self._strict_json_schema)
        raw_text = self._request_generation(
            prompt,
            system_prompt=system_prompt,
            figma_reference_png=figma_reference_png,
            output_spec=output_spec,
            analytics_span_name="repair",
        )
        patch_response = self._parse_repair_patch_response(raw_text)
        target_planned_paths = {
            (target.target, target.widget_name): target.planned_path.replace("\\", "/")
            for target in scope.targets
        }
        normalized_sources = (
            {key.replace("\\", "/"): value for key, value in planned_files.items()}
            if planned_files
            else None
        )
        apply_outcome = apply_repair_patches(
            current_generation,
            patch_response,
            escalation_level=escalation_level,
            base_sources=normalized_sources,
            target_planned_paths=target_planned_paths,
            clean_tree=clean_tree if use_screen_ir else None,
            project_dir=project_dir,
            tokens=tokens,
            use_screen_ir=use_screen_ir,
            require_screen_ir=require_screen_ir,
        )
        if apply_outcome.ir_patches_applied:
            logger.info(
                "LLM repair: applied {} irPatch(es), rejected {}",
                apply_outcome.ir_patches_applied,
                apply_outcome.patches_rejected,
            )
        elif apply_outcome.patches_rejected and not apply_outcome.patches_applied:
            logger.warning(
                "LLM repair: all {} patch(es) rejected (diff did not apply or invalid format)",
                apply_outcome.patches_rejected,
            )
        return apply_outcome.generation

    def repair(
        self,
        clean_tree: CleanDesignTreeNode,
        tokens: DesignTokens,
        *,
        feature_name: str,
        asset_manifest: list[dict[str, str]],
        current_generation: FlutterGenerationResponse,
        analyze_errors: list[str],
        widget_hints: list[str] | None = None,
        navigation_hints: list[str] | None = None,
        routing_enabled: bool = False,
        theme_variant: str = "material_3",
        figma_reference_png: bytes | None = None,
        planned_files: dict[str, str] | None = None,
        architecture: str = "feature_first",
        failed_attempts_history: list[str] | None = None,
        cpi_supervisor_directive: str | None = None,
        repair_system_prompt: str | None = None,
        escalation_level: int = 1,
        geometry_feedback: str | None = None,
        use_screen_ir: bool = False,
        require_screen_ir: bool = False,
        project_dir: Path | None = None,
    ) -> FlutterGenerationResponse:
        del (
            asset_manifest,
            widget_hints,
            navigation_hints,
            routing_enabled,
            theme_variant,
        )
        self._warn_non_strict_structured_output()

        def _attempt() -> FlutterGenerationResponse:
            return self._execute_repair(
                feature_name=feature_name,
                current_generation=current_generation,
                analyze_errors=analyze_errors,
                planned_files=planned_files,
                architecture=architecture,
                figma_reference_png=figma_reference_png,
                clean_tree=clean_tree,
                failed_attempts_history=failed_attempts_history,
                cpi_supervisor_directive=cpi_supervisor_directive,
                repair_system_prompt=repair_system_prompt,
                escalation_level=escalation_level,
                geometry_feedback=geometry_feedback,
                use_screen_ir=use_screen_ir,
                require_screen_ir=require_screen_ir,
                project_dir=project_dir,
                tokens=tokens,
            )

        return self._run_with_retry(_attempt)

    async def repair_async(
        self,
        clean_tree: CleanDesignTreeNode,
        tokens: DesignTokens,
        *,
        feature_name: str,
        asset_manifest: list[dict[str, str]],
        current_generation: FlutterGenerationResponse,
        analyze_errors: list[str],
        widget_hints: list[str] | None = None,
        navigation_hints: list[str] | None = None,
        routing_enabled: bool = False,
        theme_variant: str = "material_3",
        figma_reference_png: bytes | None = None,
        planned_files: dict[str, str] | None = None,
        architecture: str = "feature_first",
        failed_attempts_history: list[str] | None = None,
        cpi_supervisor_directive: str | None = None,
        repair_system_prompt: str | None = None,
        escalation_level: int = 1,
        geometry_feedback: str | None = None,
        use_screen_ir: bool = False,
        require_screen_ir: bool = False,
        project_dir: Path | None = None,
    ) -> FlutterGenerationResponse:
        del (
            asset_manifest,
            widget_hints,
            navigation_hints,
            routing_enabled,
            theme_variant,
        )
        self._warn_non_strict_structured_output()

        async def _attempt() -> FlutterGenerationResponse:
            return await asyncio.to_thread(
                self._execute_repair,
                feature_name=feature_name,
                current_generation=current_generation,
                analyze_errors=analyze_errors,
                planned_files=planned_files,
                architecture=architecture,
                figma_reference_png=figma_reference_png,
                clean_tree=clean_tree,
                failed_attempts_history=failed_attempts_history,
                cpi_supervisor_directive=cpi_supervisor_directive,
                repair_system_prompt=repair_system_prompt,
                escalation_level=escalation_level,
                geometry_feedback=geometry_feedback,
                use_screen_ir=use_screen_ir,
                require_screen_ir=require_screen_ir,
                project_dir=project_dir,
                tokens=tokens,
            )

        return await self._run_with_retry_async(_attempt)

    def generate(
        self,
        clean_tree: CleanDesignTreeNode,
        tokens: DesignTokens,
        *,
        feature_name: str,
        asset_manifest: list[dict[str, str]],
        widget_hints: list[str] | None = None,
        navigation_hints: list[str] | None = None,
        routing_enabled: bool = False,
        theme_variant: str = "material_3",
        figma_reference_png: bytes | None = None,
        use_screen_ir: bool = False,
        require_screen_ir: bool = False,
        project_dir: Path | None = None,
        persist_ir_snapshots: bool = True,
    ) -> FlutterGenerationResponse:
        self._warn_non_strict_structured_output()
        prompt, system_prompt = self._generation_prompts(
            clean_tree,
            tokens,
            feature_name=feature_name,
            asset_manifest=asset_manifest,
            widget_hints=widget_hints,
            navigation_hints=navigation_hints,
            routing_enabled=routing_enabled,
            theme_variant=theme_variant,
            figma_reference_png=figma_reference_png,
            use_screen_ir=use_screen_ir,
            project_dir=project_dir,
        )

        def _attempt() -> FlutterGenerationResponse:
            raw_text = self._request_generation(
                prompt,
                system_prompt=system_prompt,
                figma_reference_png=figma_reference_png,
                analytics_span_name="generate",
            )
            return self._finalize_generation_response(
                self._parse_generation_response(raw_text),
                clean_tree=clean_tree,
                use_screen_ir=use_screen_ir,
                require_screen_ir=require_screen_ir,
                project_dir=project_dir,
                tokens=tokens,
                feature_name=feature_name,
                persist_ir_snapshots=persist_ir_snapshots,
            )

        return self._run_with_retry(_attempt)

    async def generate_async(
        self,
        clean_tree: CleanDesignTreeNode,
        tokens: DesignTokens,
        *,
        feature_name: str,
        asset_manifest: list[dict[str, str]],
        widget_hints: list[str] | None = None,
        navigation_hints: list[str] | None = None,
        routing_enabled: bool = False,
        theme_variant: str = "material_3",
        figma_reference_png: bytes | None = None,
        use_screen_ir: bool = False,
        require_screen_ir: bool = False,
        project_dir: Path | None = None,
        persist_ir_snapshots: bool = True,
    ) -> FlutterGenerationResponse:
        self._warn_non_strict_structured_output()
        prompt, system_prompt = self._generation_prompts(
            clean_tree,
            tokens,
            feature_name=feature_name,
            asset_manifest=asset_manifest,
            widget_hints=widget_hints,
            navigation_hints=navigation_hints,
            routing_enabled=routing_enabled,
            theme_variant=theme_variant,
            figma_reference_png=figma_reference_png,
            use_screen_ir=use_screen_ir,
            project_dir=project_dir,
        )

        async def _attempt() -> FlutterGenerationResponse:
            raw_text = await asyncio.to_thread(
                partial(
                    self._request_generation,
                    prompt,
                    system_prompt=system_prompt,
                    figma_reference_png=figma_reference_png,
                    analytics_span_name="generate",
                ),
            )
            return self._finalize_generation_response(
                self._parse_generation_response(raw_text),
                clean_tree=clean_tree,
                use_screen_ir=use_screen_ir,
                require_screen_ir=require_screen_ir,
                project_dir=project_dir,
                tokens=tokens,
                feature_name=feature_name,
                persist_ir_snapshots=persist_ir_snapshots,
            )

        return await self._run_with_retry_async(_attempt)

    def _visual_refine_prompts(
        self,
        clean_tree: CleanDesignTreeNode,
        tokens: DesignTokens,
        *,
        feature_name: str,
        asset_manifest: list[dict[str, str]],
        current_generation: FlutterGenerationResponse,
        changed_ratio: float,
        threshold: float,
        widget_hints: list[str] | None,
        navigation_hints: list[str] | None,
        routing_enabled: bool,
        theme_variant: str,
        refine_attempt: int,
        max_refine_attempts: int,
        previous_changed_ratio: float | None,
        refine_focus: RefineFocus,
        diff_bands: tuple[DiffBandRegion, ...],
        refine_history: tuple[RefineAttemptSummary, ...],
        interactive_inventory: list[dict[str, Any]] | None,
        handler_audit: dict[str, Any] | None,
        canvas_size: dict[str, float | int] | None,
        asset_warnings: list[str] | None,
        surgical_widget_snippets: dict[str, str] | None = None,
        geometry_feedback: str | None = None,
        use_screen_ir: bool = False,
    ) -> tuple[str, str]:
        prompt = build_visual_refine_user_payload(
            feature_name=feature_name,
            clean_tree=clean_tree,
            tokens=tokens,
            asset_manifest=asset_manifest,
            current_generation=current_generation,
            changed_ratio=changed_ratio,
            threshold=threshold,
            widget_hints=widget_hints,
            navigation_hints=navigation_hints,
            refine_attempt=refine_attempt,
            max_refine_attempts=max_refine_attempts,
            previous_changed_ratio=previous_changed_ratio,
            refine_focus=refine_focus,
            diff_bands=diff_bands,
            refine_history=refine_history,
            interactive_inventory=interactive_inventory,
            handler_audit=handler_audit,
            canvas_size=canvas_size,
            asset_warnings=asset_warnings,
            surgical_widget_snippets=surgical_widget_snippets,
            geometry_feedback=geometry_feedback,
            use_screen_ir=use_screen_ir,
        )
        system_prompt = build_visual_refine_system_prompt(
            routing_enabled=routing_enabled,
            theme_variant=theme_variant,
            stack_root=clean_tree.type == NodeType.STACK,
            surgical_widgets=bool(surgical_widget_snippets),
            use_screen_ir=use_screen_ir,
        )
        return prompt, system_prompt

    async def visual_refine_async(
        self,
        clean_tree: CleanDesignTreeNode,
        tokens: DesignTokens,
        *,
        feature_name: str,
        asset_manifest: list[dict[str, str]],
        current_generation: FlutterGenerationResponse,
        changed_ratio: float,
        threshold: float,
        widget_hints: list[str] | None = None,
        navigation_hints: list[str] | None = None,
        routing_enabled: bool = False,
        theme_variant: str = "material_3",
        figma_reference_png: bytes | None = None,
        flutter_render_png: bytes | None = None,
        visual_diff_png: bytes | None = None,
        refine_attempt: int = 1,
        max_refine_attempts: int = 1,
        previous_changed_ratio: float | None = None,
        refine_focus: RefineFocus = "interaction",
        diff_bands: tuple[DiffBandRegion, ...] = (),
        refine_history: tuple[RefineAttemptSummary, ...] = (),
        interactive_inventory: list[dict[str, Any]] | None = None,
        handler_audit: dict[str, Any] | None = None,
        canvas_size: dict[str, float | int] | None = None,
        asset_warnings: list[str] | None = None,
        surgical_widget_snippets: dict[str, str] | None = None,
        geometry_feedback: str | None = None,
        use_screen_ir: bool = False,
        require_screen_ir: bool = False,
        project_dir: Path | None = None,
    ) -> FlutterGenerationResponse:
        self._warn_non_strict_structured_output()
        prompt, system_prompt = self._visual_refine_prompts(
            clean_tree,
            tokens,
            feature_name=feature_name,
            asset_manifest=asset_manifest,
            current_generation=current_generation,
            changed_ratio=changed_ratio,
            threshold=threshold,
            widget_hints=widget_hints,
            navigation_hints=navigation_hints,
            routing_enabled=routing_enabled,
            theme_variant=theme_variant,
            refine_attempt=refine_attempt,
            max_refine_attempts=max_refine_attempts,
            previous_changed_ratio=previous_changed_ratio,
            refine_focus=refine_focus,
            diff_bands=diff_bands,
            refine_history=refine_history,
            interactive_inventory=interactive_inventory,
            handler_audit=handler_audit,
            canvas_size=canvas_size,
            asset_warnings=asset_warnings,
            surgical_widget_snippets=surgical_widget_snippets,
            geometry_feedback=geometry_feedback,
            use_screen_ir=use_screen_ir,
        )

        async def _attempt() -> FlutterGenerationResponse:
            raw_text = await asyncio.to_thread(
                partial(
                    self._request_generation,
                    prompt,
                    system_prompt=system_prompt,
                    figma_reference_png=figma_reference_png,
                    flutter_render_png=flutter_render_png,
                    visual_diff_png=visual_diff_png,
                    user_preamble=VISUAL_REFINE_USER_PREAMBLE,
                    analytics_span_name="refine",
                ),
            )
            return self._finalize_generation_response(
                self._parse_generation_response(raw_text),
                clean_tree=clean_tree,
                use_screen_ir=use_screen_ir,
                require_screen_ir=require_screen_ir,
                project_dir=project_dir,
                tokens=tokens,
                feature_name=feature_name,
            )

        return await self._run_with_retry_async(_attempt)

    def _build_user_prompt(
        self,
        clean_tree: CleanDesignTreeNode,
        tokens: DesignTokens,
        *,
        feature_name: str,
        asset_manifest: list[dict[str, str]],
        widget_hints: list[str] | None = None,
        navigation_hints: list[str] | None = None,
        use_screen_ir: bool = False,
        project_dir: Path | None = None,
    ) -> str:
        from figma_flutter_agent.generator.ir.tree import index_clean_tree
        from figma_flutter_agent.llm.ir_payload import (
            dump_screen_ir_blueprint_for_llm,
            dump_widget_ir_blueprint,
        )
        from figma_flutter_agent.llm.semantic_context import assemble_semantic_context

        user_payload: dict[str, Any] = {
            "featureName": feature_name,
            "cleanTree": dump_clean_tree_for_llm(clean_tree),
            "tokens": dump_tokens_for_llm(tokens),
            "assetManifest": asset_manifest,
        }
        if use_screen_ir:
            screen_ir_blueprint = dump_screen_ir_blueprint_for_llm(clean_tree)
            user_payload["screenIrBlueprint"] = screen_ir_blueprint
            semantic_packet = assemble_semantic_context(
                clean_tree,
                screen_ir_blueprint=screen_ir_blueprint,
            )
            for key, value in semantic_packet.model_dump_for_llm().items():
                user_payload[key] = value
            if project_dir is not None:
                from figma_flutter_agent.debug.ir_dumps import write_ir_debug_json

                write_ir_debug_json(
                    stage="semantic_context",
                    feature_name=feature_name,
                    payload=semantic_packet.model_dump_for_debug(),
                    project_dir=project_dir,
                )
                write_ir_debug_json(
                    stage="semantic_context_llm",
                    feature_name=feature_name,
                    payload=semantic_packet.model_dump_for_llm(),
                    project_dir=project_dir,
                )
            from figma_flutter_agent.parser.interaction import collect_interaction_signals

            interaction_signals = collect_interaction_signals(clean_tree)
            if interaction_signals:
                user_payload["interactionSignals"] = interaction_signals
            if widget_hints:
                indexed = index_clean_tree(clean_tree)
                blueprints: dict[str, Any] = {}
                for hint in widget_hints:
                    node_id = self._figma_id_from_widget_hint(hint)
                    if node_id and node_id in indexed:
                        blueprints[hint] = dump_widget_ir_blueprint(indexed[node_id])
                if blueprints:
                    user_payload["extractedWidgetBlueprints"] = blueprints
        if widget_hints:
            user_payload["widgetExtractionHints"] = widget_hints
        if navigation_hints:
            user_payload["navigationHints"] = navigation_hints
        if clean_tree.type == NodeType.STACK:
            user_payload["canvasSize"] = build_canvas_size(clean_tree)
            layout_anchors = build_foreground_layout_anchors(clean_tree)
            if layout_anchors:
                user_payload["layoutAnchors"] = layout_anchors
        output_schema = (
            "FlutterGenerationResponse JSON (screenIr, extractedWidgets with widgetIr)"
            if use_screen_ir
            else "FlutterGenerationResponse JSON (screenCode, extractedWidgets)"
        )
        return format_labeled_user_payload(
            mode="generate",
            output_schema=output_schema,
            sections=user_payload,
        )

    @staticmethod
    def _figma_id_from_widget_hint(hint: str) -> str | None:
        import re

        match = re.search(r"\bnode\s+([\w:\-]+)", hint, flags=re.IGNORECASE)
        return match.group(1) if match else None

    @abstractmethod
    def _request_generation(
        self,
        prompt: str,
        *,
        system_prompt: str,
        figma_reference_png: bytes | None = None,
        flutter_render_png: bytes | None = None,
        visual_diff_png: bytes | None = None,
        user_preamble: str = REFERENCE_USER_PREAMBLE,
        output_spec: StructuredOutputSpec | None = None,
        analytics_span_name: str | None = None,
    ) -> str:
        """Call provider SDK and return raw JSON text."""
