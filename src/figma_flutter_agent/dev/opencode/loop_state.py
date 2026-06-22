"""Loop budget state for the repair pipeline outer correction loop."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from figma_flutter_agent.config.debug_pipeline import DebugPipelineLoopsConfig


@dataclass
class LoopBudgetState:
    """Mutable counters for orchestrator loop budgets."""

    diagnose_refinements: int = 0
    repair_retries: int = 0
    fix_attempts: int = 0
    total_candidate_patches: int = 0
    toolchain_retries: int = 0
    check_after_fix: int = 0
    correction_cycle: int = 0
    repair_noop_retries: int = 0
    outer_round: int = 0
    root_hash_counts: dict[str, int] = field(default_factory=dict)
    last_root_hash: str = ""
    last_root_improved: bool = False

    def snapshot(self) -> dict[str, Any]:
        """Serialize budget counters for prompt injection."""
        return {
            "diagnose_refinements": self.diagnose_refinements,
            "repair_retries": self.repair_retries,
            "fix_attempts": self.fix_attempts,
            "total_candidate_patches": self.total_candidate_patches,
            "toolchain_retries": self.toolchain_retries,
            "check_after_fix": self.check_after_fix,
            "correction_cycle": self.correction_cycle,
            "repair_noop_retries": self.repair_noop_retries,
            "outer_round": self.correction_cycle,
            "same_root_repeats": dict(self.root_hash_counts),
        }

    def record_root_hash(self, root_hash: str, *, improved: bool) -> int:
        """Increment repeat counter for a failure root hash."""
        if not root_hash:
            return 0
        if improved:
            self.root_hash_counts[root_hash] = 0
            self.last_root_improved = True
        else:
            self.root_hash_counts[root_hash] = self.root_hash_counts.get(root_hash, 0) + 1
            self.last_root_improved = False
        self.last_root_hash = root_hash
        return self.root_hash_counts[root_hash]

    def same_root_exhausted(self, loops: DebugPipelineLoopsConfig) -> bool:
        """Return whether the current root hash exceeded the repeat budget."""
        if not self.last_root_hash:
            return False
        repeats = self.root_hash_counts.get(self.last_root_hash, 0)
        return repeats >= loops.same_root_hash_repeat_without_improvement and not self.last_root_improved

    def increment_for_route(self, route: str) -> None:
        """Bump the budget counter associated with a dispatch route."""
        if route == "diagnose.refine":
            self.diagnose_refinements += 1
        elif route == "repair.retry":
            self.repair_retries += 1
        elif route == "repair.noop":
            self.repair_noop_retries += 1
        elif route == "plan.revise":
            self.diagnose_refinements += 1
        elif route == "fix":
            self.fix_attempts += 1
            self.total_candidate_patches += 1
        elif route == "check.retry":
            self.toolchain_retries += 1

    def budget_exceeded(self, route: str, loops: DebugPipelineLoopsConfig) -> bool:
        """Return whether taking ``route`` would exceed configured budgets."""
        if route in {"diagnose.refine", "plan.revise"} and (
            self.diagnose_refinements >= loops.max_diagnose_refinements_per_root
        ):
            return True
        if route == "repair.retry" and self.repair_retries >= loops.max_repair_retries_per_plan:
            return True
        if route == "repair.noop" and self.repair_noop_retries >= loops.max_repair_noop_retries:
            return True
        if route == "fix" and self.fix_attempts >= loops.max_fix_attempts:
            return True
        if route == "check.retry" and self.toolchain_retries >= loops.max_toolchain_retries:
            return True
        if self.total_candidate_patches >= loops.max_total_candidate_patches:
            return True
        return self.same_root_exhausted(loops)
