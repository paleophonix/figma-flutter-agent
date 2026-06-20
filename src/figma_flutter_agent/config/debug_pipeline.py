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

ALL_PIPELINE_STEPS: frozenset[str] = frozenset(
    {
        "recognise",
        "inspect",
        "diagnose",
        "plan",
        "repair",
        "fix",
        "review",
        "summarize",
    },
)

AGENT_BOARDS: frozenset[str] = frozenset({"screen", "forensic"})

FUSION_STEPS: frozenset[DebugPipelineStep] = frozenset(
    {"recognise", "diagnose", "review"},
)

FUSION_OUTER_MODEL = "openrouter/fusion"

DEFAULT_SINGLE_MODEL = "deepseek/deepseek-v4-pro"

DEFAULT_BOARD_MODELS: tuple[str, ...] = (
    "deepseek/deepseek-v4-pro",
    "xiaomi/mimo-v2.5-pro",
    "minimax/minimax-m3",
    "moonshotai/kimi-k2.7-code",
)

FUSION_ESCALATION_START_ROUND = 2
FUSION_ESCALATION_MAX_PANEL = 4


class DebugPipelineOpenRouterConfig(BaseModel):
    """OpenRouter Fusion outer alias."""

    model_config = ConfigDict(extra="ignore")

    fusion_model: str = FUSION_OUTER_MODEL


class DebugPipelineModelsConfig(BaseModel):
    """Direct slug fallback plus optional per-step and board-aware overrides."""

    model_config = ConfigDict(extra="ignore")

    single: str = DEFAULT_SINGLE_MODEL
    per_step: dict[str, str] = Field(default_factory=dict)
    board_overrides: dict[str, dict[str, str]] = Field(default_factory=dict)

    @field_validator("per_step")
    @classmethod
    def _validate_per_step(cls, value: dict[str, str]) -> dict[str, str]:
        unknown = sorted(set(value) - ALL_PIPELINE_STEPS)
        if unknown:
            msg = f"unknown debug_pipeline.models.per_step keys: {', '.join(unknown)}"
            raise ValueError(msg)
        return value

    @field_validator("board_overrides")
    @classmethod
    def _validate_board_overrides(
        cls,
        value: dict[str, dict[str, str]],
    ) -> dict[str, dict[str, str]]:
        for board, steps in value.items():
            if board not in AGENT_BOARDS:
                msg = (
                    f"unknown debug_pipeline.models.board_overrides board: {board!r} "
                    f"(expected screen or forensic)"
                )
                raise ValueError(msg)
            unknown = sorted(set(steps) - ALL_PIPELINE_STEPS)
            if unknown:
                msg = (
                    f"unknown debug_pipeline.models.board_overrides.{board} keys: "
                    f"{', '.join(unknown)}"
                )
                raise ValueError(msg)
        return value


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
    confirm_next_round: bool = False


class DebugPipelineWorktreesConfig(BaseModel):
    """Repair worktree retention on disk and in git metadata."""

    model_config = ConfigDict(extra="ignore")

    retain_latest: int = Field(
        default=1,
        ge=0,
        le=32,
        description="Keep N newest repair worktrees after each pipeline run.",
    )
    prune_orphans_after_run: bool = True


class DebugPipelineConfig(BaseModel):
    """Wizard / OpenCode repair pipeline runtime policy."""

    model_config = ConfigDict(extra="ignore")

    effort: LlmReasoningEffort = "high"
    openrouter: DebugPipelineOpenRouterConfig = Field(
        default_factory=DebugPipelineOpenRouterConfig,
    )
    models: DebugPipelineModelsConfig = Field(default_factory=DebugPipelineModelsConfig)
    emit_fix_engine: Literal["opencode", "legacy_llm_repair"] = "opencode"
    regenerate_after_compiler_repair: bool = True
    check_flutter_capture_verify: bool = Field(
        default=True,
        description=(
            "After repair, run flutter test capture verify and require "
            "flutterCaptureOk in check when capture was initially blocked."
        ),
    )
    worktrees: DebugPipelineWorktreesConfig = Field(default_factory=DebugPipelineWorktreesConfig)
    loops: DebugPipelineLoopsConfig = Field(default_factory=DebugPipelineLoopsConfig)
    trace: DebugPipelineTraceConfig = Field(default_factory=DebugPipelineTraceConfig)
    interactive: DebugPipelineInteractiveConfig = Field(
        default_factory=DebugPipelineInteractiveConfig,
    )
    board_models: tuple[str, ...] = Field(default_factory=lambda: DEFAULT_BOARD_MODELS)
    fusion_escalation: bool = Field(
        default=True,
        description=(
            "Round 2+ Fusion panel on recognise/diagnose/review "
            "(requires board_models)."
        ),
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

    def model_for_step(
        self,
        step: DebugPipelineStep,
        *,
        board: str = "forensic",
    ) -> str:
        """Resolve OpenRouter slug: board override → per_step → single fallback."""
        board_steps = self.models.board_overrides.get(board, {})
        if step in board_steps:
            return board_steps[step]
        if step in self.models.per_step:
            return self.models.per_step[step]
        return self.models.single

    def single_model_for_step(
        self,
        step: DebugPipelineStep,
        *,
        board: str = "forensic",
    ) -> str:
        """Return direct OpenRouter slug for a step (no Fusion)."""
        return self.model_for_step(step, board=board)

    def uses_fusion(self, step: DebugPipelineStep, *, outer_round: int = 1) -> bool:
        """Whether the step should call round-based OpenRouter Fusion escalation."""
        return (
            self.fusion_escalation
            and step in FUSION_STEPS
            and outer_round >= FUSION_ESCALATION_START_ROUND
            and bool(self.board_models)
        )
