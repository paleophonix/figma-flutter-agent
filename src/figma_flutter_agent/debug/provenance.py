"""Structured provenance dumps for tree mutations and classification decisions."""

from __future__ import annotations

import json
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from loguru import logger

from figma_flutter_agent.debug.paths import provenance_dump_path


class DeviationReason(StrEnum):
    """Named cause for a fact mutation, degradation, or recovery (F2)."""

    MISSING_VECTOR_ASSET = "missing_vector_asset"
    FILESYSTEM_COMPOSITE_ICON_RECOVERY = "filesystem_composite_icon_recovery"
    LAYOUT_POLLUTION_TOKENS = "layout_pollution_tokens"
    INVALID_SCREEN_CLASS = "invalid_screen_class"
    ARTBOARD_PREVIEW_LEAK = "artboard_preview_leak"
    UNSUPPORTED_VISUAL_NODE = "unsupported_visual_node"
    STRUCTURAL_GROUPING_RECONCILE = "structural_grouping_reconcile"
    ASSET_RECOVERY = "asset_recovery"
    FIDELITY_DOWNGRADE = "fidelity_downgrade"


class DeviationSeverity(StrEnum):
    """Whether a recorded deviation preserves or degrades intended fidelity (F2)."""

    RECOVERABLE = "recoverable"
    DEGRADED = "degraded"


@dataclass
class DeviationRecord:
    """Typed record of a fact mutation, degradation, or recovery (F2).

    Every mutation of a fact (as opposed to a candidate/evidence value) must
    produce a ``DeviationRecord``. No record means no mutation.
    """

    node_id: str
    field: str
    before: Any
    after: Any
    reason: DeviationReason
    source: str
    severity: DeviationSeverity
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        """Serialize for the debug provenance dump."""
        return {
            "nodeId": self.node_id,
            "field": self.field,
            "before": self.before,
            "after": self.after,
            "reason": self.reason.value,
            "source": self.source,
            "severity": self.severity.value,
            "provenance": self.provenance,
        }


_provenance_recorder: ContextVar[ProvenanceRecorder | None] = ContextVar(
    "provenance_recorder",
    default=None,
)


@dataclass
class ProvenanceMutation:
    """One recorded field mutation on a clean-tree or IR node."""

    checkpoint: str
    transform: str
    node_id: str
    field: str
    old: Any
    new: Any
    policy: str | None = None


@dataclass
class ProvenanceDecision:
    """Classification decision stub (populated in EPIC 2)."""

    node_id: str
    kind: str
    confidence: float
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProvenanceRecorder:
    """Accumulates mutations and decisions for one generate run."""

    feature_name: str
    project_dir: Path | None = None
    checkpoints: list[str] = field(default_factory=list)
    mutations: list[ProvenanceMutation] = field(default_factory=list)
    decisions: list[ProvenanceDecision] = field(default_factory=list)
    deviations: list[DeviationRecord] = field(default_factory=list)

    def note_checkpoint(self, checkpoint: str) -> None:
        """Record that a conservation checkpoint ran."""
        if checkpoint not in self.checkpoints:
            self.checkpoints.append(checkpoint)

    def record_mutation(
        self,
        *,
        checkpoint: str,
        transform: str,
        node_id: str,
        field: str,
        old: Any,
        new: Any,
        policy: str | None = None,
    ) -> None:
        """Append a mutation entry."""
        self.note_checkpoint(checkpoint)
        self.mutations.append(
            ProvenanceMutation(
                checkpoint=checkpoint,
                transform=transform,
                node_id=node_id,
                field=field,
                old=old,
                new=new,
                policy=policy,
            ),
        )

    def record_decision(
        self,
        *,
        node_id: str,
        kind: str,
        confidence: float,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        """Append a classification decision (EPIC 2 hook)."""
        self.decisions.append(
            ProvenanceDecision(
                node_id=node_id,
                kind=kind,
                confidence=confidence,
                evidence=evidence or {},
            ),
        )

    def record_deviation(
        self,
        *,
        node_id: str,
        field: str,
        before: Any,
        after: Any,
        reason: DeviationReason,
        source: str,
        severity: DeviationSeverity,
        provenance: dict[str, Any] | None = None,
    ) -> None:
        """Append a typed deviation record for a fact mutation, degradation, or recovery (F2)."""
        self.deviations.append(
            DeviationRecord(
                node_id=node_id,
                field=field,
                before=before,
                after=after,
                reason=reason,
                source=source,
                severity=severity,
                provenance=provenance or {},
            ),
        )

    def to_payload(self) -> dict[str, Any]:
        """Serialize the recorder for JSON dump."""
        from figma_flutter_agent.generator.ir.version import EMITTER_VERSION

        payload: dict[str, Any] = {
            "featureName": self.feature_name,
            "emitterVersion": EMITTER_VERSION,
            "checkpoints": list(self.checkpoints),
            "mutations": [
                {
                    "checkpoint": item.checkpoint,
                    "transform": item.transform,
                    "nodeId": item.node_id,
                    "field": item.field,
                    "old": item.old,
                    "new": item.new,
                    "policy": item.policy,
                }
                for item in self.mutations
            ],
            "decisions": [
                {
                    "nodeId": item.node_id,
                    "kind": item.kind,
                    "confidence": item.confidence,
                    "evidence": item.evidence,
                }
                for item in self.decisions
            ],
            "deviations": [item.to_payload() for item in self.deviations],
        }
        return payload


def activate_provenance_recorder(
    *,
    feature_name: str,
    project_dir: Path | None,
) -> ProvenanceRecorder:
    """Install a session recorder for the current async context."""
    recorder = ProvenanceRecorder(feature_name=feature_name, project_dir=project_dir)
    _provenance_recorder.set(recorder)
    return recorder


def get_provenance_recorder() -> ProvenanceRecorder | None:
    """Return the active provenance recorder, if any."""
    return _provenance_recorder.get()


def clear_provenance_recorder() -> None:
    """Remove the active provenance recorder."""
    _provenance_recorder.set(None)


def record_decision(
    *,
    node_id: str,
    kind: str,
    confidence: float,
    evidence: dict[str, Any] | None = None,
) -> None:
    """Record a classification decision on the active provenance session (EPIC 2 hook).

    Args:
        node_id: Figma node id.
        kind: Semantic widget kind label.
        confidence: Detector confidence in ``[0, 1]``.
        evidence: Optional structured detector evidence.
    """
    recorder = get_provenance_recorder()
    if recorder is None:
        return
    recorder.record_decision(
        node_id=node_id,
        kind=kind,
        confidence=confidence,
        evidence=evidence,
    )


def write_provenance_dump(recorder: ProvenanceRecorder | None = None) -> Path | None:
    """Flush provenance JSON to disk when ``project_dir`` is set.

    Args:
        recorder: Optional explicit recorder; defaults to the active session.

    Returns:
        Written path, or ``None`` when skipped.
    """
    active = recorder or get_provenance_recorder()
    if active is None or active.project_dir is None:
        return None
    destination = provenance_dump_path(active.project_dir, active.feature_name)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(active.to_payload(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    logger.debug("Wrote provenance dump to {}", destination.as_posix())
    return destination
