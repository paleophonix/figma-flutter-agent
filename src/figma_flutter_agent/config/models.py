"""All Pydantic sub-config BaseModel classes for the agent configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from figma_flutter_agent.validation.geometry_metrics import GeometryTierThresholds

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from figma_flutter_agent.config.debug_pipeline import DebugPipelineConfig

AnalyzeScopeSetting = Literal["written_only", "all_planned", "project", "generated_only"]

GeometryPrecision = Literal["standard", "full"]

RoutingType = Literal["none", "go_router", "auto_route", "navigator2"]

StyleMetadataSource = Literal["rest_synthesis", "dev_mode_inspect", "hybrid"]

ResponsivePreviewMode = Literal["static", "responsive", "both"]


class ResponsiveConfig(BaseModel):
    """Responsive layout settings."""

    mode: ResponsivePreviewMode = Field(
        default="responsive",
        description=(
            "Wizard preview: static (fixed Figma artboard), responsive (wide adaptive "
            "preview), or both (static web-server + responsive Chrome; logs attach to "
            "responsive only)."
        ),
    )
    max_web_width: int = 1200
    adaptive_render: bool = Field(
        default=False,
        description=(
            "Deprecated for wizard launch sizing; responsive.mode now selects "
            "preview behavior. Retained for compatibility with older configs."
        ),
    )
    preview_width: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Fallback Chrome wizard preview width in logical pixels when no layout "
            "dump is available. Does not select responsive vs fixed preview mode."
        ),
    )
    preview_height: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Fallback Chrome wizard preview height in logical pixels when no layout "
            "dump is available. Must be set when preview_width is set."
        ),
    )
    macro_height_threshold_px: int = 900
    shell_safe_area: bool = False
    status_bar_inset_px: float = 44.0
    require_reflow: bool = Field(
        default=False,
        description=(
            "When true with responsive mode other than static, fail generation when "
            "layout tier is scaled/fixed instead of reflowed (LAW-RESPONSIVE-REQUIRE-REFLOW)."
        ),
    )

    @property
    def enabled(self) -> bool:
        """Whether codegen emits responsive reflow (``responsive`` or ``both``)."""
        return self.mode in ("responsive", "both")

    @model_validator(mode="before")
    @classmethod
    def _migrate_enabled_to_mode(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        payload = dict(data)
        if "enabled" in payload:
            legacy_enabled = payload.pop("enabled")
            if "mode" not in payload:
                payload["mode"] = "responsive" if legacy_enabled else "static"
        return payload

    @model_validator(mode="after")
    def _sync_static_preview_flags(self) -> ResponsiveConfig:
        if self.mode == "static" and self.adaptive_render:
            return self.model_copy(update={"adaptive_render": False})
        return self

    @model_validator(mode="after")
    def _validate_preview_size_pair(self) -> ResponsiveConfig:
        width_set = self.preview_width is not None
        height_set = self.preview_height is not None
        if width_set != height_set:
            msg = (
                "responsive.preview_width and responsive.preview_height must both "
                "be set or both omitted"
            )
            raise ValueError(msg)
        return self


class LayoutConfig(BaseModel):
    """Layout generation settings."""

    avoid_fixed_sizes: bool = True
    use_scaffold: bool = True
    app_bar_inset_px: float = 56.0
    snap_device_pixels: bool = False


class LayoutPassesSettings(BaseModel):
    """IR middle-end layout pass policy (EPIC 4)."""

    inject_root_scroll_host: bool = True
    scroll_extent_fallback_threshold_px: int | None = Field(
        default=None,
        description="Fallback scroll threshold when artboard height is unknown.",
    )


class AccessibilityConfig(BaseModel):
    """Accessibility analysis and automatic clean-tree fixes."""

    auto_fix: bool = True


class SemanticsSettings(BaseModel):
    """Deterministic semantic classifier thresholds."""

    enabled: bool = True
    report_only: bool = True
    llm_gray_zone_annotations: bool = False
    confidence_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    grey_zone_min: float = Field(default=0.5, ge=0.0, le=1.0)
    authoritative_classifier: bool = True
    strict_fidelity: bool = Field(
        default=False,
        description=(
            "When true, route native_unverified semantic nodes to geometric layout emit "
            "instead of themed styled primitives."
        ),
    )
    strict_l10n: bool = Field(
        default=False,
        description="When true, hard-fail baked tiers that block localization.",
    )
    strict_a11y: bool = Field(
        default=False,
        description="When true, hard-fail baked tiers on accessibility-critical text.",
    )


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
    strict_visible_vectors: bool = Field(
        default=False,
        description=(
            "When true, visible VECTOR nodes without drawable asset keys after "
            "the asset stage abort the pipeline with a named error."
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


class AiReusableConfig(BaseModel):
    """LLM-assisted reusable widget candidate detection (gated inference amplifier)."""

    model_config = ConfigDict(extra="ignore")

    enabled: bool = False
    mode: Literal["suggest", "enforce"] = "suggest"
    min_confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    max_candidates: int = Field(default=12, ge=1, le=48)
    require_static_gate: bool = True
    require_evidence: bool = True


class WidgetEnrichConfig(BaseModel):
    """LLM naming and constructor param labels for extracted cluster widgets."""

    model_config = ConfigDict(extra="ignore")

    enabled: bool = False
    cache_by_subtree_hash: bool = True


class WidgetExtractionConfig(BaseModel):
    """Widget extraction policy (annotation, dedup, inference)."""

    model_config = ConfigDict(extra="ignore")

    policy: Literal[
        "off",
        "dedup",
        "annotated",
        "balanced",
        "auto_reusable",
        "aggressive",
    ] = "balanced"
    min_count: int = Field(default=2, ge=1)
    annotation_prefixes: list[str] = Field(default_factory=lambda: ["@widget"])
    extract_figma_components_single_use: bool = True
    fail_on_unextracted_annotations: bool = True
    auto_reusable_min_score: float = Field(default=0.85, ge=0.0, le=1.0)
    parameterize_text: bool = False
    parameterize_assets: bool = False
    parameterize_variants: bool = False
    ai_reusable: AiReusableConfig = Field(default_factory=AiReusableConfig)
    enrich: WidgetEnrichConfig = Field(default_factory=WidgetEnrichConfig)


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
    widget_extraction: WidgetExtractionConfig = Field(default_factory=WidgetExtractionConfig)
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
    runtime_fail_renderflex_overflow: bool = Field(
        default=False,
        description=(
            "When true, fixture geometry gate fails if flutter test logs "
            "'RenderFlex overflowed' even when PNG capture succeeds."
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
    pixel_fidelity: bool = Field(
        default=False,
        description=(
            "When true, enable pixel fidelity profile overrides (static responsive, "
            "full geometry precision, preserve placement, hard pixel invariants)."
        ),
    )
    strict_visual_fidelity: bool = Field(
        default=False,
        description=(
            "Pixel/visual profile: route native_unverified nodes to geometric fallback "
            "and allow baked static text where text policy permits."
        ),
    )
    strict_product_fidelity: bool = Field(
        default=False,
        description=("Product profile: block baked tiers on localizable and a11y-critical text."),
    )
    geometry_precision: GeometryPrecision = Field(
        default="standard",
        description='Layout numeric precision: "standard" (1dp) or "full" (sub-pixel).',
    )
    preserve_placement: bool = Field(
        default=False,
        description=(
            "When true, skip stack/viewport placement clamps that mutate Figma coordinates."
        ),
    )
    promote_soft_pixel_invariants: bool = Field(
        default=False,
        description=(
            "When true, promote T1/T2/T3 geometry invariant violations from soft to hard."
        ),
    )
    suppress_archetype_compensation: bool = Field(
        default=False,
        description=(
            "When true, skip archetype-tier reconcile passes and layout archetype "
            "fast-path emitters (pixel fidelity / migration)."
        ),
    )
    archetype_reconcile: bool = Field(
        default=False,
        description=(
            "When true, run legacy archetype reconcile passes during normalize. "
            "Default false after Wave F; enable only for transitional corpus."
        ),
    )
    render_profile: Literal["semantic_app", "visual_pixel", "hybrid_review"] = Field(
        default="semantic_app",
        description="High-level emit path: semantic app UX vs visual pixel fork.",
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
    debug_capture: bool = Field(
        default=False,
        description=(
            "After generate, capture Flutter render and diff under .debug/capture/ "
            "(Figma gold stays in .debug/reference/figma/)."
        ),
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
    default_capture_mode: Literal["preview", "oracle"] = Field(
        default="preview",
        description=(
            "Default wizard/dev capture mode: preview writes a Flutter web PNG (chrome parity) "
            "without Figma diff; oracle adds flutter_render + diff heatmap."
        ),
    )
    flutter_device_id: str | None = Field(
        default=None,
        description=(
            "flutter run -d target for wizard launch/preview (e.g. chrome, windows). "
            "Omit or set to auto to prefer Chrome web when listed; set default to let Flutter choose."
        ),
    )
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
    strict_emit_contracts: bool = Field(
        default=False,
        description=(
            "When true with strict spec23, fail on FID-26 emit contract gaps "
            "(layer blur, strut, bottom pin, opacity wrapper). Signoff/CI only."
        ),
    )
    emit_parse_gate: bool = Field(
        default=False,
        description=(
            "Before llm_repair/write, syntax-check planned files in a temp project "
            "(dart format batch on Unix; dart analyze on Windows). "
            "Fail-fast when emitter output is not parseable (IR-first emit safety)."
        ),
    )
    fail_on_render_errors: bool = Field(
        default=False,
        description=(
            "When true, wizard ``flutter run`` preview fails if render/layout errors "
            "(for example RenderFlex overflow) are captured in ``last.log``."
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
    layout_passes: LayoutPassesSettings = Field(default_factory=LayoutPassesSettings)
    accessibility: AccessibilityConfig = Field(default_factory=AccessibilityConfig)
    semantics: SemanticsSettings = Field(default_factory=SemanticsSettings)
    quality: QualityConfig = Field(default_factory=QualityConfig)
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    state_management: StateManagementConfig = Field(default_factory=StateManagementConfig)
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
    debug_pipeline: DebugPipelineConfig = Field(default_factory=DebugPipelineConfig)

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
