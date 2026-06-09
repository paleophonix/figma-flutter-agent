"""Factory for creating LLM client instances."""

from __future__ import annotations

from figma_flutter_agent.errors import LlmError
from figma_flutter_agent.llm.capabilities import (
    LlmProvider,
    log_structured_output_fallback,
    provider_capabilities,
    validate_llm_provider_setup,
)
from figma_flutter_agent.llm.reasoning import DEFAULT_LLM_MAX_OUTPUT_TOKENS, LlmReasoningSettings
from figma_flutter_agent.llm.clients.client import _LLM_DEFAULT_MAX_RETRIES
from figma_flutter_agent.llm.clients.protocol import LlmClient
from figma_flutter_agent.llm.clients.anthropic import AnthropicLlmClient
from figma_flutter_agent.llm.clients.openai import OpenAiLlmClient
from figma_flutter_agent.llm.clients.openrouter import OpenRouterLlmClient
from figma_flutter_agent.llm.clients.google import GoogleLlmClient

_DEFAULT_MODELS: dict[LlmProvider, str] = {
    "anthropic": "claude-sonnet-4-6",
    "openai": "gpt-4o",
    "openrouter": "anthropic/claude-sonnet-4",
    "google": "gemini-2.5-flash",
}


def create_llm_client(
    *,
    provider: LlmProvider,
    api_key: str,
    model: str,
    require_strict_json_schema: bool = False,
    temperature: float | None = None,
    top_p: float | None = None,
    reasoning: LlmReasoningSettings | None = None,
    max_retries: int = _LLM_DEFAULT_MAX_RETRIES,
    max_output_tokens: int = DEFAULT_LLM_MAX_OUTPUT_TOKENS,
) -> LlmClient:
    """Create an LLM client for the configured provider.

    Args:
        provider: Active LLM provider name.
        api_key: Provider API key.
        model: Provider model identifier.
        require_strict_json_schema: When True, reject providers without strict schema support.
        temperature: Optional sampling temperature override.
        top_p: Optional nucleus sampling top_p override.
        reasoning: Optional reasoning/thinking controls; omitted params use provider defaults.
        max_retries: Maximum attempts on transient LLM API failures.
        max_output_tokens: Completion token budget; increased automatically when reasoning is on.

    Returns:
        Configured LLM client implementation.

    Raises:
        LlmError: If the provider name is unsupported or fails capability validation.
    """
    validate_llm_provider_setup(
        provider=provider,
        model=model,
        require_strict_json_schema=require_strict_json_schema,
    )
    caps = provider_capabilities(provider)
    strict_json_schema = caps.supports_strict_json_schema
    if not strict_json_schema:
        log_structured_output_fallback(provider=provider, model=model)
    resolved_reasoning = reasoning or LlmReasoningSettings()
    if provider == "anthropic":
        return AnthropicLlmClient(
            api_key=api_key,
            model=model,
            provider=provider,
            strict_json_schema=strict_json_schema,
            temperature=temperature,
            top_p=top_p,
            reasoning=resolved_reasoning,
            max_retries=max_retries,
            max_output_tokens=max_output_tokens,
        )
    if provider == "openai":
        return OpenAiLlmClient(
            api_key=api_key,
            model=model,
            provider=provider,
            strict_json_schema=strict_json_schema,
            temperature=temperature,
            top_p=top_p,
            reasoning=resolved_reasoning,
            max_retries=max_retries,
            max_output_tokens=max_output_tokens,
        )
    if provider == "openrouter":
        return OpenRouterLlmClient(
            api_key=api_key,
            model=model,
            provider=provider,
            strict_json_schema=strict_json_schema,
            temperature=temperature,
            top_p=top_p,
            reasoning=resolved_reasoning,
            max_retries=max_retries,
            max_output_tokens=max_output_tokens,
        )
    if provider == "google":
        return GoogleLlmClient(
            api_key=api_key,
            model=model,
            provider=provider,
            strict_json_schema=strict_json_schema,
            temperature=temperature,
            top_p=top_p,
            reasoning=resolved_reasoning,
            max_retries=max_retries,
            max_output_tokens=max_output_tokens,
        )
    raise LlmError(f"Unsupported LLM provider: {provider}")


def default_model_for_provider(provider: LlmProvider) -> str:
    """Return the default model identifier for a provider."""
    return _DEFAULT_MODELS[provider]
