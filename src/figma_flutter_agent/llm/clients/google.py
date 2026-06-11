"""GoogleLlmClient — Flutter codegen via Google AI Studio (Gemini OpenAI-compatible API)."""

from __future__ import annotations

from figma_flutter_agent.llm.capabilities import LlmProvider
from figma_flutter_agent.llm.clients.client import _LLM_DEFAULT_MAX_RETRIES
from figma_flutter_agent.llm.clients.openai import OpenAiLlmClient
from figma_flutter_agent.llm.reasoning import DEFAULT_LLM_MAX_OUTPUT_TOKENS, LlmReasoningSettings

_GOOGLE_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


class GoogleLlmClient(OpenAiLlmClient):
    """Generate Flutter widget code via Google AI Studio (Gemini OpenAI-compatible API)."""

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        provider: LlmProvider = "google",
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
            base_url=_GOOGLE_OPENAI_BASE_URL,
            provider=provider,
            strict_json_schema=strict_json_schema,
            temperature=temperature,
            top_p=top_p,
            reasoning=reasoning,
            max_retries=max_retries,
            max_output_tokens=max_output_tokens,
        )
