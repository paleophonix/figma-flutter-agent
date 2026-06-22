"""Shared pipeline types and protocols."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from figma_flutter_agent.dev.opencode.reasoning_chain import ReasoningChain
from figma_flutter_agent.dev.opencode.run_gate import RunGateResult
from figma_flutter_agent.dev.opencode.workspace import RepairWorkspace


class OpenCodeRepairClient(Protocol):
    """Minimal OpenCode client for repair build step."""

    def bind_worktree(self, directory: str | None) -> None: ...

    async def create_session(self, *, title: str) -> str: ...

    async def prompt_message(
        self,
        session_id: str,
        *,
        text: str,
        agent: str | None = None,
        model: str | None = None,
        reasoning_effort: str | None = None,
        on_progress: Callable[[str], None] | None = None,
        progress_step: str = "repair",
        progress_poll_sec: float = 8.0,
    ) -> dict[str, Any]: ...


@dataclass
class PipelineOutcome:
    """Final pipeline run outcome."""

    gate: RunGateResult
    workspace: RepairWorkspace | None
    chain: ReasoningChain = field(default_factory=ReasoningChain)
    stopped: bool = False
    stop_reason: str = ""
    summarize_blocked: bool = False
    trace_dir: Path | None = None
    loop_rounds: int = 0
