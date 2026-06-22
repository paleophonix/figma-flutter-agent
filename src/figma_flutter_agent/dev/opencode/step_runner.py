"""OpenRouter and OpenCode step execution."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from loguru import logger

from figma_flutter_agent.config.debug_pipeline import DebugPipelineStep
from figma_flutter_agent.config.settings import Settings
from figma_flutter_agent.dev.opencode.panel_merge import persist_fusion_metadata
from figma_flutter_agent.dev.opencode.prompt_assembler import assemble_step_prompt
from figma_flutter_agent.dev.opencode.reasoning_chain import ReasoningChain
from figma_flutter_agent.dev.opencode.schema_gate import (
    parse_step_json,
    structured_output_spec,
    validate_step_output,
)
from figma_flutter_agent.dev.opencode.trace import RepairTraceRecorder
from figma_flutter_agent.errors import LlmError
from figma_flutter_agent.llm.openrouter_fusion import (
    OpenRouterFusionInvocation,
    build_single_invocation,
)
from figma_flutter_agent.llm.schema import StructuredOutputSpec


@dataclass(frozen=True)
class _StructuredStepResponse:
    """Assistant JSON text plus the invocation that produced it."""

    content: str
    invocation: OpenRouterFusionInvocation


class StepRunner(Protocol):
    """Injectable step runner for tests."""

    def run_read_step(
        self,
        step: DebugPipelineStep,
        *,
        board: str,
        run_context: dict[str, Any],
        chain: ReasoningChain,
        user_prompt: str,
        figma_png: bytes | None = None,
        flutter_render_png: bytes | None = None,
        outer_round: int = 1,
    ) -> dict[str, Any]: ...


class OpenRouterStepRunner:
    """Execute read-only steps via OpenRouter structured output."""

    def __init__(
        self,
        settings: Settings,
        *,
        state_dir: Path | None = None,
        trace: RepairTraceRecorder | None = None,
    ) -> None:
        self._settings = settings
        self._state_dir = state_dir
        self._trace = trace

    def run_read_step(
        self,
        step: DebugPipelineStep,
        *,
        board: str,
        run_context: dict[str, Any],
        chain: ReasoningChain,
        user_prompt: str,
        figma_png: bytes | None = None,
        flutter_render_png: bytes | None = None,
        outer_round: int = 1,
    ) -> dict[str, Any]:
        from figma_flutter_agent.dev.opencode import create_openrouter_debug_client

        system_prompt = assemble_step_prompt(
            step,
            board=board,
            run_context=run_context,
            reasoning_chain_json=chain.compact_json_for_step(
                step,
                run_context.get("pivot"),
            ),
            l6_bindings=run_context.get("_l6_bindings"),
        )
        name, schema = structured_output_spec(step)
        output_spec = StructuredOutputSpec(
            name=name,
            schema=schema,
            anthropic_tool_name=name,
            anthropic_tool_description=f"Repair pipeline {step} output",
        )
        client, invocation = create_openrouter_debug_client(
            self._settings,
            step=step,
            board=board,
            outer_round=outer_round,
        )
        from figma_flutter_agent.dev.opencode.repair_log import emit_repair_progress

        fusion_panel = ""
        if invocation.use_fusion and invocation.analysis_models:
            fusion_panel = f" panel={','.join(invocation.analysis_models)}"
        emit_repair_progress(
            step,
            f"OpenRouter {invocation.model}{fusion_panel}",
        )
        pipeline = self._settings.agent.debug_pipeline
        started = time.perf_counter()
        active_invocation = invocation
        raw = self._complete_structured_with_fusion_fallback(
            client=client,
            invocation=invocation,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output_spec=output_spec,
            step=step,
            board=board,
            figma_png=figma_png,
            flutter_render_png=flutter_render_png,
        )
        active_invocation = raw.invocation
        payload, active_invocation = self._parse_step_with_retry(
            client=client,
            raw=raw,
            step=step,
            board=board,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output_spec=output_spec,
            figma_png=figma_png,
            flutter_render_png=flutter_render_png,
            primary_invocation=invocation,
            active_invocation=active_invocation,
        )
        duration_ms = (time.perf_counter() - started) * 1000.0
        payload = validate_step_output(step, payload)
        token_meta = {
            "tokens_in": getattr(client, "_last_token_usage", {}).get("input_tokens"),
            "tokens_out": getattr(client, "_last_token_usage", {}).get("output_tokens"),
            "cost_usd": getattr(client, "_last_token_usage", {}).get("total_cost_usd"),
            "input_cost_usd": getattr(client, "_last_token_usage", {}).get("input_cost_usd"),
            "output_cost_usd": getattr(client, "_last_token_usage", {}).get("output_cost_usd"),
        }
        panel_src: Path | None = None
        if active_invocation.use_fusion:
            panel_path = persist_fusion_metadata(
                step,
                active_invocation,
                state_dir=self._state_dir,
            )
            if panel_path is not None:
                panel_src = panel_path.parent
        if self._trace is not None:
            pipeline = self._settings.agent.debug_pipeline
            self._trace.record_step(
                step,
                payload,
                duration_ms=duration_ms,
                meta={
                    "model": invocation.model,
                    "fusion": active_invocation.use_fusion,
                    "fusion_fallback": active_invocation is not invocation,
                    "effort": pipeline.effort,
                    **{k: v for k, v in token_meta.items() if v is not None},
                },
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                panel_src=panel_src,
            )
        elif active_invocation.use_fusion:
            persist_fusion_metadata(
                step,
                active_invocation,
                state_dir=self._state_dir,
            )
        return payload

    def _judge_model_for_parse_retry(
        self,
        *,
        step: DebugPipelineStep,
        board: str,
        primary_invocation: OpenRouterFusionInvocation,
    ) -> str:
        """Resolve the direct OpenRouter slug used for structured-output parse retries."""
        pipeline = self._settings.agent.debug_pipeline
        if primary_invocation.use_fusion:
            return (
                primary_invocation.judge_model
                or pipeline.single_model_for_step(step, board=board)
            )
        return pipeline.single_model_for_step(step, board=board)

    def _parse_step_with_retry(
        self,
        *,
        client: Any,
        raw: _StructuredStepResponse,
        step: DebugPipelineStep,
        board: str,
        system_prompt: str,
        user_prompt: str,
        output_spec: StructuredOutputSpec,
        figma_png: bytes | None,
        flutter_render_png: bytes | None,
        primary_invocation: OpenRouterFusionInvocation,
        active_invocation: OpenRouterFusionInvocation,
    ) -> tuple[dict[str, Any], OpenRouterFusionInvocation]:
        """Parse step JSON; retry once on direct judge model when prose or tools leak in."""
        content = raw.content
        try:
            return parse_step_json(content, step=step), active_invocation
        except LlmError:
            judge_model = self._judge_model_for_parse_retry(
                step=step,
                board=board,
                primary_invocation=primary_invocation,
            )
            logger.warning(
                "OpenRouter returned non-JSON for repair.{}; retrying judge model {}",
                step,
                judge_model,
            )
            retry_invocation = build_single_invocation(model=judge_model)
            fallback = self._complete_structured_with_fusion_fallback(
                client=client,
                invocation=retry_invocation,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                output_spec=output_spec,
                step=step,
                board=board,
                figma_png=figma_png,
                flutter_render_png=flutter_render_png,
                analytics_suffix=".structured_parse_retry",
            )
            payload = parse_step_json(fallback.content, step=step)
            logger.info(
                "Structured parse retry succeeded for repair.{} via {}",
                step,
                judge_model,
            )
            return payload, fallback.invocation

    def _complete_structured_with_fusion_fallback(
        self,
        *,
        client: Any,
        invocation: OpenRouterFusionInvocation,
        system_prompt: str,
        user_prompt: str,
        output_spec: StructuredOutputSpec,
        step: DebugPipelineStep,
        board: str,
        figma_png: bytes | None,
        flutter_render_png: bytes | None = None,
        analytics_suffix: str = "",
    ) -> _StructuredStepResponse:
        """Call OpenRouter structured output; retry judge model when Fusion fails."""
        pipeline = self._settings.agent.debug_pipeline
        span = f"repair.{step}{analytics_suffix}"
        try:
            content = client.complete_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                output_spec=output_spec,
                invocation=invocation,
                figma_reference_png=figma_png if step == "recognise" else None,
                flutter_render_png=flutter_render_png if step == "recognise" else None,
                analytics_span_name=span,
            )
            return _StructuredStepResponse(content=content, invocation=invocation)
        except LlmError as exc:
            if not invocation.use_fusion or analytics_suffix:
                raise
            judge_model = invocation.judge_model or pipeline.model_for_step(step, board=board)
            logger.warning(
                "OpenRouter Fusion transport failed for repair.{}: {}; retrying judge model {}",
                step,
                exc,
                judge_model,
            )
            fallback = build_single_invocation(model=judge_model)
            content = client.complete_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                output_spec=output_spec,
                invocation=fallback,
                figma_reference_png=figma_png if step == "recognise" else None,
                flutter_render_png=flutter_render_png if step == "recognise" else None,
                analytics_span_name=f"{span}.fusion_fallback",
            )
            logger.info("Fusion transport fallback succeeded for repair.{} via {}", step, judge_model)
            return _StructuredStepResponse(content=content, invocation=fallback)


def write_step_state(state_dir: Path, step: str, payload: dict[str, Any]) -> Path:
    """Persist step JSON under ``.repair/state/``."""
    path = state_dir / f"{step}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
