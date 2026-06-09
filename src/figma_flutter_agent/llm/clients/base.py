"""BaseLlmClient ABC and image content builders."""

from __future__ import annotations

import asyncio
import base64
import json
import random
import time
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from functools import partial
from pathlib import Path
from typing import Any, TypeVar

from loguru import logger

from figma_flutter_agent.errors import LlmError, format_error_for_log
from figma_flutter_agent.llm.capabilities import (
    LlmProvider,
    log_structured_output_fallback,
)
from figma_flutter_agent.llm.prompts import (
    FIGMA_REFERENCE_INLINE_LABEL,
    FIGMA_REFERENCE_ONLY_LABEL,
    FLUTTER_RENDER_INLINE_LABEL,
    REFERENCE_USER_PREAMBLE,
    VISUAL_DIFF_INLINE_LABEL,
    VISUAL_REFINE_IMAGE_INTRO,
    VISUAL_REFINE_USER_PREAMBLE,
    build_repair_system_prompt,
    build_system_prompt,
    build_visual_refine_system_prompt,
    render_cpi_supervisor_prompt,
)
from figma_flutter_agent.llm.reasoning import (
    DEFAULT_LLM_MAX_OUTPUT_TOKENS,
    LLM_OUTPUT_TOKEN_CAP,
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
    generation_output_spec,
    repair_patch_output_spec,
)
from figma_flutter_agent.llm.cpi_supervisor import (
    build_cpi_supervisor_context,
    build_cpi_supervisor_user_payload,
)
from figma_flutter_agent.llm.payload_format import format_labeled_user_payload
from figma_flutter_agent.llm.payload_slim import dump_clean_tree_for_llm, dump_tokens_for_llm
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    DesignTokens,
    FlutterGenerationResponse,
    FlutterRepairPatchResponse,
    NodeType,
    RepairCpiSupervisorResponse,
)
from figma_flutter_agent.validation.pixel.models import DiffBandRegion
from figma_flutter_agent.llm.clients.protocol import _provider_api_label, _first_chat_choice

_T = TypeVar("_T")
_LLM_DEFAULT_MAX_RETRIES = 3
_LLM_HTTP_TIMEOUT_SEC = 180.0
_LLM_HTTP_CONNECT_TIMEOUT_SEC = 30.0


def _encode_png_base64(png_bytes: bytes) -> str:
    return base64.standard_b64encode(png_bytes).decode("ascii")


def _is_visual_refine_attachment(
    figma_reference_png: bytes | None,
    flutter_render_png: bytes | None,
) -> bool:
    return figma_reference_png is not None and flutter_render_png is not None


def _build_anthropic_user_content(
    prompt: str,
    figma_reference_png: bytes | None,
    flutter_render_png: bytes | None = None,
    visual_diff_png: bytes | None = None,
    *,
    user_preamble: str = REFERENCE_USER_PREAMBLE,
) -> str | list[dict[str, object]]:
    if figma_reference_png is None and flutter_render_png is None:
        return prompt
    content: list[dict[str, object]] = []
    visual_refine = _is_visual_refine_attachment(figma_reference_png, flutter_render_png)
    if visual_refine:
        content.append({"type": "text", "text": VISUAL_REFINE_IMAGE_INTRO})
    if figma_reference_png is not None:
        figma_label = (
            FIGMA_REFERENCE_INLINE_LABEL if visual_refine else FIGMA_REFERENCE_ONLY_LABEL
        )
        content.append({"type": "text", "text": figma_label})
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": _encode_png_base64(figma_reference_png),
                },
            }
        )
    if flutter_render_png is not None:
        content.append({"type": "text", "text": FLUTTER_RENDER_INLINE_LABEL})
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": _encode_png_base64(flutter_render_png),
                },
            }
        )
    if visual_diff_png is not None:
        content.append({"type": "text", "text": VISUAL_DIFF_INLINE_LABEL})
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": _encode_png_base64(visual_diff_png),
                },
            }
        )
    content.append({"type": "text", "text": f"{user_preamble}{prompt}"})
    return content


def _build_openai_user_content(
    prompt: str,
    figma_reference_png: bytes | None,
    flutter_render_png: bytes | None = None,
    visual_diff_png: bytes | None = None,
    *,
    user_preamble: str = REFERENCE_USER_PREAMBLE,
) -> str | list[dict[str, object]]:
    if figma_reference_png is None and flutter_render_png is None:
        return prompt
    content: list[dict[str, object]] = []
    visual_refine = _is_visual_refine_attachment(figma_reference_png, flutter_render_png)
    if visual_refine:
        content.append({"type": "text", "text": VISUAL_REFINE_IMAGE_INTRO})
    if figma_reference_png is not None:
        figma_label = (
            FIGMA_REFERENCE_INLINE_LABEL if visual_refine else FIGMA_REFERENCE_ONLY_LABEL
        )
        content.append({"type": "text", "text": figma_label})
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{_encode_png_base64(figma_reference_png)}",
                },
            }
        )
    if flutter_render_png is not None:
        content.append({"type": "text", "text": FLUTTER_RENDER_INLINE_LABEL})
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{_encode_png_base64(flutter_render_png)}",
                },
            }
        )
    if visual_diff_png is not None:
        content.append({"type": "text", "text": VISUAL_DIFF_INLINE_LABEL})
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{_encode_png_base64(visual_diff_png)}",
                },
            }
        )
    content.append({"type": "text", "text": f"{user_preamble}{prompt}"})
    return content


class BaseLlmClient(ABC):
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
        analytics_span_name: str | None = None,
    ) -> None:
        from figma_flutter_agent.observability.llm_trace import current_llm_trace_context
        from figma_flutter_agent.observability.posthog_llm import capture_ai_generation

        span_name = self._resolved_analytics_span_name(analytics_span_name)
        if span_name is None:
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
        )

    @staticmethod
    def _is_retryable(exc: LlmError) -> bool:
        if BaseLlmClient._is_truncation_error(exc):
            return False
        return exc.status_code is None or exc.status_code in {429, 500, 502, 503, 504}

    @staticmethod
    def _is_truncation_error(exc: LlmError) -> bool:
        message = str(exc).lower()
        return "truncated" in message or "max_tokens reached" in message

    def _bump_output_token_limit_after_truncation(self) -> bool:
        current = self._effective_max_output_tokens()
        if current >= LLM_OUTPUT_TOKEN_CAP:
            return False
        bumped = min(current * 2, LLM_OUTPUT_TOKEN_CAP)
        if bumped <= current:
            return False
        self._max_output_tokens_override = bumped
        logger.warning(
            "LLM response truncated at max_tokens={}; retrying with max_tokens={}",
            current,
            bumped,
        )
        return True

    @staticmethod
    def _retry_delay(attempt: int) -> float:
        return float((2**attempt) + random.uniform(0.1, 1.0))

    def _log_retry(self, exc: LlmError, *, delay: float, attempt: int) -> None:
        logger.warning(
            "LLM request failed for model {}: {} — retrying in {:.2f}s (attempt {}/{})",
            self._model,
            format_error_for_log(exc),
            delay,
            attempt + 1,
            self._max_retries,
        )

    def _run_with_retry(self, operation: Callable[[], _T]) -> _T:
        for attempt in range(self._max_retries):
            try:
                return operation()
            except LlmError as exc:
                if self._is_truncation_error(exc) and self._bump_output_token_limit_after_truncation():
                    if attempt == self._max_retries - 1:
                        raise
                    delay = self._retry_delay(attempt)
                    self._log_retry(exc, delay=delay, attempt=attempt)
                    time.sleep(delay)
                    continue
                if not self._is_retryable(exc) or attempt == self._max_retries - 1:
                    raise
                delay = self._retry_delay(attempt)
                self._log_retry(exc, delay=delay, attempt=attempt)
                time.sleep(delay)
        raise LlmError("LLM generation failed after retries")

    async def _run_with_retry_async(
        self,
        operation: Callable[[], Awaitable[_T]],
    ) -> _T:
        for attempt in range(self._max_retries):
            try:
                return await operation()
            except LlmError as exc:
                if self._is_truncation_error(exc) and self._bump_output_token_limit_after_truncation():
                    if attempt == self._max_retries - 1:
                        raise
                    delay = self._retry_delay(attempt)
                    self._log_retry(exc, delay=delay, attempt=attempt)
                    await asyncio.sleep(delay)
                    continue
                if not self._is_retryable(exc) or attempt == self._max_retries - 1:
                    raise
                delay = self._retry_delay(attempt)
                self._log_retry(exc, delay=delay, attempt=attempt)
                await asyncio.sleep(delay)
        raise LlmError("LLM generation failed after retries")

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
    ) -> tuple[str, str]:
        prompt = self._build_user_prompt(
            clean_tree,
            tokens,
            feature_name=feature_name,
            asset_manifest=asset_manifest,
            widget_hints=widget_hints,
            navigation_hints=navigation_hints,
            use_screen_ir=use_screen_ir,
        )
        system_prompt = build_system_prompt(
            routing_enabled=routing_enabled,
            theme_variant=theme_variant,
            figma_reference_attached=figma_reference_png is not None,
            stack_root=clean_tree.type == NodeType.STACK,
            use_screen_ir=use_screen_ir,
        )
        return prompt, system_prompt

    def _finalize_generation_response(
        self,
        response: FlutterGenerationResponse,
        *,
        clean_tree: CleanDesignTreeNode,
        use_screen_ir: bool,
        require_screen_ir: bool = False,
        project_dir: Path | None = None,
        tokens: DesignTokens | None = None,
        feature_name: str | None = None,
    ) -> FlutterGenerationResponse:
        if response.screen_ir is not None:
            from figma_flutter_agent.debug.ir_dumps import write_screen_ir_snapshot
            from figma_flutter_agent.generator.ir.presence import (
                expand_extracted_widget_names_for_validate,
                normalize_screen_ir_presence,
            )
            from figma_flutter_agent.generator.ir.validate import (
                validate_extracted_widgets,
                validate_screen_ir,
            )

            if project_dir is not None and feature_name:
                write_screen_ir_snapshot(
                    stage="llm_parsed",
                    feature_name=feature_name,
                    screen_ir=response.screen_ir,
                    extracted_widgets=response.extracted_widgets or None,
                    project_dir=project_dir,
                )

            extracted = frozenset(widget.widget_name for widget in response.extracted_widgets)
            screen_ir = normalize_screen_ir_presence(
                response.screen_ir,
                clean_tree,
                extracted_widget_names=extracted,
            )
            if screen_ir is not response.screen_ir:
                response = response.model_copy(update={"screen_ir": screen_ir})
            extracted_for_validate = expand_extracted_widget_names_for_validate(
                extracted,
                clean_tree=clean_tree,
                screen_ir=screen_ir,
            )
            validate_screen_ir(
                response.screen_ir,
                clean_tree,
                extracted_widget_names=extracted_for_validate,
                project_dir=project_dir,
                tokens=tokens,
                skip_presence_normalize=True,
            )
            validate_extracted_widgets(
                response.extracted_widgets,
                clean_tree,
                project_dir=project_dir,
                tokens=tokens,
            )
            if project_dir is not None and feature_name and response.screen_ir is not None:
                write_screen_ir_snapshot(
                    stage="llm_validated",
                    feature_name=feature_name,
                    screen_ir=response.screen_ir,
                    extracted_widgets=response.extracted_widgets or None,
                    project_dir=project_dir,
                )
            return response.model_copy(update={"screen_code": None})
        if response.resolved_screen_code():
            raise LlmError(
                "Model returned screenCode; screenIr is required and Dart screen bodies "
                "are no longer accepted"
            )
        raise LlmError("LLM response missing screenIr")

    def _parse_repair_patch_response(self, raw_text: str) -> FlutterRepairPatchResponse:
        try:
            payload = json.loads(self._coerce_json_text(raw_text))
            return FlutterRepairPatchResponse.model_validate(payload)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("LLM repair patch validation failed: {}", exc)
            raise LlmError(f"LLM repair patch validation failed: {exc}") from exc

    def _parse_cpi_supervisor_response(self, raw_text: str) -> RepairCpiSupervisorResponse:
        try:
            payload = json.loads(self._coerce_json_text(raw_text))
            return RepairCpiSupervisorResponse.model_validate(payload)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("CPI supervisor validation failed: {}", exc)
            raise LlmError(f"CPI supervisor validation failed: {exc}") from exc

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
    ) -> str:
        from figma_flutter_agent.generator.ir.tree import index_clean_tree
        from figma_flutter_agent.llm.ir_payload import (
            dump_screen_ir_blueprint,
            dump_widget_ir_blueprint,
        )

        user_payload: dict[str, Any] = {
            "featureName": feature_name,
            "cleanTree": dump_clean_tree_for_llm(clean_tree),
            "tokens": dump_tokens_for_llm(tokens),
            "assetManifest": asset_manifest,
        }
        if use_screen_ir:
            user_payload["screenIrBlueprint"] = dump_screen_ir_blueprint(clean_tree)
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

    @staticmethod
    def _coerce_json_text(raw_text: str) -> str:
        """Strip markdown fences and whitespace from provider JSON payloads."""
        text = raw_text.strip()
        if not text.startswith("```"):
            return text
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()

    def _looks_like_truncated_json(self, raw_text: str) -> bool:
        text = self._coerce_json_text(raw_text)
        if not text:
            return True
        if text.count("{") != text.count("}"):
            return True
        if text.count("[") != text.count("]"):
            return True
        return text.rstrip().endswith(",")

    def _parse_generation_response(self, raw_text: str) -> FlutterGenerationResponse:
        coerced = self._coerce_json_text(raw_text)
        if self._looks_like_truncated_json(raw_text):
            raise LlmError(
                "LLM response JSON appears truncated (unbalanced brackets or trailing comma); "
                "increase max output tokens or reduce payload size"
            )
        try:
            payload = json.loads(coerced)
            return FlutterGenerationResponse.model_validate(payload)
        except json.JSONDecodeError as exc:
            logger.warning("LLM structured output JSON parse failed: {}", exc)
            raise LlmError(f"LLM response validation failed: {exc}") from exc
        except ValueError as exc:
            logger.warning("LLM structured output validation failed: {}", exc)
            raise LlmError(f"LLM response validation failed: {exc}") from exc

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
