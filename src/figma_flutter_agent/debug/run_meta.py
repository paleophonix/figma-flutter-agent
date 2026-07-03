"""Per-screen pipeline run metadata for Run Gate (``run.meta.json``)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from figma_flutter_agent.debug.paths import RUN_META_JSON, screen_root

WritebackOutcome = Literal["committed", "rollback", "skipped", "failed"]


RUN_META_SCHEMA_VERSION = "2"


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
    run_meta_schema_version: str = RUN_META_SCHEMA_VERSION
    status: str = "completed"
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
        """Parse run.meta.json dict."""
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
            run_meta_schema_version=str(
                data.get("runMetaSchemaVersion") or RUN_META_SCHEMA_VERSION,
            ),
            status=str(data.get("status") or "completed"),
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


def write_run_meta(
    project_dir: Path,
    feature_name: str,
    *,
    pipeline_run_id: str,
    writeback: WritebackOutcome,
    written_files: list[str] | None = None,
    committed_build_run_id: str | None = None,
    analyze_passed: bool | None = None,
    status: str = "completed",
    cached_ir_verdict: str | None = None,
    clean_tree_hash: str | None = None,
    generation_config_hash: str | None = None,
    timed_out_stage: str | None = None,
) -> Path:
    """Persist run.meta.json after a generate pipeline run.

    Args:
        project_dir: Flutter project root.
        feature_name: Screen feature slug.
        pipeline_run_id: Correlation id for this pipeline execution.
        writeback: Whether project lib write committed, rolled back, or was skipped.
        written_files: Relative paths written to the Flutter project.
        committed_build_run_id: Run id stamped in committed project lib after write.
        analyze_passed: Pre-write analyze outcome when known.

    Returns:
        Path to written run.meta.json.
    """
    root = screen_root(project_dir, feature_name)
    root.mkdir(parents=True, exist_ok=True)
    record = RunMetaRecord(
        feature=feature_name,
        pipeline_run_id=pipeline_run_id,
        candidate_build_run_id=pipeline_run_id,
        committed_build_run_id=committed_build_run_id or pipeline_run_id,
        writeback=writeback,
        written_files=tuple(written_files or []),
        analyze_passed=analyze_passed,
        captured_at=datetime.now(tz=UTC).isoformat(),
        status=status,
        cached_ir_verdict=cached_ir_verdict,
        clean_tree_hash=clean_tree_hash,
        generation_config_hash=generation_config_hash,
        timed_out_stage=timed_out_stage,
    )
    path = root / RUN_META_JSON
    path.write_text(
        json.dumps(record.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def read_run_meta(project_dir: Path, feature_name: str) -> RunMetaRecord | None:
    """Load run.meta.json when present."""
    path = run_meta_path(project_dir, feature_name)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return None
    return RunMetaRecord.from_dict(data)
