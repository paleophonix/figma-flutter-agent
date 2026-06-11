"""Structured provenance dumps for tree mutations and classification decisions."""

from __future__ import annotations

import json
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from figma_flutter_agent.debug.paths import FIGMA_DEBUG_DIR

PROVENANCE_DIR = "provenance"

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
        }
        return payload


def provenance_dump_path(project_dir: Path, feature_name: str) -> Path:
    """Return ``.figma_debug/provenance/<feature>.json``."""
    return project_dir / FIGMA_DEBUG_DIR / PROVENANCE_DIR / f"{feature_name}.json"


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
