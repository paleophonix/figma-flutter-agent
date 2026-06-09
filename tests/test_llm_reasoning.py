from unittest.mock import MagicMock

import pytest
from openai import APITimeoutError

from figma_flutter_agent.config import Settings
from figma_flutter_agent.errors import LlmError
from figma_flutter_agent.llm.clients import OpenAiLlmClient, OpenRouterLlmClient
from figma_flutter_agent.llm.prompts import build_system_prompt
from figma_flutter_agent.llm.reasoning import (
    DEFAULT_LLM_MAX_OUTPUT_TOKENS,
    LlmReasoningSettings,
    is_likely_transport_failure,
    is_reasoning_parameter_rejection,
    is_unsupported_max_tokens_error,
    normalize_reasoning_effort,
    openai_allows_top_p,
    openai_output_token_param,
    resolve_max_output_tokens,
    should_fallback_without_reasoning,
)


def test_openai_output_token_param_for_gpt5_uses_completion_tokens() -> None:
    assert openai_output_token_param("gpt-5.5") == "max_completion_tokens"
    assert openai_output_token_param("openai/gpt-5.5") == "max_completion_tokens"
    assert openai_output_token_param("gpt-4o") == "max_tokens"


def test_openai_allows_top_p_for_legacy_models_only() -> None:
    assert openai_allows_top_p("gpt-4o") is True
    assert openai_allows_top_p("gpt-5.5") is False


def test_is_unsupported_max_tokens_error() -> None:
    assert is_unsupported_max_tokens_error(
        status_code=400,
        message="Unsupported parameter: 'max_tokens'. Use 'max_completion_tokens' instead.",
    )
    assert not is_unsupported_max_tokens_error(status_code=401, message="invalid key")


def test_openai_client_sends_max_completion_tokens_for_gpt55() -> None:
    mock_client = MagicMock()
    mock_message = MagicMock()
    mock_message.content = '{"screenCode":"class Demo {}","extractedWidgets":[]}'
    mock_choice = MagicMock()
    mock_choice.finish_reason = "stop"
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = None
    mock_client.chat.completions.create.return_value = mock_response

    client = OpenAiLlmClient(api_key="test-key", model="gpt-5.5", strict_json_schema=False)
    client._client = mock_client

    client._request_generation('{"featureName":"demo"}', system_prompt=build_system_prompt())

    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["max_completion_tokens"] == DEFAULT_LLM_MAX_OUTPUT_TOKENS
    assert "max_tokens" not in call_kwargs
    assert "top_p" not in call_kwargs


def test_normalize_reasoning_effort_rejects_unknown_values() -> None:
    assert normalize_reasoning_effort("medium") == "medium"
    assert normalize_reasoning_effort("HIGH") == "high"
    assert normalize_reasoning_effort("bogus") is None
    assert normalize_reasoning_effort("") is None


def test_reasoning_settings_none_effort_is_inactive() -> None:
    settings = LlmReasoningSettings(effort="none")
    assert settings.is_active() is False
    assert settings.openrouter_payload() is None


def test_reasoning_settings_openrouter_payload_effort_and_exclude() -> None:
    settings = LlmReasoningSettings(effort="medium", exclude=True)
    assert settings.openrouter_payload() == {"effort": "medium", "exclude": True}


def test_reasoning_settings_openrouter_payload_prefers_max_tokens() -> None:
    settings = LlmReasoningSettings(effort="high", max_tokens=8000, exclude=False)
    assert settings.openrouter_payload() == {"max_tokens": 8000, "exclude": False}


def test_reasoning_settings_anthropic_adaptive_effort() -> None:
    settings = LlmReasoningSettings(effort="high")
    kwargs = settings.anthropic_create_kwargs(max_output_tokens=16384)
    assert kwargs["thinking"] == {"type": "adaptive"}
    assert kwargs["output_config"] == {"effort": "high"}


def test_reasoning_settings_anthropic_budget_tokens() -> None:
    settings = LlmReasoningSettings(max_tokens=4096)
    kwargs = settings.anthropic_create_kwargs(max_output_tokens=16384)
    assert kwargs["thinking"] == {"type": "enabled", "budget_tokens": 4096}
    assert kwargs["max_tokens"] == 16384


def test_is_reasoning_parameter_rejection_detects_400_reasoning_errors() -> None:
    assert is_reasoning_parameter_rejection(
        status_code=400,
        message='Unknown parameter: "reasoning"',
    )
    assert not is_reasoning_parameter_rejection(
        status_code=401,
        message='Unknown parameter: "reasoning"',
    )


def test_settings_load_reasoning_from_env() -> None:
    settings = Settings(
        LLM_REASONING_EFFORT="low",
        LLM_REASONING_EXCLUDE="true",
    )
    reasoning = settings.resolved_llm_reasoning()
    assert reasoning.effort == "low"
    assert reasoning.exclude is True
    assert reasoning.openrouter_payload() == {"effort": "low", "exclude": True}


def test_settings_invalid_reasoning_effort_falls_back_to_unset() -> None:
    settings = Settings(LLM_REASONING_EFFORT="turbo")
    assert settings.resolved_llm_reasoning().is_active() is False


def test_resolve_max_output_tokens_adds_headroom_for_reasoning() -> None:
    reasoning = LlmReasoningSettings(effort="medium", exclude=True)
    assert (
        resolve_max_output_tokens(
            base=DEFAULT_LLM_MAX_OUTPUT_TOKENS,
            reasoning=reasoning,
            include_reasoning=True,
        )
        == 32_768
    )
    assert (
        resolve_max_output_tokens(
            base=DEFAULT_LLM_MAX_OUTPUT_TOKENS,
            reasoning=reasoning,
            include_reasoning=False,
        )
        == DEFAULT_LLM_MAX_OUTPUT_TOKENS
    )


def test_openrouter_client_attaches_reasoning_extra_body() -> None:
    mock_client = MagicMock()
    mock_message = MagicMock()
    mock_message.content = '{"screenCode":"class Demo {}","extractedWidgets":[]}'
    mock_choice = MagicMock()
    mock_choice.finish_reason = "stop"
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    client = OpenRouterLlmClient(
        api_key="test-key",
        model="google/gemini-3.5-flash",
        reasoning=LlmReasoningSettings(effort="medium", exclude=True),
    )
    client._client = mock_client

    client._request_generation('{"featureName":"demo"}', system_prompt=build_system_prompt())

    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["max_tokens"] == 32_768
    assert call_kwargs["extra_body"] == {
        "reasoning": {"effort": "medium", "exclude": True},
    }


def _openai_api_error(message: str, *, status_code: int) -> Exception:
    from openai import APIError as OpenAIAPIError

    exc = OpenAIAPIError(message, request=MagicMock(), body={"error": {"message": message}})
    exc.status_code = status_code
    return exc


def test_openrouter_client_falls_back_when_reasoning_is_rejected() -> None:
    mock_client = MagicMock()
    mock_message = MagicMock()
    mock_message.content = '{"screenCode":"class Demo {}","extractedWidgets":[]}'
    mock_choice = MagicMock()
    mock_choice.finish_reason = "stop"
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    reasoning_error = _openai_api_error('Unknown parameter: "reasoning"', status_code=400)
    mock_client.chat.completions.create.side_effect = [reasoning_error, mock_response]

    client = OpenRouterLlmClient(
        api_key="test-key",
        model="google/gemini-3.5-flash",
        reasoning=LlmReasoningSettings(effort="high"),
    )
    client._client = mock_client

    client._request_generation('{"featureName":"demo"}', system_prompt=build_system_prompt())

    assert mock_client.chat.completions.create.call_count == 2
    first_kwargs = mock_client.chat.completions.create.call_args_list[0].kwargs
    second_kwargs = mock_client.chat.completions.create.call_args_list[1].kwargs
    assert first_kwargs["extra_body"] == {"reasoning": {"effort": "high"}}
    assert "extra_body" not in second_kwargs
    assert client._reasoning_suppressed is True


def test_should_fallback_without_reasoning_on_transport_timeout() -> None:
    assert should_fallback_without_reasoning(
        status_code=None,
        message="OpenRouter request timed out (model=x): ConnectTimeout",
    )
    assert is_likely_transport_failure(status_code=None, message="ConnectTimeout")
    assert not should_fallback_without_reasoning(
        status_code=401,
        message="Invalid API key",
    )


def test_openrouter_client_falls_back_on_timeout_without_reasoning() -> None:
    mock_client = MagicMock()
    mock_message = MagicMock()
    mock_message.content = '{"screenCode":"class Demo {}","extractedWidgets":[]}'
    mock_choice = MagicMock()
    mock_choice.finish_reason = "stop"
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    timeout_error = APITimeoutError("request timed out")
    mock_client.chat.completions.create.side_effect = [timeout_error, mock_response]

    client = OpenRouterLlmClient(
        api_key="test-key",
        model="google/gemini-3-flash-preview",
        reasoning=LlmReasoningSettings(effort="medium", exclude=True),
    )
    client._client = mock_client

    client._request_generation('{"featureName":"demo"}', system_prompt=build_system_prompt())

    assert mock_client.chat.completions.create.call_count == 2
    assert "extra_body" not in mock_client.chat.completions.create.call_args_list[1].kwargs
    assert client._reasoning_suppressed is True


def test_openrouter_client_bumps_max_tokens_after_truncation() -> None:
    mock_client = MagicMock()
    mock_message = MagicMock()
    mock_message.content = '{"screenCode":"class Demo {}","extractedWidgets":[]}'
    truncated_choice = MagicMock()
    truncated_choice.finish_reason = "length"
    truncated_choice.message = mock_message
    truncated_response = MagicMock()
    truncated_response.choices = [truncated_choice]

    ok_choice = MagicMock()
    ok_choice.finish_reason = "stop"
    ok_choice.message = mock_message
    ok_response = MagicMock()
    ok_response.choices = [ok_choice]
    ok_response.usage = None

    mock_client.chat.completions.create.side_effect = [truncated_response, ok_response]

    client = OpenRouterLlmClient(
        api_key="test-key",
        model="google/gemini-3-flash-preview",
        reasoning=LlmReasoningSettings(effort="medium", exclude=True),
        max_retries=3,
    )
    client._client = mock_client

    client._run_with_retry(
        lambda: client._request_generation(
            '{"featureName":"demo"}',
            system_prompt=build_system_prompt(),
        )
    )

    assert mock_client.chat.completions.create.call_count == 2
    first_tokens = mock_client.chat.completions.create.call_args_list[0].kwargs["max_tokens"]
    second_tokens = mock_client.chat.completions.create.call_args_list[1].kwargs["max_tokens"]
    assert first_tokens == 32_768
    assert second_tokens == 65_536


def test_openrouter_client_does_not_fallback_on_unrelated_400() -> None:
    mock_client = MagicMock()
    api_error = _openai_api_error("Invalid json schema", status_code=400)
    mock_client.chat.completions.create.side_effect = api_error

    client = OpenRouterLlmClient(
        api_key="test-key",
        model="google/gemini-3.5-flash",
        reasoning=LlmReasoningSettings(effort="high"),
    )
    client._client = mock_client

    with pytest.raises(LlmError, match="Invalid json schema"):
        client._request_generation('{"featureName":"demo"}', system_prompt=build_system_prompt())

    assert mock_client.chat.completions.create.call_count == 1
