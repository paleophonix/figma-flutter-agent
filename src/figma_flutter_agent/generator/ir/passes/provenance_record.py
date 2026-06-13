"""Field-level provenance helpers for IR layout passes."""

from __future__ import annotations

from typing import Any

from figma_flutter_agent.debug.provenance import DeviationReason, DeviationSeverity
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


def record_deviation(
    ctx: PassContext,
    *,
    node_id: str,
    field_name: str,
    before: Any,
    after: Any,
    reason: DeviationReason,
    source: str,
    severity: DeviationSeverity,
    provenance: dict[str, Any] | None = None,
) -> None:
    """Append a typed ``DeviationRecord`` when a recorder is attached (F2).

    Every fact mutation, degradation, or recovery applied by an IR pass must
    call this helper. No record means no mutation.
    """
    if ctx.provenance is None:
        return
    ctx.provenance.record_deviation(
        node_id=node_id,
        field=field_name,
        before=before,
        after=after,
        reason=reason,
        source=source,
        severity=severity,
        provenance=provenance,
    )
