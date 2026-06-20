"""Emit-layer fix runner via OpenCode (planned_files only)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from figma_flutter_agent.dev.opencode.schema_gate import validate_step_output


@dataclass(frozen=True)
class FixResult:
    """Outcome of one fix attempt."""

    attempt: int
    exhausted: bool
    payload: dict[str, Any]


def run_fix_attempt(
    *,
    state_dir: Path,
    check_payload: dict[str, Any],
    attempt: int,
    max_attempts: int,
    opencode_summary: str = "",
) -> FixResult:
    """Record fix attempt outcome (OpenCode edit delegated to repair session)."""
    exhausted = attempt >= max_attempts
    payload: dict[str, Any] = {
        "step": "fix",
        "phase": "emit_materialization",
        "attempt": attempt,
        "maxAttempts": max_attempts,
        "blocked": False,
        "exhausted": exhausted,
        "failure_class": check_payload.get("failure_class"),
        "same_root_hash": check_payload.get("same_root_hash"),
        "notes": opencode_summary[:500] if opencode_summary else "",
    }
    validate_step_output("fix", payload)
    path = state_dir / f"fix_{attempt}.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (state_dir / "fix.json").write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )
    return FixResult(attempt=attempt, exhausted=exhausted, payload=payload)
