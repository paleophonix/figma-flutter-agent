"""Provider capability matrix for structured JSON output (workspace rule §8)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from figma_flutter_agent.errors import LlmError

LlmProvider = Literal["anthropic", "openai", "openrouter", "google"]

# OpenRouter upstream slugs routed to OpenAI Chat Completions with json_schema strict.
_OPENROUTER_OPENAI_STRICT_PREFIX = "openai/"


@dataclass(frozen=True)
class ProviderCapabilities:
    """Structured-output support for an LLM provider."""

    supports_strict_json_schema: bool
    recommended_models: tuple[str, ...]
    notes: str = ""


_PROVIDER_CAPABILITIES: dict[LlmProvider, ProviderCapabilities] = {
    "anthropic": ProviderCapabilities(
        supports_strict_json_schema=True,
        recommended_models=("claude-sonnet-4-6",),
        notes="Tool-use + strict JSON schema via Messages API.",
    ),
    "openai": ProviderCapabilities(
        supports_strict_json_schema=True,
        recommended_models=("gpt-4o", "gpt-4.1-mini"),
        notes="Chat Completions response_format json_schema strict.",
    ),
    "openrouter": ProviderCapabilities(
        supports_strict_json_schema=False,
        recommended_models=("anthropic/claude-sonnet-4",),
        notes=(
            "OpenAI-compat proxy; json_schema strict is enabled for openai/* upstream "
            "slugs via resolve_strict_json_schema."
        ),
    ),
    "google": ProviderCapabilities(
        supports_strict_json_schema=False,
        recommended_models=("gemini-2.5-flash", "gemini-2.0-flash"),
        notes="Google AI Studio key (GOOGLE_API_KEY); Gemini via OpenAI-compat endpoint.",
    ),
}


def provider_capabilities(provider: LlmProvider) -> ProviderCapabilities:
    """Return capability metadata for a provider.

    Raises:
        LlmError: When ``provider`` is not a supported name.
    """
    try:
        return _PROVIDER_CAPABILITIES[provider]
    except KeyError as exc:
        raise LlmError(f"Unsupported LLM provider: {provider}") from exc


def resolve_strict_json_schema(*, provider: LlmProvider, model: str) -> bool:
    """Return whether structured LLM calls should use json_schema strict mode.

    Args:
        provider: Active LLM provider name.
        model: Resolved provider model identifier (OpenRouter slugs include vendor prefix).

    Returns:
        True when the provider/model pair is known to honor strict JSON schema output.
    """
    caps = provider_capabilities(provider)
    if provider == "openrouter":
        slug = model.strip().casefold()
        if slug.startswith(_OPENROUTER_OPENAI_STRICT_PREFIX):
            return True
    return caps.supports_strict_json_schema


def log_structured_output_fallback(*, provider: LlmProvider, model: str) -> None:
    """Log when structured output cannot rely on strict provider schema mode."""
    from loguru import logger

    caps = provider_capabilities(provider)
    strict = resolve_strict_json_schema(provider=provider, model=model)
    logger.bind(provider=provider, model=model).warning(
        "LLM structured_output_fallback: provider {} does not guarantee strict JSON schema "
        "(request uses json_schema with strict={}). {}",
        provider,
        strict,
        caps.notes,
    )


def validate_llm_provider_setup(
    *,
    provider: LlmProvider,
    model: str,
    require_strict_json_schema: bool,
) -> None:
    """Validate provider/model against the capability matrix.

    Args:
        provider: Active LLM provider.
        model: Resolved model identifier.
        require_strict_json_schema: When True, prefer strict schema mode when the provider
            supports it; otherwise log a structured-output fallback warning and continue.

    Raises:
        LlmError: When the provider name is unsupported.
    """
    if require_strict_json_schema and not resolve_strict_json_schema(
        provider=provider,
        model=model,
    ):
        log_structured_output_fallback(provider=provider, model=model)
