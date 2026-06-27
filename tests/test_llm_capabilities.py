"""Tests for LLM provider capability matrix."""

from loguru import logger

from figma_flutter_agent.llm.capabilities import (
    resolve_strict_json_schema,
    validate_llm_provider_setup,
)
from figma_flutter_agent.llm.clients import GoogleLlmClient, create_llm_client


def test_resolve_strict_json_schema_openrouter_openai_slug() -> None:
    assert resolve_strict_json_schema(provider="openrouter", model="openai/gpt-5.4") is True
    assert resolve_strict_json_schema(provider="openrouter", model="OpenAI/gpt-5.4") is True


def test_resolve_strict_json_schema_openrouter_non_openai_slug() -> None:
    assert (
        resolve_strict_json_schema(provider="openrouter", model="anthropic/claude-sonnet-4")
        is False
    )


def test_validate_warns_openrouter_when_strict_schema_requested() -> None:
    messages: list[str] = []
    handler_id = logger.add(lambda message: messages.append(message.record["message"]))
    try:
        validate_llm_provider_setup(
            provider="openrouter",
            model="anthropic/claude-sonnet-4",
            require_strict_json_schema=True,
        )
    finally:
        logger.remove(handler_id)

    assert any("structured_output_fallback" in message for message in messages)


def test_create_llm_client_allows_anthropic_with_strict_schema() -> None:
    client = create_llm_client(
        provider="anthropic",
        api_key="test",
        model="claude-sonnet-4-6",
        require_strict_json_schema=True,
    )
    assert client is not None


def test_create_llm_client_allows_openrouter_when_strict_schema_requested() -> None:
    client = create_llm_client(
        provider="openrouter",
        api_key="test",
        model="anthropic/claude-sonnet-4",
        require_strict_json_schema=True,
    )
    assert client is not None


def test_create_llm_client_openrouter_openai_slug_uses_strict_schema() -> None:
    client = create_llm_client(
        provider="openrouter",
        api_key="test",
        model="openai/gpt-5.4",
        require_strict_json_schema=False,
    )
    assert client._strict_json_schema is True


def test_create_llm_client_logs_fallback_for_openrouter_non_openai() -> None:
    messages: list[str] = []
    handler_id = logger.add(lambda message: messages.append(message.record["message"]))
    try:
        create_llm_client(
            provider="openrouter",
            api_key="test",
            model="anthropic/claude-sonnet-4",
            require_strict_json_schema=False,
        )
    finally:
        logger.remove(handler_id)

    assert any("structured_output_fallback" in message for message in messages)


def test_google_client_defaults_to_non_strict_schema() -> None:
    client = GoogleLlmClient(api_key="test", model="gemini-2.0-flash")
    assert client._strict_json_schema is False
