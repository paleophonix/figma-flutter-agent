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
