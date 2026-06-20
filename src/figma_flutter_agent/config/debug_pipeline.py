"""OpenCode repair pipeline model policy (``.ai-figma-flutter.yml`` → ``debug_pipeline``)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from figma_flutter_agent.llm.reasoning import (
    LlmReasoningEffort,
    LlmReasoningSettings,
    normalize_reasoning_effort,
)

DebugPipelineStep = Literal[
    "recognise",
    "inspect",
    "diagnose",
    "plan",
    "repair",
    "fix",
    "review",
    "summarize",
]

ENSEMBLE_STEPS: frozenset[DebugPipelineStep] = frozenset(
    {"recognise", "diagnose", "review"},
)

FUSION_OUTER_MODEL = "openrouter/fusion"
FUSION_JUDGE_MODEL = "deepseek/deepseek-v4-pro"

PANEL_CORE: tuple[str, ...] = (
    "moonshotai/kimi-k2.7-code",
    "minimax/minimax-m3",
    "xiaomi/mimo-v2.5-pro",
    "deepseek/deepseek-v4-pro",
)

QWEN_VL_MODEL = "qwen/qwen3-vl-235b-a22b-thinking"
QWEN_MAX_MODEL = "qwen/qwen3.7-max"

DEFAULT_RECOGNISE_PANEL: tuple[str, ...] = (QWEN_VL_MODEL, *PANEL_CORE)
DEFAULT_DIAGNOSE_PANEL: tuple[str, ...] = (QWEN_MAX_MODEL, *PANEL_CORE)
DEFAULT_REVIEW_PANEL: tuple[str, ...] = (QWEN_VL_MODEL, *PANEL_CORE)

DEFAULT_SINGLE_MODEL = FUSION_JUDGE_MODEL


class DebugPipelineEnsembleConfig(BaseModel):
    """When enabled, recognise / diagnose / review use OpenRouter Fusion panels."""

    model_config = ConfigDict(extra="ignore")

    enabled: bool = True
    panel_size: int = Field(default=5, ge=1, le=8)


class DebugPipelineOpenRouterConfig(BaseModel):
    """OpenRouter Fusion outer alias and judge model."""

    model_config = ConfigDict(extra="ignore")

    fusion_model: str = FUSION_OUTER_MODEL
    judge_model: str = FUSION_JUDGE_MODEL


class DebugPipelinePanelsConfig(BaseModel):
    """Per-step Fusion ``analysis_models`` (1–8 slugs each)."""

    model_config = ConfigDict(extra="ignore")

    recognise: tuple[str, ...] = Field(default_factory=lambda: DEFAULT_RECOGNISE_PANEL)
    diagnose: tuple[str, ...] = Field(default_factory=lambda: DEFAULT_DIAGNOSE_PANEL)
    review: tuple[str, ...] = Field(default_factory=lambda: DEFAULT_REVIEW_PANEL)


class DebugPipelineModelsConfig(BaseModel):
    """Direct slug for every ×1 step (and ensemble-off fallback on recognise/diagnose/review)."""

    model_config = ConfigDict(extra="ignore")

    single: str = DEFAULT_SINGLE_MODEL


class DebugPipelineLoopsConfig(BaseModel):
    """Orchestrator loop budgets."""

    model_config = ConfigDict(extra="ignore")

    max_fix_attempts: int = Field(default=2, ge=0, le=16)
    max_repair_retries_per_plan: int = Field(default=2, ge=0, le=16)
    max_diagnose_refinements_per_root: int = Field(default=2, ge=0, le=16)
    max_attempts_per_root_law: int = Field(default=4, ge=0, le=32)
    max_total_candidate_patches: int = Field(default=4, ge=0, le=32)
    max_toolchain_retries: int = Field(default=2, ge=0, le=16)
    max_check_after_fix: int = Field(default=2, ge=0, le=16)
    same_root_hash_repeat_without_improvement: int = Field(default=2, ge=1, le=8)


class DebugPipelineTraceConfig(BaseModel):
    """Disk and PostHog tracing for one repair pipeline run."""

    model_config = ConfigDict(extra="ignore")

    enabled: bool = True
    disk: bool = True
    posthog: bool = True
    disk_dir: str = ".traces"
    store_prompts: Literal["off", "hash", "full"] = "hash"


class DebugPipelineInteractiveConfig(BaseModel):
    """Wizard / interactive repair pipeline controls."""

    model_config = ConfigDict(extra="ignore")

    confirm_next_step: bool = False


class DebugPipelineConfig(BaseModel):
    """Wizard / OpenCode repair pipeline runtime policy."""

    model_config = ConfigDict(extra="ignore")

    effort: LlmReasoningEffort = "high"
    openrouter: DebugPipelineOpenRouterConfig = Field(
        default_factory=DebugPipelineOpenRouterConfig,
    )
    ensemble: DebugPipelineEnsembleConfig = Field(
        default_factory=DebugPipelineEnsembleConfig,
    )
    models: DebugPipelineModelsConfig = Field(default_factory=DebugPipelineModelsConfig)
    panels: DebugPipelinePanelsConfig = Field(default_factory=DebugPipelinePanelsConfig)
    emit_fix_engine: Literal["opencode", "legacy_llm_repair"] = "opencode"
    loops: DebugPipelineLoopsConfig = Field(default_factory=DebugPipelineLoopsConfig)
    trace: DebugPipelineTraceConfig = Field(default_factory=DebugPipelineTraceConfig)
    interactive: DebugPipelineInteractiveConfig = Field(
        default_factory=DebugPipelineInteractiveConfig,
    )

    @field_validator("effort", mode="before")
    @classmethod
    def _normalize_effort(cls, value: object) -> LlmReasoningEffort:
        normalized = normalize_reasoning_effort(value)
        if normalized is None:
            return "high"
        return normalized

    def reasoning_settings(self) -> LlmReasoningSettings:
        """Return OpenRouter reasoning payload for all debug-pipeline LLM calls."""
        return LlmReasoningSettings(effort=self.effort)

    def panel_for_step(self, step: DebugPipelineStep) -> tuple[str, ...]:
        """Return configured analysis_models for an ensemble step."""
        if step == "recognise":
            return self.panels.recognise
        if step == "diagnose":
            return self.panels.diagnose
        if step == "review":
            return self.panels.review
        msg = f"step {step} has no fusion panel"
        raise ValueError(msg)

    def single_model_for_step(self, step: DebugPipelineStep) -> str:
        """Return direct OpenRouter slug for a step (no Fusion)."""
        _ = step
        return self.models.single

    def uses_fusion(self, step: DebugPipelineStep) -> bool:
        """Whether the step should call OpenRouter Fusion."""
        return self.ensemble.enabled and step in ENSEMBLE_STEPS
