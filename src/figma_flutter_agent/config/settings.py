"""Main Settings class with environment variable overrides."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, cast

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from ruamel.yaml import YAML

from figma_flutter_agent.errors import FigmaFlutterError
from figma_flutter_agent.llm.capabilities import LlmProvider
from figma_flutter_agent.llm.clients import default_model_for_provider
from figma_flutter_agent.llm.reasoning import (
    DEFAULT_LLM_MAX_OUTPUT_TOKENS,
    LlmReasoningSettings,
    normalize_max_output_tokens,
    normalize_reasoning_effort,
    normalize_reasoning_max_tokens,
)

from .models import AgentYamlConfig
from .paths import resolve_agent_config_path

LlmProviderSetting = Literal[
    "anthropic",
    "openai",
    "openrouter",
    "google",
    "google_aistudio",
]

_LLM_PROVIDER_ALIASES: dict[str, LlmProvider] = {
    "google_aistudio": "google",
    "google_ai_studio": "google",
    "aistudio": "google",
    "gemini": "google",
}


class Settings(BaseSettings):
    """Runtime settings with environment variable overrides."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: Any,
        env_settings: Any,
        dotenv_settings: Any,
        file_secret_settings: Any,
    ) -> tuple[Any, ...]:
        """Skip ``.env`` during pytest so local developer keys do not affect unit tests."""
        import os

        sources: list[Any] = [init_settings, env_settings, file_secret_settings]
        if not os.getenv("PYTEST_CURRENT_TEST"):
            sources.insert(1, dotenv_settings)
        return tuple(sources)

    figma_access_token: SecretStr = Field(default=SecretStr(""), alias="FIGMA_ACCESS_TOKEN")
    anthropic_api_key: SecretStr = Field(default=SecretStr(""), alias="ANTHROPIC_API_KEY")
    openai_api_key: SecretStr = Field(default=SecretStr(""), alias="OPENAI_API_KEY")
    openrouter_api_key: SecretStr = Field(default=SecretStr(""), alias="OPENROUTER_API_KEY")
    google_api_key: SecretStr = Field(
        default=SecretStr(""),
        alias="GOOGLE_API_KEY",
        description="API key from Google AI Studio (https://aistudio.google.com/apikey).",
    )
    llm_provider: LlmProviderSetting = Field(default="anthropic", alias="LLM_PROVIDER")
    llm_generate_model: str = Field(default="", alias="LLM_GENERATE_MODEL")
    llm_generate_model_2: str = Field(default="", alias="LLM_GENERATE_MODEL_2")
    llm_generate_model_3: str = Field(default="", alias="LLM_GENERATE_MODEL_3")
    llm_repair_model: str = Field(default="", alias="LLM_REPAIR_MODEL")
    llm_refine_model: str = Field(default="", alias="LLM_REFINE_MODEL")
    llm_require_strict_json_schema: bool = Field(
        default=False,
        alias="LLM_REQUIRE_STRICT_JSON_SCHEMA",
        description="Prefer strict JSON schema LLM output when the provider supports it.",
    )
    llm_max_retries: int = Field(
        default=3,
        alias="LLM_MAX_RETRIES",
        ge=1,
        le=10,
        description="Maximum LLM API call attempts on transient failures.",
    )
    llm_temperature: float | None = Field(
        default=None,
        alias="LLM_TEMPERATURE",
        ge=0.0,
        le=2.0,
        description="LLM sampling temperature for generate; omitted when unset.",
    )
    llm_repair_temperature: float | None = Field(
        default=None,
        alias="LLM_REPAIR_TEMPERATURE",
        ge=0.0,
        le=2.0,
        description="LLM sampling temperature for analyze repair; omitted when unset.",
    )
    llm_top_p: float | None = Field(
        default=None,
        alias="LLM_TOP_P",
        ge=0.0,
        le=1.0,
        description="LLM nucleus sampling top_p; omitted when unset.",
    )
    llm_reasoning_effort: str | None = Field(
        default=None,
        alias="LLM_REASONING_EFFORT",
        description="Reasoning effort: none|minimal|low|medium|high|xhigh; omitted when unset.",
    )
    llm_reasoning_max_tokens: int | None = Field(
        default=None,
        alias="LLM_REASONING_MAX_TOKENS",
        ge=1,
        description="Reasoning token budget (Anthropic/Gemini 2.5 style); omitted when unset.",
    )
    llm_reasoning_exclude: bool | None = Field(
        default=None,
        alias="LLM_REASONING_EXCLUDE",
        description="When true, hide reasoning tokens from the response payload.",
    )
    llm_max_output_tokens: int = Field(
        default=DEFAULT_LLM_MAX_OUTPUT_TOKENS,
        alias="LLM_MAX_OUTPUT_TOKENS",
        ge=1024,
        description="Completion token budget per LLM call; auto-increased when reasoning is on.",
    )
    default_project_dir: Path = Field(
        default=Path("."),
        alias="FIGMA_FLUTTER_PROJECT_DIR",
        description=(
            "Flutter workspace root when --project-dir is omitted: parent directory "
            "containing one or more Flutter apps (each with pubspec.yaml), or a single "
            "app root. Active app is chosen in the interactive wizard (switch)."
        ),
    )
    flutter_sdk: str = Field(
        default="",
        alias="FIGMA_FLUTTER_SDK",
        description="Flutter SDK root when flutter is not on PATH (VS Code tasks on Windows).",
    )
    opencode_base_url: str = Field(
        default="http://127.0.0.1:4096",
        alias="OPENCODE_BASE_URL",
        description="OpenCode serve base URL for wizard debug.",
    )
    opencode_server_password: SecretStr = Field(
        default=SecretStr(""),
        alias="OPENCODE_SERVER_PASSWORD",
        description="Optional basic-auth password for opencode serve.",
    )
    figma_smoke_file_key: str = Field(default="", alias="FIGMA_SMOKE_FILE_KEY")
    figma_smoke_node_id: str = Field(default="", alias="FIGMA_SMOKE_NODE_ID")
    figma_default_url: str = Field(
        default="",
        alias="FIGMA_DEFAULT_URL",
        description="Optional default Figma file or frame URL for interactive prompts.",
    )
    posthog_api_key: SecretStr = Field(
        default=SecretStr(""),
        alias="POSTHOG_API_KEY",
        description="PostHog project API key; enables $ai_generation capture when set.",
    )
    posthog_host: str = Field(
        default="https://us.i.posthog.com",
        alias="POSTHOG_HOST",
        description="PostHog ingest host (US/EU).",
    )
    posthog_capture_max_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
        alias="POSTHOG_CAPTURE_MAX_ATTEMPTS",
        description="Retry count for background PostHog $ai_generation ingest.",
    )
    posthog_capture_timeout_sec: float = Field(
        default=8.0,
        gt=0,
        le=120,
        alias="POSTHOG_CAPTURE_TIMEOUT_SEC",
        description="Per-attempt HTTP timeout for PostHog LLM capture.",
    )
    posthog_capture_retry_base_sec: float = Field(
        default=0.75,
        gt=0,
        le=60,
        alias="POSTHOG_CAPTURE_RETRY_BASE_SEC",
        description="Base delay between PostHog capture retries (exponential backoff).",
    )
    loki_enabled: bool = Field(
        default=True,
        alias="LOKI_ENABLED",
        description="Ship logs to Loki when true and LOKI_URL is set.",
    )
    loki_url: str = Field(
        default="",
        alias="LOKI_URL",
        description="Grafana Loki base or push URL; enables remote log shipping when set.",
    )
    loki_user: str = Field(
        default="",
        alias="LOKI_USER",
        description="Grafana Cloud instance id for Loki basic auth (optional).",
    )
    loki_api_key: SecretStr = Field(
        default=SecretStr(""),
        alias="LOKI_API_KEY",
        description="Loki API token or password (Bearer when LOKI_USER is empty).",
    )
    loki_labels: str = Field(
        default="",
        alias="LOKI_LABELS",
        description="Extra Loki stream labels as comma-separated key=value pairs.",
    )
    loki_batch_size: int = Field(
        default=64,
        ge=1,
        le=1000,
        alias="LOKI_BATCH_SIZE",
        description="Max log lines per Loki push batch.",
    )
    loki_flush_interval_sec: float = Field(
        default=2.0,
        gt=0,
        le=60,
        alias="LOKI_FLUSH_INTERVAL_SEC",
        description="Max seconds to hold log lines before flushing to Loki.",
    )
    loki_push_max_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
        alias="LOKI_PUSH_MAX_ATTEMPTS",
        description="Retry count for Loki push batches.",
    )
    loki_push_timeout_sec: float = Field(
        default=8.0,
        gt=0,
        le=120,
        alias="LOKI_PUSH_TIMEOUT_SEC",
        description="Per-attempt HTTP timeout for Loki push.",
    )
    loki_push_retry_base_sec: float = Field(
        default=0.75,
        gt=0,
        le=60,
        alias="LOKI_PUSH_RETRY_BASE_SEC",
        description="Base delay between Loki push retries (exponential backoff).",
    )
    enable_safety_backup: bool = True
    figma_api_base_url: str = "https://api.figma.com"
    config_path: Path | None = None

    agent: AgentYamlConfig = Field(default_factory=AgentYamlConfig)

    @model_validator(mode="before")
    @classmethod
    def _coalesce_legacy_llm_model_env(cls, data: Any) -> Any:
        """Map deprecated ``LLM_MODEL`` to ``LLM_GENERATE_MODEL`` when unset."""
        if not isinstance(data, dict):
            return data
        merged = dict(data)
        if not merged.get("LLM_GENERATE_MODEL") and not merged.get("llm_generate_model"):
            legacy = merged.get("LLM_MODEL") or merged.get("llm_model")
            if legacy:
                merged["LLM_GENERATE_MODEL"] = legacy
        return merged

    @field_validator("llm_temperature", "llm_repair_temperature", "llm_top_p", mode="before")
    @classmethod
    def _empty_optional_float(cls, value: Any) -> Any:
        if value == "" or value is None:
            return None
        return value

    @field_validator("llm_reasoning_effort", mode="before")
    @classmethod
    def _normalize_llm_reasoning_effort(cls, value: Any) -> str | None:
        return normalize_reasoning_effort(value)

    @field_validator("llm_reasoning_max_tokens", mode="before")
    @classmethod
    def _normalize_llm_reasoning_max_tokens(cls, value: Any) -> int | None:
        return normalize_reasoning_max_tokens(value)

    @field_validator("llm_max_output_tokens", mode="before")
    @classmethod
    def _normalize_llm_max_output_tokens(cls, value: Any) -> int:
        parsed = normalize_max_output_tokens(value)
        if parsed is not None:
            return parsed
        if value == "" or value is None:
            return DEFAULT_LLM_MAX_OUTPUT_TOKENS
        return DEFAULT_LLM_MAX_OUTPUT_TOKENS

    @field_validator("llm_reasoning_exclude", mode="before")
    @classmethod
    def _normalize_llm_reasoning_exclude(cls, value: Any) -> bool | None:
        if value == "" or value is None:
            return None
        if isinstance(value, bool):
            return value
        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        return normalized not in {"0", "false", "no", "off"}

    @field_validator("llm_provider", mode="before")
    @classmethod
    def _normalize_llm_provider(cls, value: Any) -> str:
        if value is None:
            return "anthropic"
        normalized = str(value).strip().lower().replace("-", "_")
        return _LLM_PROVIDER_ALIASES.get(normalized, normalized)

    @field_validator("loki_enabled", mode="before")
    @classmethod
    def _normalize_loki_enabled(cls, value: Any) -> bool:
        if value == "" or value is None:
            return True
        if isinstance(value, bool):
            return value
        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        return normalized not in {"0", "false", "no", "off"}

    @field_validator("llm_require_strict_json_schema", mode="before")
    @classmethod
    def _normalize_llm_require_strict_json_schema(cls, value: Any) -> bool:
        if value == "" or value is None:
            return False
        if isinstance(value, bool):
            return value
        normalized = str(value).strip().lower()
        return normalized in {"1", "true", "yes", "on"}

    def resolved_llm_provider(self) -> LlmProvider:
        """Return the active LLM provider."""
        return cast(
            LlmProvider,
            _LLM_PROVIDER_ALIASES.get(self.llm_provider, self.llm_provider),
        )

    def resolved_llm_reasoning(self) -> LlmReasoningSettings:
        """Return normalized reasoning settings; invalid env values are dropped."""
        return LlmReasoningSettings(
            effort=self.llm_reasoning_effort,  # type: ignore[arg-type]
            max_tokens=self.llm_reasoning_max_tokens,
            exclude=self.llm_reasoning_exclude,
        )

    def _resolved_llm_model_from_env(self, env_model: str) -> str | None:
        if env_model:
            return env_model
        return None

    def resolved_llm_generate_model(self) -> str:
        """Return the model for primary screen codegen.

        Precedence: ``LLM_GENERATE_MODEL`` env → provider default.
        """
        resolved = self._resolved_llm_model_from_env(self.llm_generate_model)
        if resolved:
            return resolved
        return default_model_for_provider(self.resolved_llm_provider())

    def resolved_llm_compare_models(self) -> list[str]:
        """Return the three wizard compare models from env slots 1–3.

        Returns:
            Non-empty model ids for ``LLM_GENERATE_MODEL``,
            ``LLM_GENERATE_MODEL_2``, and ``LLM_GENERATE_MODEL_3``.

        Raises:
            LlmError: When any compare slot is unset.
        """
        from figma_flutter_agent.errors import LlmError

        slots = (
            ("LLM_GENERATE_MODEL", self.llm_generate_model),
            ("LLM_GENERATE_MODEL_2", self.llm_generate_model_2),
            ("LLM_GENERATE_MODEL_3", self.llm_generate_model_3),
        )
        models: list[str] = []
        missing: list[str] = []
        for env_name, raw in slots:
            resolved = self._resolved_llm_model_from_env(raw)
            if resolved:
                models.append(resolved)
            else:
                missing.append(env_name)
        if missing:
            joined = ", ".join(missing)
            raise LlmError(
                f"Wizard compare requires all three generate models; missing: {joined}"
            )
        return models

    def resolved_llm_repair_model(self) -> str:
        """Return the model for analyze repair passes.

        Precedence: ``LLM_REPAIR_MODEL`` env → ``resolved_llm_generate_model()``.
        """
        if self.llm_repair_model:
            return self.llm_repair_model
        return self.resolved_llm_generate_model()

    def resolved_llm_refine_model(self) -> str:
        """Return the model for visual refine passes.

        Precedence: ``LLM_REFINE_MODEL`` env → ``resolved_llm_generate_model()``.
        """
        if self.llm_refine_model:
            return self.llm_refine_model
        return self.resolved_llm_generate_model()

    @staticmethod
    def _model_slug_uses_gemini_35_flash(model: str) -> bool:
        normalized = model.strip().lower()
        return normalized.endswith("gemini-3.5-flash") or "/gemini-3.5-flash" in normalized

    def resolved_llm_generate_temperature(self) -> float | None:
        """Sampling temperature for primary codegen (provider default when None).

        Reasoning models (e.g. Gemini 3.5 Flash with thinking) are typically run at
        provider-recommended temperature (~1.0). Do not force a low default here.
        """
        return self.llm_temperature

    def resolved_llm_repair_temperature(self) -> float | None:
        """Sampling temperature for analyze repair (low by default for deterministic patches)."""
        if self.llm_repair_temperature is not None:
            return self.llm_repair_temperature
        if self._model_slug_uses_gemini_35_flash(self.resolved_llm_repair_model()):
            return 0.2
        return 0.2

    def resolved_llm_model(self) -> str:
        """Deprecated alias for ``resolved_llm_generate_model()``."""
        return self.resolved_llm_generate_model()

    def llm_api_key(self) -> str:
        """Return the API key for the active LLM provider."""
        keys: dict[LlmProviderSetting, SecretStr] = {
            "anthropic": self.anthropic_api_key,
            "openai": self.openai_api_key,
            "openrouter": self.openrouter_api_key,
            "google": self.google_api_key,
        }
        return keys[self.resolved_llm_provider()].get_secret_value()

    def figma_token(self) -> str:
        """Return the Figma access token."""
        return self.figma_access_token.get_secret_value()

    def llm_api_key_env_name(self) -> str:
        """Return the environment variable name for the active LLM provider key."""
        env_names: dict[LlmProviderSetting, str] = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "google": "GOOGLE_API_KEY",
        }
        return env_names[self.resolved_llm_provider()]

    def load_yaml_config(self, path: Path | None = None) -> None:
        """Merge YAML configuration from the agent repo into settings.

        Args:
            path: Optional explicit config path. When omitted, loads from the agent repo
                (``.ai-figma-flutter.yml``, then ``.ai-figma-flutter.yml.example``).
                Flutter project directories are never searched.
        """
        try:
            config_file = resolve_agent_config_path(path or self.config_path)
        except FigmaFlutterError:
            return
        yaml_loader = YAML(typ="safe")
        raw: dict[str, Any] = yaml_loader.load(config_file.read_text(encoding="utf-8")) or {}
        self.agent = AgentYamlConfig.model_validate(raw)
        self.config_path = config_file


def load_settings(config_path: Path | None = None) -> Settings:
    """Load settings from environment and agent-repo YAML config.

    Args:
        config_path: Optional YAML override (``--config``). Defaults to the agent repo
            ``.ai-figma-flutter.yml`` (or ``.example`` fallback).

    Returns:
        Fully initialized settings instance.
    """
    resolved = None
    if config_path is not None:
        resolved = resolve_agent_config_path(config_path)
    settings = Settings(config_path=resolved)
    settings.load_yaml_config(resolved)
    return settings
