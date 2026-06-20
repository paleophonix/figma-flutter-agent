"""Cumulative reasoning chain for OpenCode repair pipeline handoffs."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ReasoningChain:
    """Append-only structured outputs from completed steps."""

    steps: dict[str, dict[str, Any]] = field(default_factory=dict)

    def append(self, step: str, payload: dict[str, Any]) -> None:
        """Record one step output."""
        self.steps[step] = payload

    def compact_json(self) -> str:
        """Serialize chain for L6 prompt injection."""
        return json.dumps(self.steps, ensure_ascii=False, separators=(",", ":"))

    def prior_steps(self, current_step: str) -> dict[str, Any]:
        """Return outputs for all steps before ``current_step`` in pipeline order."""
        order = (
            "recognise",
            "inspect",
            "diagnose",
            "plan",
            "repair",
            "check",
            "fix",
            "capture",
            "review",
            "summarize",
        )
        if current_step not in order:
            return dict(self.steps)
        idx = order.index(current_step)
        allowed = set(order[:idx])
        return {name: payload for name, payload in self.steps.items() if name in allowed}

    def save(self, path: Path) -> None:
        """Persist chain to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"steps": self.steps}, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path) -> ReasoningChain:
        """Load chain from disk."""
        if not path.is_file():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("steps"), dict):
            return cls(steps={str(k): v for k, v in data["steps"].items() if isinstance(v, dict)})
        return cls()
