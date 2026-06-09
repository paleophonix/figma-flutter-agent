"""OpenRouterLlmClient — Flutter codegen via OpenRouter OpenAI-compatible API."""

from __future__ import annotations

from figma_flutter_agent.llm.capabilities import LlmProvider
from figma_flutter_agent.llm.reasoning import DEFAULT_LLM_MAX_OUTPUT_TOKENS, LlmReasoningSettings
from figma_flutter_agent.llm.clients.base import _LLM_DEFAULT_MAX_RETRIES
from figma_flutter_agent.llm.clients.openai import OpenAiLlmClient

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
