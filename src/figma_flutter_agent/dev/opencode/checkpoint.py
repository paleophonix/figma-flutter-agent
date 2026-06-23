"""Checkpoint manifest for repair pipeline resume and replay."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def append_checkpoint(
    state_dir: Path,
    *,
    step: str,
    loop_round: int,
    extra: dict[str, Any] | None = None,
) -> None:
    """Append one checkpoint record under ``state_dir/checkpoints.jsonl``."""
    state_dir.mkdir(parents=True, exist_ok=True)
    record: dict[str, Any] = {
        "step": step,
        "loop_round": loop_round,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    if extra:
        record.update(extra)
    path = state_dir / "checkpoints.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_last_checkpoint(state_dir: Path) -> dict[str, Any] | None:
    """Return the last JSONL checkpoint record when present."""
    path = state_dir / "checkpoints.jsonl"
    if not path.is_file():
        return None
    last: dict[str, Any] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            last = parsed
    return last


_CHECKPOINT_TO_PHASE: dict[str, str] = {
    "recognise": "inspect",
    "inspect": "diagnose",
    "diagnose": "plan",
    "plan": "repair",
    "repair": "check",
    "regenerate": "check",
    "capture_verify": "check",
    "check": "check",
    "capture": "check",
    "review": "check",
}

_LOOP_BUDGET_FILE = "loop_budget.json"


def save_loop_budget(state_dir: Path, loop_state: Any) -> None:
    """Persist outer-loop budget counters for resume."""
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / _LOOP_BUDGET_FILE
    path.write_text(json.dumps(loop_state.snapshot(), indent=2) + "\n", encoding="utf-8")


def load_loop_budget(state_dir: Path) -> dict[str, Any] | None:
    """Load persisted loop budget snapshot when present."""
    path = state_dir / _LOOP_BUDGET_FILE
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def restore_loop_budget(state_dir: Path) -> Any:
    """Hydrate ``LoopBudgetState`` from disk or return a fresh instance."""
    from figma_flutter_agent.dev.opencode.loop_state import LoopBudgetState

    raw = load_loop_budget(state_dir)
    if not raw:
        return LoopBudgetState()
    state = LoopBudgetState()
    state.diagnose_refinements = int(raw.get("diagnose_refinements") or 0)
    state.diagnose_bootstrap = int(raw.get("diagnose_bootstrap") or 0)
    state.plan_validation_attempts = int(raw.get("plan_validation_attempts") or 0)
    state.orchestrator_steps = int(raw.get("orchestrator_steps") or 0)
    state.repair_retries = int(raw.get("repair_retries") or 0)
    state.fix_attempts = int(raw.get("fix_attempts") or 0)
    state.total_candidate_patches = int(raw.get("total_candidate_patches") or 0)
    state.toolchain_retries = int(raw.get("toolchain_retries") or 0)
    state.capture_produce_attempts = int(raw.get("capture_produce_attempts") or 0)
    state.check_after_fix = int(raw.get("check_after_fix") or 0)
    state.repair_noop_retries = int(raw.get("repair_noop_retries") or 0)
    state.correction_cycle = int(raw.get("correction_cycle") or raw.get("outer_round") or 0)
    state.outer_round = state.correction_cycle
    repeats = raw.get("same_root_repeats")
    if isinstance(repeats, dict):
        state.root_hash_counts = {str(k): int(v) for k, v in repeats.items()}
    return state


def _checkpoint_failed_check_route(
    chain: Any,
    *,
    step: str,
    loop_round: int,
) -> tuple[str, int] | None:
    """Map a failed check checkpoint to the next orchestrator entry."""
    from figma_flutter_agent.dev.opencode.failure_class import FailureClass
    from figma_flutter_agent.dev.opencode.route_dispatch import (
        RouteDecision,
        entry_step_for,
        resolve_from_check,
    )

    payload = chain.steps.get(step) if step in chain.steps else None
    if payload is None and step.startswith("check_"):
        payload = chain.steps.get(step)
    if payload is None and step == "check":
        payload = chain.steps.get("check")
    if not isinstance(payload, dict) or payload.get("passed"):
        return None
    route = resolve_from_check(payload)
    if route == RouteDecision.STOP_HUMAN:
        failure = str(payload.get("failure_class") or "")
        if failure in {
            FailureClass.UNKNOWN_BLOCKED.value,
            FailureClass.TOOLCHAIN_FLAKE.value,
        }:
            return "plan", loop_round
        return "diagnose", loop_round
    return entry_step_for(route), loop_round


def resolve_resume_phase_entry(state_dir: Path) -> tuple[str, int]:
    """Map saved checkpoints and chain state to orchestrator resume entry.

    Args:
        state_dir: Repair ``.repair/state`` directory.

    Returns:
        Tuple of ``phase_entry`` and ``loop_round`` for the outer correction loop.
    """
    from figma_flutter_agent.dev.opencode.reasoning_chain import ReasoningChain
    from figma_flutter_agent.dev.opencode.route_dispatch import (
        entry_step_for,
        repair_touched_compiler_plan_targets,
        resolve_from_review,
    )
    from figma_flutter_agent.dev.opencode.scope_enforcement import (
        plan_has_actionable_compiler_targets,
    )

    chain = ReasoningChain.load(state_dir / "reasoning_chain.json")
    checkpoint = load_last_checkpoint(state_dir)
    loop_round = int(checkpoint.get("loop_round") or 1) if checkpoint else 1
    step = str(checkpoint.get("step") or "") if checkpoint else ""

    review = chain.steps.get("review")
    if review and str(review.get("decision", "")).upper() == "LOOP":
        return entry_step_for(resolve_from_review(review)), loop_round

    if step == "repair":
        repair = chain.steps.get("repair")
        if isinstance(repair, dict) and repair.get("noop"):
            plan = chain.steps.get("plan")
            plan_payload = plan if isinstance(plan, dict) else {}
            if repair_touched_compiler_plan_targets(repair, plan_payload):
                return "repair", loop_round
            if plan_has_actionable_compiler_targets(plan_payload):
                return "plan", loop_round
            return "plan", loop_round
        from figma_flutter_agent.dev.opencode.repair_state import repair_needs_retry

        if isinstance(repair, dict) and repair_needs_retry(repair):
            return "repair", loop_round
        return "check", loop_round

    if step == "check" or step.startswith("check_"):
        routed = _checkpoint_failed_check_route(chain, step=step, loop_round=loop_round)
        if routed is not None:
            return routed

    if step == "summarize":
        if review and str(review.get("decision", "")).upper() == "LOOP":
            return entry_step_for(resolve_from_review(review)), loop_round
        return "check", loop_round
    return _CHECKPOINT_TO_PHASE.get(step, "recognise"), loop_round


def persist_resume_context(state_dir: Path, updates: dict[str, Any]) -> None:
    """Merge resume hints into ``.repair/data_context.json``."""
    path = state_dir.parent / "data_context.json"
    existing: dict[str, Any] = {}
    if path.is_file():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            existing = loaded
    merged = {**existing, **updates}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_resume_context(state_dir: Path) -> dict[str, Any] | None:
    """Load resume hints from ``data_context.json`` when present."""
    for candidate in (state_dir.parent / "data_context.json", state_dir / "data_context.json"):
        if candidate.is_file():
            data = json.loads(candidate.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    chain_path = state_dir / "reasoning_chain.json"
    if chain_path.is_file():
        return {"reasoning_chain": json.loads(chain_path.read_text(encoding="utf-8"))}
    return None
