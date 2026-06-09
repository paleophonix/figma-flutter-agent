"""Tests for LLM provider capability matrix."""

from loguru import logger

from figma_flutter_agent.llm.capabilities import validate_llm_provider_setup
from figma_flutter_agent.llm.clients import GoogleLlmClient, create_llm_client


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


def test_create_llm_client_logs_fallback_for_openrouter() -> None:
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
