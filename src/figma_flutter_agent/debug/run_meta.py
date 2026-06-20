"""Per-screen pipeline run metadata for Run Gate (``run.meta.json``)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from figma_flutter_agent.debug.paths import RUN_META_JSON, screen_root

WritebackOutcome = Literal["committed", "rollback", "skipped", "failed"]


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

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "feature": self.feature,
            "pipeline_run_id": self.pipeline_run_id,
            "candidate_build_run_id": self.candidate_build_run_id,
            "committed_build_run_id": self.committed_build_run_id,
            "writeback": self.writeback,
            "written_files": list(self.written_files),
            "analyze_passed": self.analyze_passed,
            "captured_at": self.captured_at,
        }

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
