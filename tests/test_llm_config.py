import pytest
from pydantic import SecretStr

from figma_flutter_agent.config import AgentYamlConfig, GenerationConfig, Settings
from figma_flutter_agent.errors import LlmError
from figma_flutter_agent.llm.client import create_llm_client, default_model_for_provider


def test_resolved_llm_generate_model_prefers_env_for_any_provider() -> None:
    settings = Settings(
        LLM_PROVIDER="anthropic",
        LLM_GENERATE_MODEL="claude-opus-4-20250514",
    )

    assert settings.resolved_llm_generate_model() == "claude-opus-4-20250514"


def test_resolved_llm_generate_model_accepts_legacy_llm_model_env() -> None:
    settings = Settings(
        LLM_PROVIDER="anthropic",
        LLM_MODEL="claude-opus-4-20250514",
    )

    assert settings.resolved_llm_generate_model() == "claude-opus-4-20250514"


def test_resolved_llm_generate_model_env_override_for_openrouter() -> None:
    settings = Settings(
        LLM_PROVIDER="openrouter",
        LLM_GENERATE_MODEL="anthropic/claude-sonnet-4",
    )

    assert settings.resolved_llm_generate_model() == "anthropic/claude-sonnet-4"


def test_resolved_llm_generate_model_falls_back_to_provider_default() -> None:
    settings_without_model = Settings(LLM_PROVIDER="openrouter")
    assert settings_without_model.resolved_llm_generate_model() == default_model_for_provider(
        "openrouter"
    )


def test_yaml_llm_model_section_is_ignored() -> None:
    settings = Settings(
        LLM_PROVIDER="openrouter",
        LLM_GENERATE_MODEL="google/gemini-3.5-flash",
    )
    settings.agent = AgentYamlConfig.model_validate(
        {"llm": {"model": "claude-sonnet-4-6"}, "generation": GenerationConfig()}
    )
    assert settings.resolved_llm_generate_model() == "google/gemini-3.5-flash"


def test_resolved_llm_repair_and_refine_models_fallback_to_generate() -> None:
    settings = Settings(
        LLM_PROVIDER="openrouter",
        LLM_GENERATE_MODEL="google/gemini-3.5-flash",
    )
    assert settings.resolved_llm_repair_model() == "google/gemini-3.5-flash"
    assert settings.resolved_llm_refine_model() == "google/gemini-3.5-flash"


def test_resolved_llm_repair_and_refine_models_use_dedicated_env() -> None:
    settings = Settings(
        LLM_PROVIDER="openrouter",
        LLM_GENERATE_MODEL="google/gemini-3.5-flash",
        LLM_REPAIR_MODEL="google/gemini-2.5-flash",
        LLM_REFINE_MODEL="google/gemini-2.5-flash-lite",
    )
    assert settings.resolved_llm_generate_model() == "google/gemini-3.5-flash"
    assert settings.resolved_llm_repair_model() == "google/gemini-2.5-flash"
    assert settings.resolved_llm_refine_model() == "google/gemini-2.5-flash-lite"


def test_llm_require_strict_json_schema_loads_from_env() -> None:
    settings = Settings(LLM_REQUIRE_STRICT_JSON_SCHEMA="true")
    assert settings.llm_require_strict_json_schema is True


def test_generation_yaml_ignores_legacy_require_strict_json_schema() -> None:
    settings = Settings()
    settings.load_yaml_config()
    settings.agent = AgentYamlConfig.model_validate(
        {
            "generation": {
                "require_strict_json_schema": True,
                "use_deterministic_screen": False,
            }
        }
    )
    assert settings.llm_require_strict_json_schema is False


def test_llm_api_key_selects_provider_key() -> None:
    settings = Settings(
        LLM_PROVIDER="openrouter",
        OPENROUTER_API_KEY=SecretStr("sk-or-v1-test"),
    )
    assert settings.llm_api_key() == "sk-or-v1-test"
    assert settings.llm_api_key_env_name() == "OPENROUTER_API_KEY"


def test_google_provider_uses_google_api_key_and_default_model() -> None:
    settings = Settings(
        LLM_PROVIDER="google",
        GOOGLE_API_KEY=SecretStr("google-test-key"),
    )
    assert settings.llm_api_key() == "google-test-key"
    assert settings.llm_api_key_env_name() == "GOOGLE_API_KEY"
    assert settings.resolved_llm_generate_model() == default_model_for_provider("google")


def test_create_llm_client_returns_google_client() -> None:
    client = create_llm_client(provider="google", api_key="test", model="gemini-2.0-flash")
    assert type(client).__name__ == "GoogleLlmClient"


def test_settings_repr_masks_api_keys() -> None:
    settings = Settings(
        ANTHROPIC_API_KEY=SecretStr("sk-ant-secret-value"),
        OPENAI_API_KEY=SecretStr("sk-openai-secret"),
    )
    rendered = repr(settings)
    assert "sk-ant-secret-value" not in rendered
    assert "sk-openai-secret" not in rendered


def test_create_llm_client_rejects_unknown_provider() -> None:
    with pytest.raises(LlmError, match="Unsupported LLM provider"):
        create_llm_client(provider="unknown", api_key="test", model="test")  # type: ignore[arg-type]


def test_settings_load_llm_sampling_from_env() -> None:
    settings = Settings(LLM_TEMPERATURE="0.2", LLM_TOP_P="0.9")
    assert settings.llm_temperature == 0.2
    assert settings.llm_top_p == 0.9


def test_settings_load_llm_max_retries_from_env() -> None:
    settings = Settings(LLM_MAX_RETRIES="5")
    assert settings.llm_max_retries == 5


def test_settings_treat_empty_llm_sampling_env_as_unset() -> None:
    settings = Settings(LLM_TEMPERATURE="", LLM_TOP_P="")
    assert settings.llm_temperature is None
    assert settings.llm_top_p is None
