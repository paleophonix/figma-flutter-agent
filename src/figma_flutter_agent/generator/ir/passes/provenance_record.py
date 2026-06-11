"""Field-level provenance helpers for IR layout passes."""

from __future__ import annotations

from typing import Any

from figma_flutter_agent.generator.ir.passes.protocol import PassContext, ProvenanceSink


def record_node_mutation(
    ctx: PassContext,
    *,
    transform: str,
    node_id: str,
    field_name: str,
    old: Any,
    new: Any,
    policy: str | None = None,
) -> None:
    """Append a structured mutation record when a recorder is attached."""
    sink = ProvenanceSink(
        recorder=ctx.provenance,
        checkpoint=ctx.checkpoint,
        transform=transform,
    )
    sink.record(
        node_id=node_id,
        field_name=field_name,
        old=old,
        new=new,
        policy=policy,
    )
