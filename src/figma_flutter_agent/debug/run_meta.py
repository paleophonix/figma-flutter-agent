"""Per-screen pipeline run metadata for Run Gate (``run.meta.json``)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from figma_flutter_agent.debug.paths import RUN_META_JSON, screen_root
from figma_flutter_agent.debug.run_meta_lock import (
    atomic_write_run_meta_dict,
    run_meta_lifecycle_lock,
)
from figma_flutter_agent.errors import RunMetaStaleWriterError

WritebackOutcome = Literal["committed", "rollback", "skipped", "failed"]
RunMetaStatus = Literal[
    "started",
    "parsed",
    "ir_ready",
    "planned",
    "validated",
    "completed",
    "failed",
    "timed_out",
    "legacy",
    "unknown",
]

RUN_META_SCHEMA_VERSION = "2"
LEGACY_RUN_META_SCHEMA_VERSION = "legacy"

# Candidate-scoped keys cleared on each new run; only committed + extension keys survive.
_STAMPED_RUN_META_KEYS = frozenset(
    {
        "feature",
        "pipeline_run_id",
        "candidate_build_run_id",
        "committed_build_run_id",
        "writeback",
        "written_files",
        "analyze_passed",
        "captured_at",
        "runMetaSchemaVersion",
        "status",
        "cached_ir_verdict",
        "clean_tree_hash",
        "generation_config_hash",
        "timed_out_stage",
        "last_error",
    }
)

_INCOMPLETE_RUN_STATUSES = frozenset(
    {"started", "parsed", "ir_ready", "planned", "validated"}
)
_TERMINAL_FAILURE_STATUSES = frozenset({"failed", "timed_out"})
INCOMPLETE_RUN_STATUSES = _INCOMPLETE_RUN_STATUSES
TERMINAL_FAILURE_RUN_STATUSES = _TERMINAL_FAILURE_STATUSES
KNOWN_RUN_META_SCHEMA_VERSIONS = frozenset({RUN_META_SCHEMA_VERSION})
KNOWN_RUN_META_STATUSES = frozenset(
    {
        "started",
        "parsed",
        "ir_ready",
        "planned",
        "validated",
        "completed",
        "failed",
        "timed_out",
        "legacy",
    }
)
KNOWN_WRITEBACK_OUTCOMES = frozenset({"committed", "rollback", "skipped", "failed"})


@dataclass(frozen=True)
class RunMetaRecord:
    """Serialized run.meta.json payload."""

    feature: str
    pipeline_run_id: str
    candidate_build_run_id: str
    committed_build_run_id: str | None
    writeback: WritebackOutcome
    written_files: tuple[str, ...]
    analyze_passed: bool | None
    captured_at: str
    run_meta_schema_version: str
    status: RunMetaStatus
    cached_ir_verdict: str | None = None
    clean_tree_hash: str | None = None
    generation_config_hash: str | None = None
    timed_out_stage: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        payload: dict[str, Any] = {
            "feature": self.feature,
            "pipeline_run_id": self.pipeline_run_id,
            "candidate_build_run_id": self.candidate_build_run_id,
            "committed_build_run_id": self.committed_build_run_id,
            "writeback": self.writeback,
            "written_files": list(self.written_files),
            "analyze_passed": self.analyze_passed,
            "captured_at": self.captured_at,
            "runMetaSchemaVersion": self.run_meta_schema_version,
            "status": self.status,
        }
        if self.cached_ir_verdict is not None:
            payload["cached_ir_verdict"] = self.cached_ir_verdict
        if self.clean_tree_hash is not None:
            payload["clean_tree_hash"] = self.clean_tree_hash
        if self.generation_config_hash is not None:
            payload["generation_config_hash"] = self.generation_config_hash
        if self.timed_out_stage is not None:
            payload["timed_out_stage"] = self.timed_out_stage
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunMetaRecord:
        """Parse run.meta.json dict without upgrading legacy artifacts."""
        schema_raw = data.get("runMetaSchemaVersion")
        if schema_raw is None:
            schema_version = LEGACY_RUN_META_SCHEMA_VERSION
        else:
            schema_version = str(schema_raw)

        status_raw = data.get("status")
        if status_raw is None:
            status: RunMetaStatus = "legacy"
        else:
            status = str(status_raw)  # type: ignore[assignment]

        return cls(
            feature=str(data.get("feature") or ""),
            pipeline_run_id=str(data.get("pipeline_run_id") or ""),
            candidate_build_run_id=str(
                data.get("candidate_build_run_id") or data.get("pipeline_run_id") or "",
            ),
            committed_build_run_id=(
                str(data["committed_build_run_id"]) if data.get("committed_build_run_id") else None
            ),
            writeback=str(data.get("writeback") or "skipped"),  # type: ignore[arg-type]
            written_files=tuple(str(path) for path in data.get("written_files") or []),
            analyze_passed=data.get("analyze_passed"),
            captured_at=str(data.get("captured_at") or ""),
            run_meta_schema_version=schema_version,
            status=status,
            cached_ir_verdict=(
                str(data["cached_ir_verdict"]) if data.get("cached_ir_verdict") else None
            ),
            clean_tree_hash=(
                str(data["clean_tree_hash"]) if data.get("clean_tree_hash") else None
            ),
            generation_config_hash=(
                str(data["generation_config_hash"])
                if data.get("generation_config_hash")
                else None
            ),
            timed_out_stage=(
                str(data["timed_out_stage"]) if data.get("timed_out_stage") else None
            ),
        )


def run_meta_path(project_dir: Path, feature_name: str) -> Path:
    """Return canonical ``run.meta.json`` path for a screen."""
    return screen_root(project_dir, feature_name) / RUN_META_JSON


def _read_run_meta_dict(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _write_run_meta_dict(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_run_meta_dict(path, payload)


def _assert_run_meta_ownership(existing: dict[str, Any], *, pipeline_run_id: str) -> None:
    """Reject lifecycle writes when the on-disk artifact belongs to another run."""
    current = str(existing.get("pipeline_run_id") or "").strip()
    if current and current != pipeline_run_id:
        msg = (
            f"run.meta ownership mismatch: writer={pipeline_run_id!r} "
            f"artifact={current!r}"
        )
        raise RunMetaStaleWriterError(msg)


def _resolve_committed_build_run_id(
    existing: dict[str, Any],
    *,
    pipeline_run_id: str,
    writeback: WritebackOutcome,
    explicit_committed: str | None = None,
) -> str | None:
    """Resolve committed run id from writeback outcome and prior artifact."""
    if writeback == "committed":
        return explicit_committed or pipeline_run_id
    raw = existing.get("committed_build_run_id")
    return str(raw) if raw else None


def _extension_fields(existing: dict[str, Any]) -> dict[str, Any]:
    """Return unknown/extension keys preserved across run boundaries."""
    return {key: value for key, value in existing.items() if key not in _STAMPED_RUN_META_KEYS}


def _current_run_evidence(existing: dict[str, Any], pipeline_run_id: str) -> dict[str, Any]:
    """Return forensic fields from the in-flight run when ids still match."""
    if str(existing.get("pipeline_run_id") or "") != pipeline_run_id:
        return {}
    preserved: dict[str, Any] = {}
    for key in (
        "cached_ir_verdict",
        "clean_tree_hash",
        "generation_config_hash",
        "timed_out_stage",
    ):
        if key in existing:
            preserved[key] = existing[key]
    return preserved


def is_run_meta_gate_trusted(meta: RunMetaRecord) -> bool:
    """Return whether Run Gate may trust schema status and writeback fields."""
    if meta.run_meta_schema_version == LEGACY_RUN_META_SCHEMA_VERSION:
        return meta.status == "legacy"
    if meta.run_meta_schema_version not in KNOWN_RUN_META_SCHEMA_VERSIONS:
        return False
    if meta.status not in KNOWN_RUN_META_STATUSES:
        return False
    if meta.writeback not in KNOWN_WRITEBACK_OUTCOMES:
        return False
    return True


def begin_run_meta(
    project_dir: Path,
    feature_name: str,
    *,
    pipeline_run_id: str,
) -> Path:
    """Start a new pipeline run: candidate = current run, committed = previous commit."""
    path = run_meta_path(project_dir, feature_name)
    with run_meta_lifecycle_lock(path):
        existing = _read_run_meta_dict(path)
        prev_committed = existing.get("committed_build_run_id")
        payload = _extension_fields(existing)
        payload["feature"] = feature_name
        payload["pipeline_run_id"] = pipeline_run_id
        payload["candidate_build_run_id"] = pipeline_run_id
        payload["status"] = "started"
        payload["runMetaSchemaVersion"] = RUN_META_SCHEMA_VERSION
        payload["captured_at"] = datetime.now(tz=UTC).isoformat()
        if prev_committed is not None:
            payload["committed_build_run_id"] = prev_committed
        _write_run_meta_dict(path, payload)
    return path


def abandon_superseded_run_meta(
    project_dir: Path,
    feature_name: str,
    *,
    pipeline_run_id: str,
    superseded_by: str,
) -> None:
    """Remove a stale early-feature artifact superseded by canonical resolved feature."""
    path = run_meta_path(project_dir, feature_name)
    if not path.is_file():
        return
    with run_meta_lifecycle_lock(path):
        existing = _read_run_meta_dict(path)
        if str(existing.get("pipeline_run_id") or "") != pipeline_run_id:
            return
        path.unlink(missing_ok=True)


def reconcile_run_meta_feature_identity(
    project_dir: Path,
    *,
    pipeline_run_id: str,
    early_feature: str | None,
    resolved_feature: str,
) -> str:
    """Return canonical lifecycle feature slug; migrate when early != resolved."""
    if early_feature == resolved_feature:
        return resolved_feature
    if early_feature is not None:
        abandon_superseded_run_meta(
            project_dir,
            early_feature,
            pipeline_run_id=pipeline_run_id,
            superseded_by=resolved_feature,
        )
    begin_run_meta(project_dir, resolved_feature, pipeline_run_id=pipeline_run_id)
    return resolved_feature


def update_run_meta_stage(
    project_dir: Path,
    feature_name: str,
    *,
    pipeline_run_id: str,
    status: RunMetaStatus,
    **fields: Any,
) -> Path:
    """Read-modify-write run.meta with atomic replace; preserves unknown keys."""
    path = run_meta_path(project_dir, feature_name)
    with run_meta_lifecycle_lock(path):
        payload = _read_run_meta_dict(path)
        _assert_run_meta_ownership(payload, pipeline_run_id=pipeline_run_id)
        payload.update(fields)
        payload["feature"] = feature_name
        payload["pipeline_run_id"] = pipeline_run_id
        payload["status"] = status
        payload["runMetaSchemaVersion"] = RUN_META_SCHEMA_VERSION
        payload["captured_at"] = datetime.now(tz=UTC).isoformat()
        _write_run_meta_dict(path, payload)
    return path


def mark_run_meta_failed(
    project_dir: Path,
    feature_name: str,
    *,
    pipeline_run_id: str,
    error: str | None = None,
) -> Path:
    """Record pipeline failure with forensic writeback and cleared candidate evidence."""
    path = run_meta_path(project_dir, feature_name)
    with run_meta_lifecycle_lock(path):
        existing = _read_run_meta_dict(path)
        _assert_run_meta_ownership(existing, pipeline_run_id=pipeline_run_id)
        prev_committed = existing.get("committed_build_run_id")
        payload = _extension_fields(existing)
        payload.update(
            {
                "feature": feature_name,
                "pipeline_run_id": pipeline_run_id,
                "candidate_build_run_id": pipeline_run_id,
                "status": "failed",
                "writeback": "failed",
                "written_files": [],
                "analyze_passed": None,
                "runMetaSchemaVersion": RUN_META_SCHEMA_VERSION,
                "captured_at": datetime.now(tz=UTC).isoformat(),
            }
        )
        payload.update(_current_run_evidence(existing, pipeline_run_id))
        if prev_committed is not None:
            payload["committed_build_run_id"] = prev_committed
        if error:
            payload["last_error"] = error[:500]
        _write_run_meta_dict(path, payload)
    return path


def write_run_meta(
    project_dir: Path,
    feature_name: str,
    *,
    pipeline_run_id: str,
    writeback: WritebackOutcome,
    written_files: list[str] | None = None,
    committed_build_run_id: str | None = None,
    analyze_passed: bool | None = None,
    status: RunMetaStatus = "completed",
    cached_ir_verdict: str | None = None,
    clean_tree_hash: str | None = None,
    generation_config_hash: str | None = None,
    timed_out_stage: str | None = None,
) -> Path:
    """Persist final run.meta.json after a generate pipeline run."""
    path = run_meta_path(project_dir, feature_name)
    with run_meta_lifecycle_lock(path):
        existing = _read_run_meta_dict(path)
        _assert_run_meta_ownership(existing, pipeline_run_id=pipeline_run_id)
        resolved_committed = _resolve_committed_build_run_id(
            existing,
            pipeline_run_id=pipeline_run_id,
            writeback=writeback,
            explicit_committed=committed_build_run_id,
        )
        record = RunMetaRecord(
            feature=feature_name,
            pipeline_run_id=pipeline_run_id,
            candidate_build_run_id=pipeline_run_id,
            committed_build_run_id=resolved_committed,
            writeback=writeback,
            written_files=tuple(written_files or []),
            analyze_passed=analyze_passed,
            captured_at=datetime.now(tz=UTC).isoformat(),
            run_meta_schema_version=RUN_META_SCHEMA_VERSION,
            status=status,
            cached_ir_verdict=cached_ir_verdict,
            clean_tree_hash=clean_tree_hash,
            generation_config_hash=generation_config_hash,
            timed_out_stage=timed_out_stage,
        )
        payload = record.to_dict()
        for key, value in _extension_fields(existing).items():
            if key not in payload:
                payload[key] = value
        _write_run_meta_dict(path, payload)
    return path


def read_run_meta(project_dir: Path, feature_name: str) -> RunMetaRecord | None:
    """Load run.meta.json when present."""
    path = run_meta_path(project_dir, feature_name)
    if not path.is_file():
        return None
    return RunMetaRecord.from_dict(_read_run_meta_dict(path))
