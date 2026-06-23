"""Salvage pending compiler edits from a repair worktree after noop or blocked plan."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

from figma_flutter_agent.dev.opencode.gates import run_repair_gates
from figma_flutter_agent.dev.opencode.scope_enforcement import (
    collect_repair_gate_paths,
    diff_touched_paths,
    plan_has_actionable_compiler_targets,
)
from figma_flutter_agent.dev.opencode.workspace import RepairWorkspace

_COMPILER_PREFIX = "src/figma_flutter_agent/"
_SALVAGE_SKIP_PREFIXES = (
    ".repair/",
    ".debug/",
)


def _normalize_repo_path(path: str) -> str:
    normalized = path.replace("\\", "/").strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def collect_pending_compiler_gate_paths(worktree: Path) -> list[str]:
    """Return repo-relative compiler and test paths changed in the worktree.

    Args:
        worktree: Repair git worktree root.

    Returns:
        Sorted unique paths suitable for scoped repair gates.
    """
    pending: list[str] = []
    for raw in diff_touched_paths(worktree):
        normalized = _normalize_repo_path(raw)
        if any(normalized.startswith(prefix) for prefix in _SALVAGE_SKIP_PREFIXES):
            continue
        if normalized.startswith(_COMPILER_PREFIX) or normalized.startswith("tests/"):
            pending.append(normalized)
    return sorted(set(pending))


def plan_allows_worktree_salvage(plan_payload: dict[str, Any]) -> bool:
    """Return whether salvage may run for the current executive plan.

    Args:
        plan_payload: Validated or blocked plan JSON.

    Returns:
        True when the plan is blocked or has no actionable compiler CODE_CHANGE targets.
    """
    if plan_payload.get("blocked"):
        return True
    return not plan_has_actionable_compiler_targets(plan_payload)


def attempt_worktree_compiler_salvage(
    workspace: RepairWorkspace,
    *,
    plan_payload: dict[str, Any],
    diagnose_payload: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Prove and adopt pending worktree compiler edits when repair/plan stalled.

    ``RepairWorktreeSalvageLaw``: after repair noop or ``plan.blocked``, reuse
    on-disk compiler diffs from a prior OpenCode session (for example timeout)
    when scoped ruff/pytest gates pass.

    Args:
        workspace: Active repair workspace.
        plan_payload: Current executive plan (often blocked with empty steps).
        diagnose_payload: Optional diagnose output (reserved for future law routing).

    Returns:
        Synthetic repair payload when salvage succeeds; otherwise ``None``.
    """
    _ = diagnose_payload
    if not plan_allows_worktree_salvage(plan_payload):
        return None
    pending = collect_pending_compiler_gate_paths(workspace.worktree)
    compiler_paths = [path for path in pending if path.startswith(_COMPILER_PREFIX)]
    if not compiler_paths:
        return None
    gate_paths = collect_repair_gate_paths(
        plan_payload,
        worktree=workspace.worktree,
        git_touched=pending,
    )
    gate_result = run_repair_gates(workspace.worktree, touched_paths=gate_paths)
    if not gate_result.passed:
        logger.warning(
            "Repair worktree salvage gates failed compiler_paths={} ruff_ok={} pytest_ok={}",
            compiler_paths,
            gate_result.ruff_ok,
            gate_result.pytest_ok,
        )
        return None
    logger.info(
        "Repair worktree salvage adopted pending compiler edits paths={}",
        pending,
    )
    return {
        "step": "repair",
        "skipped": False,
        "salvaged": True,
        "salvage_reason": "worktree_compiler_edits_pending",
        "session_id": None,
        "filesTouched": pending,
        "scope": {
            "passed": True,
            "reason_code": "SCOPE_OK",
            "violations": [],
        },
        "gates": {
            "ruff": gate_result.ruff_ok,
            "pytest": gate_result.pytest_ok,
            "passed": gate_result.passed,
            "skipped": gate_result.skipped,
            "touched_paths": list(gate_result.touched_paths),
            "ruff_output": gate_result.ruff_output[:4000],
            "pytest_output": gate_result.pytest_output[:4000],
        },
        "noop": False,
        "incomplete": False,
        "agent_summary": (
            "Salvaged pending worktree compiler edits after repair noop or blocked plan."
        ),
    }
