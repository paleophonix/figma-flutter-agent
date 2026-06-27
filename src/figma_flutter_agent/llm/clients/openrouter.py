"""OpenRouterLlmClient — Flutter codegen via OpenRouter OpenAI-compatible API."""

from __future__ import annotations

import json
import time

from loguru import logger

from figma_flutter_agent.errors import LlmError
from figma_flutter_agent.llm.capabilities import LlmProvider
from figma_flutter_agent.llm.clients.client import _LLM_DEFAULT_MAX_RETRIES
from figma_flutter_agent.llm.clients.content import _build_openai_user_content
from figma_flutter_agent.llm.clients.openai import OpenAiLlmClient
from figma_flutter_agent.llm.clients.protocol import _first_chat_choice, _provider_api_label
from figma_flutter_agent.llm.openrouter_fusion import OpenRouterFusionInvocation
from figma_flutter_agent.llm.openrouter_usage import (
    OpenRouterUsageCost,
    parse_usage_from_response_text,
)
from figma_flutter_agent.llm.reasoning import DEFAULT_LLM_MAX_OUTPUT_TOKENS, LlmReasoningSettings
from figma_flutter_agent.llm.schema import StructuredOutputSpec

_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterLlmClient(OpenAiLlmClient):
    """Generate Flutter widget code through the OpenRouter OpenAI-compatible API."""

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        provider: LlmProvider = "openrouter",
        strict_json_schema: bool = False,
        temperature: float | None = None,
        top_p: float | None = None,
        reasoning: LlmReasoningSettings | None = None,
        max_retries: int = _LLM_DEFAULT_MAX_RETRIES,
        max_output_tokens: int = DEFAULT_LLM_MAX_OUTPUT_TOKENS,
    ) -> None:
        super().__init__(
            api_key=api_key,
            model=model,
            base_url=_OPENROUTER_BASE_URL,
            provider=provider,
            strict_json_schema=strict_json_schema,
            temperature=temperature,
            top_p=top_p,
            reasoning=reasoning,
            max_retries=max_retries,
            max_output_tokens=max_output_tokens,
        )
        self._last_token_usage: dict[str, int | float | None] = {
            "input_tokens": None,
            "output_tokens": None,
            "total_cost_usd": None,
            "input_cost_usd": None,
            "output_cost_usd": None,
        }
        self._last_usage_cost = OpenRouterUsageCost(None, None, None)

    def _chat_completions_create(self, **kwargs: object) -> object:
        """Capture OpenRouter ``usage.cost`` from the raw HTTP body before SDK parsing."""
        raw = self._client.chat.completions.with_raw_response.create(**kwargs)
        self._last_usage_cost = parse_usage_from_response_text(raw.text)
        try:
            return raw.parse()
        except (json.JSONDecodeError, ValueError) as exc:
            preview = (raw.text or "").strip()[:200]
            logger.warning(
                "OpenRouter returned malformed JSON body (model={}, preview={!r})",
                kwargs.get("model", self._model),
                preview,
            )
            raise LlmError(
                f"OpenRouter returned malformed JSON body (preview={preview!r}): {exc}"
            ) from exc

    def complete_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        output_spec: StructuredOutputSpec,
        invocation: OpenRouterFusionInvocation | None = None,
        figma_reference_png: bytes | None = None,
        flutter_render_png: bytes | None = None,
        visual_diff_png: bytes | None = None,
        analytics_span_name: str | None = None,
    ) -> str:
        """Run a structured JSON chat completion, optionally via OpenRouter Fusion.

        Args:
            system_prompt: System instruction text.
            user_prompt: User message text.
            output_spec: JSON schema response contract.
            invocation: When set, uses Fusion ``plugins`` and outer ``model``; else client model.
            figma_reference_png: Optional vision attachment.
            flutter_render_png: Optional vision attachment.
            visual_diff_png: Optional vision attachment.
            analytics_span_name: Optional analytics span label.

        Returns:
            Assistant message content (JSON string).

        Raises:
            LlmError: On empty, truncated, or transport failures.
        """
        user_content = _build_openai_user_content(
            user_prompt,
            figma_reference_png,
            flutter_render_png,
            visual_diff_png,
        )
        model_override = invocation.model if invocation is not None else None
        plugins = invocation.plugins_payload() if invocation is not None else None
        started = time.perf_counter()
        try:
            response = self._openai_chat_completion(
                system_prompt=system_prompt,
                user_content=user_content,
                output_spec=output_spec,
                model_override=model_override,
                plugins=plugins,
            )
            choice = _first_chat_choice(
                response,
                provider=self._provider,
                model=model_override or self._model,
            )
            if choice.finish_reason == "length":
                raise LlmError("LLM response truncated (max_tokens reached)")
            message = choice.message
            content = (message.content or "").strip()
            if not content:
                raise LlmError("LLM returned no text content")
            usage = getattr(response, "usage", None)
            input_tokens = getattr(usage, "prompt_tokens", None)
            output_tokens = getattr(usage, "completion_tokens", None)
            self._last_token_usage = {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_cost_usd": self._last_usage_cost.total_cost_usd,
                "input_cost_usd": self._last_usage_cost.input_cost_usd,
                "output_cost_usd": self._last_usage_cost.output_cost_usd,
            }
            self._emit_llm_analytics(
                latency_sec=time.perf_counter() - started,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                output_text=content,
                is_error=False,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_cost_usd=self._last_usage_cost.total_cost_usd,
                input_cost_usd=self._last_usage_cost.input_cost_usd,
                output_cost_usd=self._last_usage_cost.output_cost_usd,
                analytics_span_name=analytics_span_name,
            )
            return content
        except Exception as exc:
            self._emit_llm_analytics(
                latency_sec=time.perf_counter() - started,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                output_text=None,
                is_error=True,
                error_message=str(exc),
                analytics_span_name=analytics_span_name,
            )
            if isinstance(exc, LlmError):
                raise
            raise LlmError(
                f"{_provider_api_label(self._provider)} structured completion failed: {exc}"
            ) from exc
