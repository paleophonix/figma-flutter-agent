"""OpenRouter and OpenCode step execution."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Protocol

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
from figma_flutter_agent.llm.openrouter_fusion import build_single_invocation
from figma_flutter_agent.llm.schema import StructuredOutputSpec
from loguru import logger


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
        outer_round: int = 1,
    ) -> dict[str, Any]:
        from figma_flutter_agent.dev.opencode import create_openrouter_debug_client

        system_prompt = assemble_step_prompt(
            step,
            board=board,
            run_context=run_context,
            reasoning_chain_json=(
                chain.compact_json_for_refine(run_context.get("pivot"))
                if run_context.get("pivot")
                else chain.compact_json()
            ),
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
        pipeline = self._settings.agent.debug_pipeline
        started = time.perf_counter()
        active_invocation = invocation
        raw = client.complete_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output_spec=output_spec,
            invocation=active_invocation,
            figma_reference_png=figma_png if step == "recognise" else None,
            analytics_span_name=f"repair.{step}",
        )
        try:
            payload = parse_step_json(raw, step=step)
        except LlmError as exc:
            if not invocation.use_fusion:
                raise
            judge_model = (
                invocation.judge_model
                or pipeline.model_for_step(step, board=board)
            )
            logger.warning(
                "OpenRouter Fusion returned non-JSON for repair.{}; retrying judge model {}",
                step,
                judge_model,
            )
            active_invocation = build_single_invocation(model=judge_model)
            raw = client.complete_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                output_spec=output_spec,
                invocation=active_invocation,
                figma_reference_png=figma_png if step == "recognise" else None,
                analytics_span_name=f"repair.{step}.fusion_fallback",
            )
            payload = parse_step_json(raw, step=step)
            logger.info(
                "Fusion fallback succeeded for repair.{} via {}",
                step,
                judge_model,
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


def write_step_state(state_dir: Path, step: str, payload: dict[str, Any]) -> Path:
    """Persist step JSON under ``.repair/state/``."""
    path = state_dir / f"{step}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
