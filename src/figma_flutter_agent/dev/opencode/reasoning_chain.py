"""Cumulative reasoning chain for OpenCode repair pipeline handoffs."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _compact_step_summary(payload: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "passed",
        "failure_class",
        "route",
        "reason_code",
        "same_root_hash",
        "blocked",
        "exhausted",
    )
    return {key: payload[key] for key in keys if key in payload}


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

    def compact_for_refine(self, pivot: dict[str, Any] | None) -> dict[str, Any]:
        """Return a compact chain slice for refine prompts."""
        keep = ("recognise", "inspect", "diagnose", "plan", "repair", "check", "capture", "review")
        compact = {name: self.steps[name] for name in keep if name in self.steps}
        if pivot:
            compact["pivot"] = pivot
        failed_attempts: list[dict[str, Any]] = []
        for key, payload in self.steps.items():
            if key.startswith("fix_") or key.startswith("check_"):
                failed_attempts.append({"step": key, "summary": _compact_step_summary(payload)})
        if failed_attempts:
            compact["failed_attempts"] = failed_attempts[-4:]
        return compact

    def compact_json_for_refine(self, pivot: dict[str, Any] | None = None) -> str:
        """Serialize compact chain for refine-step prompt injection."""
        import json

        return json.dumps(self.compact_for_refine(pivot), ensure_ascii=False, separators=(",", ":"))

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
