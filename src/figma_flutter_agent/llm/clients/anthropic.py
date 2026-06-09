"""AnthropicLlmClient — Flutter codegen via Anthropic Messages API."""

from __future__ import annotations

import json
import time

import anthropic
from loguru import logger

from figma_flutter_agent.errors import LlmError
from figma_flutter_agent.llm.capabilities import LlmProvider
from figma_flutter_agent.llm.prompts import REFERENCE_USER_PREAMBLE
from figma_flutter_agent.llm.reasoning import DEFAULT_LLM_MAX_OUTPUT_TOKENS, LlmReasoningSettings
from figma_flutter_agent.llm.schema import StructuredOutputSpec, generation_output_spec
from figma_flutter_agent.llm.clients.base import (
    BaseLlmClient,
    _LLM_DEFAULT_MAX_RETRIES,
    _build_anthropic_user_content,
)

_ANTHROPIC_TOOL_NAME = "emit_flutter_generation"


class AnthropicLlmClient(BaseLlmClient):
    """Generate Flutter widget code through Anthropic Messages API."""

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        provider: LlmProvider = "anthropic",
        strict_json_schema: bool = True,
        temperature: float | None = None,
        top_p: float | None = None,
        reasoning: LlmReasoningSettings | None = None,
        max_retries: int = _LLM_DEFAULT_MAX_RETRIES,
        max_output_tokens: int = DEFAULT_LLM_MAX_OUTPUT_TOKENS,
    ) -> None:
        super().__init__(
            model,
            provider=provider,
            strict_json_schema=strict_json_schema,
            temperature=temperature,
            top_p=top_p,
            reasoning=reasoning,
            max_retries=max_retries,
            max_output_tokens=max_output_tokens,
        )
        self._client = anthropic.Anthropic(api_key=api_key)

    def _anthropic_create_kwargs(
        self,
        *,
        system_prompt: str,
        user_content: str | list[dict[str, object]],
        include_reasoning: bool,
        output_spec: StructuredOutputSpec,
    ) -> dict[str, object]:
        max_tokens = self._effective_max_output_tokens()
        kwargs: dict[str, object] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_content}],
            "tools": [
                {
                    "name": output_spec.anthropic_tool_name,
                    "description": output_spec.anthropic_tool_description,
                    "input_schema": output_spec.schema,
                }
            ],
            "tool_choice": {"type": "tool", "name": output_spec.anthropic_tool_name},
            **self._sampling_kwargs(),
        }
        if include_reasoning:
            kwargs.update(
                self._reasoning_settings.anthropic_create_kwargs(
                    max_output_tokens=max_tokens,
                )
            )
        return kwargs

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
        spec = output_spec or generation_output_spec(strict=self._strict_json_schema)
        user_content = _build_anthropic_user_content(
            prompt,
            figma_reference_png,
            flutter_render_png,
            visual_diff_png,
            user_preamble=user_preamble,
        )
        include_reasoning = self._include_reasoning()
        started = time.perf_counter()
        try:
            try:
                response = self._client.messages.create(
                    **self._anthropic_create_kwargs(
                        system_prompt=system_prompt,
                        user_content=user_content,
                        include_reasoning=include_reasoning,
                        output_spec=spec,
                    )
                )
            except anthropic.APIError as exc:
                llm_error = LlmError(
                    f"Anthropic API error: {exc}", status_code=getattr(exc, "status_code", None)
                )
                if self._should_retry_without_reasoning(llm_error):
                    self._suppress_reasoning_after_rejection(llm_error)
                    response = self._client.messages.create(
                        **self._anthropic_create_kwargs(
                            system_prompt=system_prompt,
                            user_content=user_content,
                            include_reasoning=False,
                            output_spec=spec,
                        )
                    )
                else:
                    raise llm_error from exc

            for block in response.content:
                if block.type == "tool_use" and block.name == spec.anthropic_tool_name:
                    if isinstance(block.input, str):
                        output_text = block.input
                    else:
                        output_text = json.dumps(block.input, ensure_ascii=True)
                    usage = getattr(response, "usage", None)
                    self._emit_llm_analytics(
                        latency_sec=time.perf_counter() - started,
                        system_prompt=system_prompt,
                        user_prompt=prompt,
                        output_text=output_text,
                        is_error=False,
                        input_tokens=getattr(usage, "input_tokens", None),
                        output_tokens=getattr(usage, "output_tokens", None),
                        analytics_span_name=analytics_span_name,
                    )
                    return output_text

            raise LlmError("LLM returned no tool_use content")
        except Exception as exc:
            self._emit_llm_analytics(
                latency_sec=time.perf_counter() - started,
                system_prompt=system_prompt,
                user_prompt=prompt,
                output_text=None,
                is_error=True,
                error_message=str(exc),
                analytics_span_name=analytics_span_name,
            )
            raise
