"""Application configuration loaded from YAML and environment variables."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from figma_flutter_agent.validation.geometry_metrics import GeometryTierThresholds

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict
from ruamel.yaml import YAML

from figma_flutter_agent.errors import FigmaFlutterError
from figma_flutter_agent.llm.capabilities import LlmProvider
from figma_flutter_agent.llm.clients.core import default_model_for_provider
from figma_flutter_agent.llm.reasoning import (
    DEFAULT_LLM_MAX_OUTPUT_TOKENS,
    LlmReasoningSettings,
    normalize_max_output_tokens,
    normalize_reasoning_effort,
    normalize_reasoning_max_tokens,
)

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


def agent_repo_root() -> Path:
    """Return the ``figma-flutter-agent`` repository root directory."""
    return Path(__file__).resolve().parents[2]


def resolve_agent_config_path(explicit: Path | None = None) -> Path:
    """Return the canonical agent YAML config path (agent repo, not the Flutter project).

    Precedence when ``explicit`` is omitted:
        ``<agent_repo>/.ai-figma-flutter.yml`` → ``<agent_repo>/.ai-figma-flutter.yml.example``

    Args:
        explicit: Optional override (for example ``--config`` on the CLI).

    Returns:
        Resolved config file path.

    Raises:
        FigmaFlutterError: When no config file exists.
    """
    if explicit is not None:
        resolved = explicit.expanduser().resolve()
        if not resolved.is_file():
            raise FigmaFlutterError(f"Config file not found: {resolved}")
        return resolved

    root = agent_repo_root()
    local = root / ".ai-figma-flutter.yml"
    if local.is_file():
        return local
    example = root / ".ai-figma-flutter.yml.example"
    if example.is_file():
        return example
    raise FigmaFlutterError(
        "Missing agent config. Copy .ai-figma-flutter.yml.example to "
        ".ai-figma-flutter.yml in the figma-flutter-agent repo root."
    )


AnalyzeScopeSetting = Literal[
    "written_only", "all_planned", "project", "generated_only"
]


class ResponsiveConfig(BaseModel):
    """Responsive layout settings."""

    enabled: bool = True
    max_web_width: int = 1200
    shell_safe_area: bool = False
    status_bar_inset_px: float = 44.0


class LayoutConfig(BaseModel):
    """Layout generation settings."""

    avoid_fixed_sizes: bool = True
    use_scaffold: bool = True
    app_bar_inset_px: float = 56.0
    snap_device_pixels: bool = False


class AccessibilityConfig(BaseModel):
    """Accessibility analysis and automatic clean-tree fixes."""

    auto_fix: bool = True


class AssetsConfig(BaseModel):
    """Asset export settings."""

    svg: bool = True
    png_scales: list[int] = Field(default_factory=lambda: [1, 2, 3])
    webp: bool = False
    illustrations: bool = True
    optimize: bool = True
    images_batch_delay_sec: float = Field(default=1.0, ge=0.0)
    strict_render_boundary: bool = Field(
        default=False,
        description=(
            "When true, unresolved render-boundary SVG paths fail the pipeline "
            "instead of only emitting a warning."
        ),
    )


class FontsConfig(BaseModel):
    """Bundled font export settings for pixel-perfect typography."""

    enabled: bool = True
    download_fonts: bool = False
    skip_system_fallback: bool = True
    cache_enabled: bool = True


class FlutterConfig(BaseModel):
    """Flutter project architecture settings."""

    architecture: Literal["feature_first", "layer_first"] = "feature_first"


class StateManagementConfig(BaseModel):
    """State management backend selection."""

    type: Literal["none", "riverpod", "bloc", "provider"] = "none"


class UxConfig(BaseModel):
    """AI UX heuristics and optional report export (spec §21.4 / §22)."""

    suggestions: bool = True
    write_report: bool = True
    design_coverage: bool = Field(
        default=False,
        description="Write design coverage JSON (interactive nodes vs ValueKey/custom-code).",
    )


class AnimationConfig(BaseModel):
    """Prototype transition manifest export (spec §21.2)."""

    write_manifest: bool = True


class ThemeConfig(BaseModel):
    """Theme generation settings."""

    variant: Literal["material_3", "cupertino"] = "material_3"
    generate: bool = True


class NamingConfig(BaseModel):
    """Naming conventions for generated artifacts."""

    widget_suffix: str = "Widget"
    feature_name: Literal["auto"] | str = "auto"


RoutingType = Literal["none", "go_router", "auto_route", "navigator2"]


class GenerationConfig(BaseModel):
    """Code generation mode settings (LLM usage policy — not model/provider env)."""

    model_config = ConfigDict(extra="ignore")

    use_screen_ir: bool = True
    require_screen_ir: bool = Field(
        default=True,
        description="Reject LLM screenCode and Dart repair patches on the screen body; screenIr is the only generation contract.",
    )
    enforce_cluster_widgets: bool = True
    cluster_min_count: int = 2
    true_subtree_pruning: bool = True
    use_package_imports: bool = True
    allow_destination_stubs: bool = False
    regen_llm_on_token_change: bool = False
    llm_figma_reference_image: bool = True
    llm_repair_after_analyze: bool = True
    llm_repair_max_attempts: int = Field(default=4, ge=1, le=5)
    llm_repair_include_figma_png: bool = False
    llm_repair_cpi_supervisor: bool = True
    llm_repair_prompt_escalation: bool = True
    llm_repair_syntax_stall_limit: int = Field(
        default=2,
        ge=1,
        le=5,
        description="Stop repair when syntax/format error count fails to decrease for this many consecutive repair rounds",
    )
    llm_repair_widgets_first: bool = True
    llm_visual_refine: bool = True
    llm_visual_refine_max_attempts: int = Field(default=2, ge=1, le=5)
    llm_visual_refine_threshold: float = Field(default=0.005, ge=0.0, le=1.0)
    llm_visual_refine_capture_golden: bool = Field(
        default=False,
        description=(
            "When true, visual refine uses flutter test --update-goldens (slow, writes test/goldens/). "
            "When false, a lightweight capture test writes a PNG only (recommended)."
        ),
    )
    golden_capture_timeout_sec: float = Field(default=300.0, ge=120.0, le=1800.0)
    text_coordinate_tolerance: int = Field(default=3, ge=0)
    runtime_geometry_gate: bool = Field(
        default=True,
        description=(
            "After analyze passes, compare golden figma_keys.json bounds to Figma "
            "stackPlacement; failed IoU triggers analyze repair with geometry feedback."
        ),
    )
    runtime_geometry_min_iou: float = Field(default=0.95, ge=0.0, le=1.0)
    runtime_geometry_use_tier_thresholds: bool = Field(
        default=True,
        description=(
            "When true, apply hierarchical GIoU thresholds (canvas/structural/"
            "component/leaf). When false, use runtime_geometry_min_iou for every node."
        ),
    )
    runtime_geometry_tier_canvas: float = Field(default=0.99, ge=0.0, le=1.0)
    runtime_geometry_tier_structural: float = Field(default=0.95, ge=0.0, le=1.0)
    runtime_geometry_tier_component: float = Field(default=0.90, ge=0.0, le=1.0)
    runtime_geometry_tier_leaf: float = Field(default=0.82, ge=0.0, le=1.0)
    runtime_geometry_capture_if_missing: bool = Field(
        default=False,
        description=(
            "When figma_keys.json is absent under the Flutter project, run golden capture "
            "before the geometry gate (slow; prefer a prior golden test run)."
        ),
    )
    apply_render_safety_guards: bool = Field(
        default=True,
        description=(
            "When true, apply touch-target, scroll, viewport, and flex guards to the clean "
            "tree before deterministic layout emit (path-agnostic via identity ScreenIr)."
        ),
    )
    validate_render_safety: bool = Field(
        default=True,
        description=(
            "When true, fail generation when stack ghost occlusion would block interactive "
            "controls after guards (deterministic path)."
        ),
    )
    use_geometry_planner: bool = Field(
        default=True,
        description=(
            "When true, run geometry planning pass (world cascade, layout slots, T1–T5 "
            "invariants) before emit."
        ),
    )
    strict_geometry_invariants: bool = Field(
        default=False,
        description=(
            "When true, treat inv_ast_coverage as HARD and apply production fail-closed "
            "geometry gates (enabled by apply_production_profile)."
        ),
    )

    def geometry_tier_thresholds(self) -> GeometryTierThresholds:
        from figma_flutter_agent.validation.geometry_metrics import (
            GeometryTierThresholds,
        )

        return GeometryTierThresholds(
            canvas=self.runtime_geometry_tier_canvas,
            structural=self.runtime_geometry_tier_structural,
            component=self.runtime_geometry_tier_component,
            leaf=self.runtime_geometry_tier_leaf,
        )

    @model_validator(mode="after")
    def _validate_screen_ir_policy(self) -> GenerationConfig:
        self.use_screen_ir = True
        self.require_screen_ir = True
        return self


class RoutingConfig(BaseModel):
    """Navigation generation settings."""

    type: RoutingType = "none"
    generate_destinations: bool = True

    def is_enabled(self) -> bool:
        """Return True when any routing backend is active."""
        return self.type != "none"


# ---------------------------------------------------------------------------
# Figma source / Dev Mode config (Phase 1)
# ---------------------------------------------------------------------------

StyleMetadataSource = Literal["rest_synthesis", "dev_mode_inspect", "hybrid"]


class StyleMetadataConfig(BaseModel):
    """Controls which source is used for CSS-like style metadata (§5.1)."""

    model_config = ConfigDict(extra="forbid")

    source: StyleMetadataSource = Field(
        default="rest_synthesis",
        description=(
            "rest_synthesis — synthesise CSS from REST nodes + Styles API (default, §5.1).\n"
            "dev_mode_inspect — use an offline CSS dump produced by the helper plugin.\n"
            "hybrid — REST synthesis base, enriched by plugin dump where available."
        ),
    )


class DevResourcesConfig(BaseModel):
    """Settings for the experimental Figma dev_resources fetch hook."""

    model_config = ConfigDict(extra="forbid")

    fetch_on_sync: bool = Field(
        default=False,
        description=(
            "When true (and dev_mode.enabled), attempt to call GET /dev_resources "
            "during the fetch stage.  Currently a stub — the endpoint requires an "
            "Enterprise Dev Mode seat and returns 403 on Personal/Pro plans."
        ),
    )


class InspectCssConfig(BaseModel):
    """Settings for the offline CSS-inspect dump integration."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["off", "plugin_dump"] = Field(
        default="off",
        description=(
            "off — no CSS dump used (default).\n"
            "plugin_dump — load a JSON dump (v1 format) produced by the "
            "figma-css-inspect helper in tools/figma_css_inspect/."
        ),
    )
    dump_path: str | None = Field(
        default=None,
        description=(
            "Path to the CSS dump file (relative to the agent repo root, or absolute). "
            "Required when mode == plugin_dump."
        ),
    )

    @model_validator(mode="after")
    def _validate_plugin_dump(self) -> InspectCssConfig:
        if self.mode == "plugin_dump" and self.dump_path is None:
            msg = "figma.dev_mode.inspect_css.dump_path is required when mode == plugin_dump"
            raise ValueError(msg)
        return self


class DevModeConfig(BaseModel):
    """Figma Dev Mode integration settings (Phase 1 scaffold)."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(
        default=False,
        description="Master switch for Dev Mode integration features.",
    )
    dev_resources: DevResourcesConfig = Field(default_factory=DevResourcesConfig)
    inspect_css: InspectCssConfig = Field(default_factory=InspectCssConfig)


class DevToolsConfig(BaseModel):
    """Optional developer-facing generated artifacts."""

    model_config = ConfigDict(extra="forbid")

    design_gallery: bool = Field(
        default=False,
        description="Emit lib/dev/design_gallery_screen.dart from DesignTokens.",
    )


class FigmaConfig(BaseModel):
    """Figma API integration and style source settings."""

    model_config = ConfigDict(extra="forbid")

    style_metadata: StyleMetadataConfig = Field(default_factory=StyleMetadataConfig)
    dev_mode: DevModeConfig = Field(default_factory=DevModeConfig)

    @model_validator(mode="after")
    def _validate_dev_mode_source_consistency(self) -> FigmaConfig:
        source = self.style_metadata.source
        dev_enabled = self.dev_mode.enabled
        if source in ("dev_mode_inspect", "hybrid") and not dev_enabled:
            msg = f"figma.style_metadata.source={source!r} requires figma.dev_mode.enabled: true"
            raise ValueError(msg)
        return self


class SyncConfig(BaseModel):
    """Incremental sync settings."""

    enabled: bool = True
    fail_on_corrupt_snapshot: bool = False


class DarkModeConfig(BaseModel):
    """Dark theme generation settings."""

    enabled: bool = False


class QualityConfig(BaseModel):
    """Optional hard gates aligned with spec §9 and §7.9."""

    enforce_spec9_gates: bool = False
    max_layout_depth: int = 8
    strict_accessibility_labels: bool = False
    strict_contrast: bool = False
    fail_duplicate_clusters: bool = False


class RuntimeConfig(BaseModel):
    """Host vs Docker runtime for golden capture and AST tooling."""

    model_config = ConfigDict(extra="forbid")

    golden_capture: Literal["auto", "docker", "host"] = "auto"
    use_ast_sidecar: bool = True
    unified_canonicalizer: bool = Field(
        default=True,
        description=(
            "When true, run normalize_clean_tree once in the planner before emit "
            "(layout reconcile + optional render-safety guards) and skip duplicate "
            "passes in layout_renderer."
        ),
    )
    de_archetype_pass: bool = Field(
        default=False,
        description=(
            "When true, skip layout archetype fast-path renderers and use generic "
            "structural emitters only (migration aid for WP-F)."
        ),
    )
    cleanup_stale_processes_on_start: bool = True
    quiet_expected_warnings: bool = Field(
        default=True,
        description=(
            "When true, expected optional-path messages (missing CSS dump in hybrid/rest mode, "
            "cached IR offline, deterministic layout wrapper fallback) log at info/debug and are "
            "omitted from PipelineResult.warnings. Actionable UX/codegen hints still respect "
            "ux.suggestions and quality gates."
        ),
    )


class ValidationConfig(BaseModel):
    """Optional visual validation settings."""

    export_figma_reference: bool = False
    generate_golden_test: bool = False
    generate_typography_specimen_test: bool = False
    reference_scale: float = 2.0
    pixel_diff_threshold: float = 0.05
    require_dart_sdk: bool = False
    spec23_dart_analyze: bool = False
    emit_parse_gate: bool = Field(
        default=False,
        description=(
            "Before llm_repair/write, syntax-check planned files in a temp project "
            "(dart format batch on Unix; dart analyze on Windows). "
            "Fail-fast when emitter output is not parseable (IR-first emit safety)."
        ),
    )
    strict_preservation: bool = False
    analyze_scope: AnalyzeScopeSetting = "generated_only"

    @field_validator("analyze_scope", mode="before")
    @classmethod
    def _normalize_analyze_scope(cls, value: object) -> str:
        if value == "generated_only":
            return "all_planned"
        if value not in ("written_only", "all_planned", "project"):
            msg = "analyze_scope must be written_only, all_planned, or project"
            raise ValueError(msg)
        return str(value)


class AgentYamlConfig(BaseModel):
    """Pipeline and codegen policy loaded from ``.ai-figma-flutter.yml`` (not LLM env)."""

    model_config = ConfigDict(extra="ignore")

    flutter: FlutterConfig = Field(default_factory=FlutterConfig)
    theme: ThemeConfig = Field(default_factory=ThemeConfig)
    dark_mode: DarkModeConfig = Field(default_factory=DarkModeConfig)
    validation: ValidationConfig = Field(default_factory=ValidationConfig)
    responsive: ResponsiveConfig = Field(default_factory=ResponsiveConfig)
    layout: LayoutConfig = Field(default_factory=LayoutConfig)
    accessibility: AccessibilityConfig = Field(default_factory=AccessibilityConfig)
    quality: QualityConfig = Field(default_factory=QualityConfig)
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    state_management: StateManagementConfig = Field(
        default_factory=StateManagementConfig
    )
    ux: UxConfig = Field(default_factory=UxConfig)
    animations: AnimationConfig = Field(default_factory=AnimationConfig)
    assets: AssetsConfig = Field(default_factory=AssetsConfig)
    fonts: FontsConfig = Field(default_factory=FontsConfig)
    naming: NamingConfig = Field(default_factory=NamingConfig)
    routing: RoutingConfig = Field(default_factory=RoutingConfig)
    sync: SyncConfig = Field(default_factory=SyncConfig)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    figma: FigmaConfig = Field(default_factory=FigmaConfig)
    dev: DevToolsConfig = Field(default_factory=DevToolsConfig)

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_theme(cls, data: Any) -> Any:
        if isinstance(data, dict) and isinstance(data.get("theme"), str):
            data = dict(data)
            data["theme"] = {"variant": data["theme"], "generate": True}
        return data

    @field_validator("theme", mode="before")
    @classmethod
    def _coerce_theme(cls, value: Any) -> Any:
        if isinstance(value, str):
            return {"variant": value, "generate": True}
        return value

    @model_validator(mode="after")
    def _apply_ir_first_emit_policy(self) -> AgentYamlConfig:
        if not self.generation.require_screen_ir:
            return self
        if not self.generation.use_screen_ir:
            self.generation.use_screen_ir = True
        if not self.validation.emit_parse_gate:
            self.validation.emit_parse_gate = True
        return self


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

    figma_access_token: SecretStr = Field(
        default=SecretStr(""), alias="FIGMA_ACCESS_TOKEN"
    )
    anthropic_api_key: SecretStr = Field(
        default=SecretStr(""), alias="ANTHROPIC_API_KEY"
    )
    openai_api_key: SecretStr = Field(default=SecretStr(""), alias="OPENAI_API_KEY")
    openrouter_api_key: SecretStr = Field(
        default=SecretStr(""), alias="OPENROUTER_API_KEY"
    )
    google_api_key: SecretStr = Field(
        default=SecretStr(""),
        alias="GOOGLE_API_KEY",
        description="API key from Google AI Studio (https://aistudio.google.com/apikey).",
    )
    llm_provider: LlmProviderSetting = Field(default="anthropic", alias="LLM_PROVIDER")
    llm_generate_model: str = Field(default="", alias="LLM_GENERATE_MODEL")
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
        if not merged.get("LLM_GENERATE_MODEL") and not merged.get(
            "llm_generate_model"
        ):
            legacy = merged.get("LLM_MODEL") or merged.get("llm_model")
            if legacy:
                merged["LLM_GENERATE_MODEL"] = legacy
        return merged

    @field_validator(
        "llm_temperature", "llm_repair_temperature", "llm_top_p", mode="before"
    )
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
        if normalized in {"0", "false", "no", "off"}:
            return False
        return None

    @field_validator("llm_provider", mode="before")
    @classmethod
    def _normalize_llm_provider(cls, value: Any) -> str:
        if value is None:
            return "anthropic"
        normalized = str(value).strip().lower().replace("-", "_")
        return _LLM_PROVIDER_ALIASES.get(normalized, normalized)

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
        return self.llm_provider

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
        return (
            normalized.endswith("gemini-3.5-flash") or "/gemini-3.5-flash" in normalized
        )

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
        raw: dict[str, Any] = (
            yaml_loader.load(config_file.read_text(encoding="utf-8")) or {}
        )
        self.agent = AgentYamlConfig.model_validate(raw)
        self.config_path = config_file


def apply_signoff_profile(settings: Settings) -> Settings:
    """Apply CI/demo-signoff gates (spec §23) without full production generate profile."""
    agent = settings.agent
    return settings.model_copy(
        update={
            "agent": agent.model_copy(
                update={
                    "quality": agent.quality.model_copy(
                        update={
                            "enforce_spec9_gates": True,
                            "strict_accessibility_labels": True,
                            "fail_duplicate_clusters": True,
                        }
                    ),
                    "validation": agent.validation.model_copy(
                        update={
                            "require_dart_sdk": True,
                            "spec23_dart_analyze": True,
                            "strict_preservation": True,
                        }
                    ),
                }
            )
        }
    )


def apply_interactive_preview_profile(settings: Settings) -> Settings:
    """Fast wizard preview profile for ``run`` / ``launch`` (Chrome manual review).

    Visual refine stays enabled when configured in ``.ai-figma-flutter.yml``; only
    documents that interactive launch does not block refine by default.
    """
    return settings


def apply_refine_ready_profile(settings: Settings) -> Settings:
    """Enable IoU-first visual refine after baseline render quality is acceptable."""
    agent = settings.agent
    return settings.model_copy(
        update={
            "agent": agent.model_copy(
                update={
                    "generation": agent.generation.model_copy(
                        update={
                            "llm_visual_refine": True,
                            "llm_visual_refine_capture_golden": False,
                            "runtime_geometry_gate": True,
                            "runtime_geometry_use_tier_thresholds": True,
                            "llm_visual_refine_threshold": 0.05,
                        }
                    ),
                }
            )
        }
    )


def apply_showcase_profile(settings: Settings) -> Settings:
    """Enable optional spec §21–§22 features for demos and reviewer walkthroughs."""
    agent = settings.agent
    return settings.model_copy(
        update={
            "agent": agent.model_copy(
                update={
                    "state_management": agent.state_management.model_copy(
                        update={"type": "riverpod"}
                    ),
                    "dark_mode": agent.dark_mode.model_copy(update={"enabled": True}),
                    "ux": agent.ux.model_copy(
                        update={"suggestions": True, "write_report": True}
                    ),
                    "animations": agent.animations.model_copy(
                        update={"write_manifest": True}
                    ),
                    "routing": agent.routing.model_copy(
                        update={"type": "go_router", "generate_destinations": True}
                    ),
                }
            )
        }
    )


def apply_visual_qa_profile(settings: Settings) -> Settings:
    """Enable visual QA outputs (reference PNG, golden tests, dark theme)."""
    agent = settings.agent
    return settings.model_copy(
        update={
            "agent": agent.model_copy(
                update={
                    "dark_mode": agent.dark_mode.model_copy(update={"enabled": True}),
                    "validation": agent.validation.model_copy(
                        update={
                            "export_figma_reference": True,
                            "generate_golden_test": True,
                            "generate_typography_specimen_test": True,
                            "reference_scale": 2.0,
                            "pixel_diff_threshold": 0.05,
                        }
                    ),
                }
            )
        }
    )


def apply_production_profile(settings: Settings) -> Settings:
    """Apply strict quality and validation gates for production / CI (spec §9, §23).

    Enables fail-fast LLM-IR behavior.

    ``strict_contrast`` is evaluated on the parse tree **before** ``accessibility.auto_fix``.
    Production sets ``auto_fix: false`` so WCAG failures are not silently repaired before the gate.
    """
    agent = settings.agent
    return settings.model_copy(
        update={
            "llm_require_strict_json_schema": True,
            "agent": agent.model_copy(
                update={
                    "accessibility": agent.accessibility.model_copy(
                        update={"auto_fix": False}
                    ),
                    "quality": agent.quality.model_copy(
                        update={
                            "enforce_spec9_gates": True,
                            "strict_accessibility_labels": True,
                            "strict_contrast": True,
                            "fail_duplicate_clusters": True,
                        }
                    ),
                    "validation": agent.validation.model_copy(
                        update={
                            "require_dart_sdk": True,
                            "spec23_dart_analyze": True,
                            "strict_preservation": True,
                            "analyze_scope": "all_planned",
                        }
                    ),
                    "generation": agent.generation.model_copy(
                        update={
                            "regen_llm_on_token_change": True,
                            "strict_geometry_invariants": True,
                        }
                    ),
                    "responsive": agent.responsive.model_copy(update={"enabled": True}),
                    "layout": agent.layout.model_copy(
                        update={"avoid_fixed_sizes": True}
                    ),
                    "sync": agent.sync.model_copy(
                        update={"enabled": True, "fail_on_corrupt_snapshot": True}
                    ),
                    "assets": agent.assets.model_copy(
                        update={"strict_render_boundary": True}
                    ),
                }
            ),
        }
    )


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
