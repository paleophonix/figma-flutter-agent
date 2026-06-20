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
    "recognise": "plan",
    "inspect": "plan",
    "diagnose": "plan",
    "plan": "repair",
    "repair": "check",
    "regenerate": "check",
    "capture_verify": "check",
    "check": "check",
    "capture": "check",
    "review": "check",
}


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
        resolve_from_check,
        resolve_from_review,
    )

    chain = ReasoningChain.load(state_dir / "reasoning_chain.json")
    checkpoint = load_last_checkpoint(state_dir)
    loop_round = int(checkpoint.get("loop_round") or 1) if checkpoint else 1
    step = str(checkpoint.get("step") or "") if checkpoint else ""

    review = chain.steps.get("review")
    if review and str(review.get("decision", "")).upper() == "LOOP":
        return entry_step_for(resolve_from_review(review)), loop_round

    for key in sorted(chain.steps.keys(), reverse=True):
        if key == "check" or key.startswith("check_"):
            payload = chain.steps[key]
            if not payload.get("passed"):
                return entry_step_for(resolve_from_check(payload)), loop_round

    if step.startswith("check_") and step in chain.steps:
        payload = chain.steps[step]
        if not payload.get("passed"):
            return entry_step_for(resolve_from_check(payload)), loop_round

    if step == "summarize":
        return "recognise", loop_round
    return _CHECKPOINT_TO_PHASE.get(step, "recognise"), loop_round


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
