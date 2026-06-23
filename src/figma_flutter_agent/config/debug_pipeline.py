"""OpenCode repair pipeline model policy (``.ai-figma-flutter.yml`` → ``debug_pipeline``)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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

FUSION_ESCALATION_MAX_PANEL = 4
DEFAULT_MIN_BOARD_MODELS = 2
DEFAULT_MAX_BOARD_MODELS = FUSION_ESCALATION_MAX_PANEL
FUSION_PANEL_HARD_CAP = 8
FUSION_DISABLED_MIN_BOARD_MODELS = 1

DEFAULT_EFFORT_PER_STEP: dict[str, LlmReasoningEffort] = {
    "recognise": "medium",
    "inspect": "low",
    "diagnose": "high",
    "plan": "medium",
    "repair": "medium",
    "fix": "low",
    "review": "high",
    "summarize": "low",
}

DEFAULT_EFFORT_ESCALATION_REPAIR: tuple[LlmReasoningEffort, ...] = (
    "none",
    "low",
    "medium",
)
DEFAULT_EFFORT_ESCALATION_FIX: tuple[LlmReasoningEffort, ...] = ("none", "low")

ESCALATABLE_WRITE_STEPS: frozenset[str] = frozenset({"repair", "fix"})


class DebugPipelineEffortEscalationConfig(BaseModel):
    """Retry-only reasoning effort ladders for OpenCode write steps."""

    model_config = ConfigDict(extra="ignore")

    enabled: bool = Field(
        default=True,
        description=(
            "When true, repair/fix use effort_escalation ladders indexed by "
            "repair_noop_retries+repair_retries or fix_attempt."
        ),
    )
    repair: tuple[LlmReasoningEffort, ...] = Field(
        default=DEFAULT_EFFORT_ESCALATION_REPAIR,
    )
    fix: tuple[LlmReasoningEffort, ...] = Field(
        default=DEFAULT_EFFORT_ESCALATION_FIX,
    )

    @field_validator("repair", "fix", mode="before")
    @classmethod
    def _normalize_ladder(cls, value: object) -> tuple[LlmReasoningEffort, ...]:
        if value is None:
            return ()
        if isinstance(value, str):
            effort = normalize_reasoning_effort(value)
            return (effort,) if effort is not None else ()
        if isinstance(value, (list, tuple)):
            rungs: list[LlmReasoningEffort] = []
            for item in value:
                effort = normalize_reasoning_effort(item)
                if effort is not None:
                    rungs.append(effort)
            return tuple(rungs)
        msg = "effort_escalation ladder must be a list of effort labels"
        raise TypeError(msg)

    def ladder_for(self, step: str) -> tuple[LlmReasoningEffort, ...] | None:
        """Return the escalation ladder for a write step, if configured."""
        if not self.enabled:
            return None
        if step == "repair" and self.repair:
            return self.repair
        if step == "fix" and self.fix:
            return self.fix
        return None


class DebugPipelineOpenRouterConfig(BaseModel):
    """OpenRouter Fusion outer alias."""

    model_config = ConfigDict(extra="ignore")

    fusion_model: str = FUSION_OUTER_MODEL


class DebugPipelineModelsConfig(BaseModel):
    """Direct slug fallback plus optional per-step and board-aware overrides."""

    model_config = ConfigDict(extra="ignore")

    single: str = DEFAULT_SINGLE_MODEL
    single_model: bool = Field(
        default=False,
        description="When true, use models.single for every step (ignore per_step).",
    )
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

    max_total_orchestrator_steps: int = Field(
        default=48,
        ge=4,
        le=256,
        description="Hard cap on orchestrator mid-cycle route transitions per run.",
    )
    max_fix_attempts: int = Field(default=2, ge=0, le=16)
    max_repair_retries_per_plan: int = Field(default=2, ge=0, le=16)
    max_repair_noop_retries: int = Field(
        default=6,
        ge=0,
        le=32,
        description="Plan/repair micro-loops when OpenCode repair touches no compiler files.",
    )
    max_diagnose_refinements_per_root: int = Field(default=2, ge=0, le=16)
    max_attempts_per_root_law: int = Field(default=4, ge=0, le=32)
    max_total_candidate_patches: int = Field(default=4, ge=0, le=32)
    max_toolchain_retries: int = Field(default=2, ge=0, le=16)
    max_check_after_fix: int = Field(default=2, ge=0, le=16)
    same_root_hash_repeat_without_improvement: int = Field(default=2, ge=1, le=8)
    max_opencode_repair_steps: int = Field(
        default=10,
        ge=4,
        le=64,
        description=(
            "OpenCode agent.steps cap for repair write sessions "
            "(limits tool-call rounds per prompt_message)."
        ),
    )
    max_opencode_fix_steps: int = Field(
        default=8,
        ge=4,
        le=64,
        description="OpenCode agent.steps cap for fix write sessions.",
    )
    opencode_prompt_timeout_sec: int | None = Field(
        default=None,
        ge=60,
        le=7200,
        description=(
            "Optional per repair/fix OpenCode prompt_message HTTP timeout in seconds. "
            "When omitted (null), the wizard waits until OpenCode finishes."
        ),
    )
    regenerate_timeout_sec: int = Field(
        default=900,
        ge=60,
        le=7200,
        description=(
            "Wall-clock cap for post-repair regenerate subprocess "
            "(worktree poetry pipeline replay). Wizard emits progress heartbeats "
            "until completion or timeout."
        ),
    )
    restart_opencode_serve_with_overlay: bool = Field(
        default=True,
        description=(
            "When true, wizard/debug kills an existing local OpenCode serve on the "
            "configured port and respawns with debug_pipeline overlay + OPENROUTER_API_KEY."
        ),
    )


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
    confirm_next_round: bool = Field(
        default=False,
        description=(
            "Wizard only: prompt before each new full correction cycle "
            "(recognise/inspect/diagnose re-entry), not before plan.revise or repair.retry."
        ),
    )


_DEFAULT_RETAIN_STOP_REASONS: tuple[str, ...] = (
    "regenerate_failed",
    "repair_gates_failed",
    "SCOPE_DRIFT",
    "budget_exhausted",
    "recognise_blocked",
    "check_failed",
    "plan_invalid_targets",
)


class DebugPipelineWorktreesConfig(BaseModel):
    """Repair worktree retention on disk and in git metadata."""

    model_config = ConfigDict(extra="ignore")

    retain_latest: int = Field(
        default=1,
        ge=0,
        le=32,
        description="Keep N newest repair worktrees after each pipeline run.",
    )
    min_age_minutes: int = Field(
        default=30,
        ge=0,
        le=24 * 60,
        description="Never destroy worktrees newer than this age (minutes).",
    )
    retain_failed: bool = Field(
        default=True,
        description="Pin failed-run worktrees when stop_reason matches retain_stop_reasons.",
    )
    retain_stop_reasons: tuple[str, ...] = Field(
        default=_DEFAULT_RETAIN_STOP_REASONS,
        description="Stop reasons that keep the current worktree beyond retain_latest.",
    )
    prune_orphans_after_run: bool = True

    @field_validator("retain_stop_reasons", mode="before")
    @classmethod
    def _normalize_retain_stop_reasons(cls, value: object) -> tuple[str, ...]:
        if value is None:
            return _DEFAULT_RETAIN_STOP_REASONS
        if isinstance(value, str):
            return (value,)
        if isinstance(value, (list, tuple)):
            return tuple(str(item) for item in value if str(item).strip())
        msg = "retain_stop_reasons must be a list of stop reason strings"
        raise TypeError(msg)


class DebugPipelineConfig(BaseModel):
    """Wizard / OpenCode repair pipeline runtime policy."""

    model_config = ConfigDict(extra="ignore")

    effort: LlmReasoningEffort = "high"
    common_effort: bool = Field(
        default=False,
        description=(
            "When true, use ``effort`` for every pipeline step. "
            "When false, use ``effort_per_step`` defaults plus overrides."
        ),
    )
    effort_per_step: dict[str, LlmReasoningEffort] = Field(default_factory=dict)
    effort_escalation: DebugPipelineEffortEscalationConfig = Field(
        default_factory=DebugPipelineEffortEscalationConfig,
    )
    openrouter: DebugPipelineOpenRouterConfig = Field(
        default_factory=DebugPipelineOpenRouterConfig,
    )
    models: DebugPipelineModelsConfig = Field(default_factory=DebugPipelineModelsConfig)
    emit_fix_engine: Literal["opencode", "legacy_llm_repair"] = "opencode"
    fix_enabled: bool = Field(
        default=False,
        description=(
            "When false, skip OpenCode fix loop; PATCH_CODE_EMIT routes stop with fix_disabled."
        ),
    )
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
    min_board_models: int = Field(
        default=DEFAULT_MIN_BOARD_MODELS,
        ge=1,
        le=FUSION_PANEL_HARD_CAP,
        description=(
            "Fusion panel floor from correction cycle 1. "
            "``1`` disables Fusion (single base model per step). "
            "``2+`` enables Fusion immediately with at least this many panelists "
            "(including the per-step base model)."
        ),
    )
    max_board_models: int = Field(
        default=DEFAULT_MAX_BOARD_MODELS,
        ge=1,
        le=FUSION_PANEL_HARD_CAP,
        description=(
            "Maximum Fusion panel size (includes base model). "
            "Caps panel growth across correction cycles when Fusion is enabled."
        ),
    )
    fusion_escalation: bool = Field(
        default=True,
        description=(
            "Fusion panel on recognise/diagnose/review when ``min_board_models > 1`` "
            "(not plan/repair micro-loops; requires board_models)."
        ),
    )

    @model_validator(mode="after")
    def _validate_board_model_panel_bounds(self) -> DebugPipelineConfig:
        if self.min_board_models > self.max_board_models:
            msg = (
                "debug_pipeline.min_board_models must be <= max_board_models "
                f"({self.min_board_models} > {self.max_board_models})"
            )
            raise ValueError(msg)
        return self

    @field_validator("effort", mode="before")
    @classmethod
    def _normalize_effort(cls, value: object) -> LlmReasoningEffort:
        normalized = normalize_reasoning_effort(value)
        if normalized is None:
            return "high"
        return normalized

    @field_validator("effort_per_step", mode="before")
    @classmethod
    def _normalize_effort_per_step(cls, value: object) -> dict[str, LlmReasoningEffort]:
        if not isinstance(value, dict):
            return {}
        normalized: dict[str, LlmReasoningEffort] = {}
        for step, raw_effort in value.items():
            effort = normalize_reasoning_effort(raw_effort)
            if effort is not None:
                normalized[str(step)] = effort
        return normalized

    @field_validator("effort_per_step")
    @classmethod
    def _validate_effort_per_step(
        cls,
        value: dict[str, LlmReasoningEffort],
    ) -> dict[str, LlmReasoningEffort]:
        unknown = sorted(set(value) - ALL_PIPELINE_STEPS)
        if unknown:
            msg = f"unknown debug_pipeline.effort_per_step keys: {', '.join(unknown)}"
            raise ValueError(msg)
        return value

    def effort_for_step(
        self,
        step: DebugPipelineStep,
        *,
        attempt_index: int = 0,
    ) -> LlmReasoningEffort:
        """Resolve reasoning effort for one pipeline step.

        Args:
            step: Pipeline step name.
            attempt_index: Zero-based retry index for repair/fix escalation ladders.
        """
        if self.common_effort:
            return self.effort
        ladder = self.effort_escalation.ladder_for(step)
        if ladder and step in ESCALATABLE_WRITE_STEPS:
            idx = min(max(attempt_index, 0), len(ladder) - 1)
            return ladder[idx]
        if step in self.effort_per_step:
            return self.effort_per_step[step]
        return DEFAULT_EFFORT_PER_STEP[step]

    def reasoning_settings(self) -> LlmReasoningSettings:
        """Return global OpenRouter reasoning payload (``common_effort`` mode)."""
        return LlmReasoningSettings(effort=self.effort)

    def reasoning_settings_for_step(
        self,
        step: DebugPipelineStep,
        *,
        attempt_index: int = 0,
    ) -> LlmReasoningSettings:
        """Return OpenRouter reasoning payload for one pipeline step."""
        return LlmReasoningSettings(
            effort=self.effort_for_step(step, attempt_index=attempt_index),
        )

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
        if not self.models.single_model and step in self.models.per_step:
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

    def structured_parse_fallback_models(self, primary: str) -> tuple[str, ...]:
        """Return alternate OpenRouter slugs for structured-output parse retries.

        Args:
            primary: Model slug that already returned non-JSON output.

        Returns:
            De-duplicated roster excluding ``primary`` (``board_models`` first).
        """
        seen = {primary}
        ordered: list[str] = []
        for slug in (*self.board_models, *DEFAULT_BOARD_MODELS):
            if slug not in seen:
                ordered.append(slug)
                seen.add(slug)
        return tuple(ordered)

    def uses_fusion(self, step: DebugPipelineStep, *, outer_round: int = 1) -> bool:
        """Whether the step should call Fusion escalation for this correction cycle.

        ``min_board_models: 1`` forces the base model only. ``min_board_models >= 2``
        enables Fusion from correction cycle 1 with a panel of at least that size.

        ``outer_round`` is the 1-based **full correction cycle** index (recognise → … →
        review), not plan/repair retry count.
        """
        return (
            self.fusion_escalation
            and step in FUSION_STEPS
            and self.min_board_models > FUSION_DISABLED_MIN_BOARD_MODELS
            and outer_round >= 1
            and bool(self.board_models)
        )
