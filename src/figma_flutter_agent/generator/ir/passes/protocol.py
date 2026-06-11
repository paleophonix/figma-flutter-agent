"""Pass protocol types for IR layout pass manager."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Protocol

from figma_flutter_agent.schemas import CleanDesignTreeNode, ScreenIr

if TYPE_CHECKING:
    from figma_flutter_agent.debug.provenance import ProvenanceRecorder


@dataclass
class PassContext:
    """Mutable state threaded through registered IR layout passes."""

    screen_ir: ScreenIr
    clean_tree: CleanDesignTreeNode
    macro_height_threshold_px: int = 900
    inject_root_scroll_host: bool = False
    provenance: ProvenanceRecorder | None = None
    checkpoint: str = "CP2_ir_passes"

    def with_trees(
        self,
        screen_ir: ScreenIr,
        clean_tree: CleanDesignTreeNode,
    ) -> PassContext:
        """Return a copy with updated dual graphs."""
        return replace(self, screen_ir=screen_ir, clean_tree=clean_tree)


class PassRun(Protocol):
    """Callable signature for a single IR layout pass."""

    def __call__(self, ctx: PassContext) -> PassContext:
        """Run the pass and return updated context."""


@dataclass(frozen=True)
class Pass:
    """Named IR layout transform with declared mutation and preservation contracts."""

    name: str
    mutates: frozenset[str]
    preserves: frozenset[str]
    run: PassRun


@dataclass
class ProvenanceSink:
    """Lightweight mutation sink used by checkpoints outside PassManager."""

    recorder: ProvenanceRecorder | None = None
    checkpoint: str = ""
    transform: str = ""

    def record(
        self,
        *,
        node_id: str,
        field_name: str,
        old: Any,
        new: Any,
        policy: str | None = None,
    ) -> None:
        """Append a structured mutation when a recorder is attached."""
        if self.recorder is None:
            return
        self.recorder.record_mutation(
            checkpoint=self.checkpoint,
            transform=self.transform,
            node_id=node_id,
            field=field_name,
            old=old,
            new=new,
            policy=policy,
        )


def pass_from_callable(
    name: str,
    runner: Callable[[PassContext], PassContext],
    *,
    mutates: frozenset[str] | None = None,
    preserves: frozenset[str] | None = None,
) -> Pass:
    """Build a ``Pass`` from an existing dual-graph function."""
    return Pass(
        name=name,
        mutates=mutates or frozenset({"screen_ir", "clean_tree"}),
        preserves=preserves or frozenset({"node_multiset", "stack_paint_order", "graph_sync"}),
        run=runner,
    )
