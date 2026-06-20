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
    structured_output_spec,
    validate_step_output,
)
from figma_flutter_agent.dev.opencode.trace import RepairTraceRecorder
from figma_flutter_agent.errors import FigmaFlutterError
from figma_flutter_agent.llm.schema import StructuredOutputSpec


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
    ) -> dict[str, Any]:
        from figma_flutter_agent.dev.opencode import create_openrouter_debug_client

        system_prompt = assemble_step_prompt(
            step,
            board=board,
            run_context=run_context,
            reasoning_chain_json=chain.compact_json(),
        )
        name, schema = structured_output_spec(step)
        output_spec = StructuredOutputSpec(
            name=name,
            schema=schema,
            anthropic_tool_name=name,
            anthropic_tool_description=f"Repair pipeline {step} output",
        )
        client, invocation = create_openrouter_debug_client(self._settings, step=step)
        started = time.perf_counter()
        raw = client.complete_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output_spec=output_spec,
            invocation=invocation,
            figma_reference_png=figma_png if step == "recognise" else None,
            analytics_span_name=f"repair.{step}",
        )
        duration_ms = (time.perf_counter() - started) * 1000.0
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise FigmaFlutterError(f"Step {step} returned non-object JSON")
        validate_step_output(step, payload)
        panel_src: Path | None = None
        if invocation.use_fusion:
            panel_path = persist_fusion_metadata(
                step,
                invocation,
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
                    "fusion": invocation.use_fusion,
                    "effort": pipeline.effort,
                },
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                panel_src=panel_src,
            )
        elif invocation.use_fusion:
            persist_fusion_metadata(
                step,
                invocation,
                state_dir=self._state_dir,
            )
        return payload


def write_step_state(state_dir: Path, step: str, payload: dict[str, Any]) -> Path:
    """Persist step JSON under ``.repair/state/``."""
    path = state_dir / f"{step}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
