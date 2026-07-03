"""Soft stage budget policy (Program 10 P0-4)."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from figma_flutter_agent.debug.paths import screen_root

STAGE_TIMING_JSON = "stage-timing.json"


@dataclass
class StageBudgetPolicy:
    """Per-stage soft budgets in seconds (pipeline boundary only)."""

    plan_materialize_sec: float = 120.0
    plan_layout_sec: float = 180.0
    plan_classify_sec: float = 90.0

    @classmethod
    def from_mapping(cls, values: dict[str, float] | None) -> StageBudgetPolicy:
        if not values:
            return cls()
        return cls(
            plan_materialize_sec=float(values.get("plan_materialize_sec", 120.0)),
            plan_layout_sec=float(values.get("plan_layout_sec", 180.0)),
            plan_classify_sec=float(values.get("plan_classify_sec", 90.0)),
        )


@dataclass
class StageTimingRecorder:
    """Collect substage durations and emit soft budget warnings."""

    policy: StageBudgetPolicy
    project_dir: Path | None = None
    feature_name: str | None = None
    entries: list[dict[str, Any]] = field(default_factory=list)

    def record(self, stage: str, started: float, *, budget_sec: float | None = None) -> None:
        elapsed = time.monotonic() - started
        exceeded = budget_sec is not None and elapsed > budget_sec
        entry = {
            "stage": stage,
            "elapsedSec": round(elapsed, 3),
            "budgetSec": budget_sec,
            "softExceeded": exceeded,
        }
        self.entries.append(entry)
        if exceeded:
            logger.warning(
                "Stage soft budget exceeded: {} took {:.2f}s (budget {:.2f}s)",
                stage,
                elapsed,
                budget_sec,
            )

    def write_artifact(self) -> Path | None:
        if self.project_dir is None or self.feature_name is None:
            return None
        path = screen_root(self.project_dir, self.feature_name) / STAGE_TIMING_JSON
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"schemaVersion": "1", "entries": self.entries}, indent=2) + "\n",
            encoding="utf-8",
        )
        return path
