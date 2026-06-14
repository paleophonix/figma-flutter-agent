"""Record Dart analyzer failures into ``<agent>/.debug/<feature>/dart-errors.json``."""

from __future__ import annotations

import json
from contextvars import ContextVar
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from loguru import logger

from figma_flutter_agent.debug.paths import dart_errors_json_path
from figma_flutter_agent.debug.terminal_log import append_terminal_output
from figma_flutter_agent.generator.dart.project_validation.errors import (
    summarize_analyze_diagnostics,
)

_LOG_FIELD_MAX_BYTES = 16_384
_ANALYZE_OUTPUT_MAX_BYTES = 1_048_576

_session: ContextVar[DartErrorSession | None] = ContextVar("dart_error_session", default=None)


def _format_log_timestamp(when: datetime) -> str:
    """Return a filesystem-safe UTC timestamp prefix for log filenames."""
    return when.astimezone(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")


def _log_stem(*, run_id: str, started_at: datetime) -> str:
    return f"{_format_log_timestamp(started_at)}-{run_id}"


@dataclass(frozen=True)
class DartErrorSession:
    """Correlation context for one CLI/pipeline run."""

    run_id: str
    log_stem: str
    feature_name: str | None = None
    project_dir: str | None = None


def dart_error_log_path(
    log_stem: str | None = None,
    *,
    project_dir: str | Path | None = None,
    feature_name: str | None = None,
) -> Path | None:
    """Return the structured Dart error artifact path for the active screen.

    Args:
        log_stem: Ignored; kept for backward-compatible call sites.
        project_dir: Flutter project root; when omitted, uses the bound session.
        feature_name: Screen slug; when omitted, uses the bound session.

    Returns:
        Path to ``<agent>/.debug/<feature>/dart-errors.json``, or ``None`` without a screen.
    """
    _ = log_stem
    resolved_project = project_dir
    if resolved_project is None:
        session = _session.get()
        if session is not None:
            resolved_project = session.project_dir
    if resolved_project is None:
        return None
    session = _session.get()
    feature = feature_name
    if feature is None and session is not None:
        feature = session.feature_name
    if not feature:
        return None
    return dart_errors_json_path(Path(resolved_project), feature)


def bound_dart_error_log_path() -> Path | None:
    """Return the Dart error artifact path for the bound session, if any."""
    session = _session.get()
    if session is None:
        return None
    return dart_error_log_path(
        session.log_stem,
        project_dir=session.project_dir,
        feature_name=session.feature_name,
    )


def bind_dart_error_session(
    *,
    run_id: str,
    feature_name: str | None = None,
    project_dir: str | Path | None = None,
) -> None:
    """Bind Dart error logging to the active pipeline/CLI session.

    Args:
        run_id: Short correlation id for this run.
        feature_name: Optional generated feature slug.
        project_dir: Flutter project root (required for on-disk logs).
    """
    project = Path(project_dir).resolve().as_posix() if project_dir is not None else None
    started_at = datetime.now(tz=UTC)
    _session.set(
        DartErrorSession(
            run_id=run_id,
            log_stem=_log_stem(run_id=run_id, started_at=started_at),
            feature_name=feature_name,
            project_dir=project,
        )
    )


def update_dart_error_session(
    *,
    feature_name: str | None = None,
    project_dir: str | Path | None = None,
) -> None:
    """Update optional fields on the bound Dart error session."""
    current = _session.get()
    if current is None:
        return
    updates: dict[str, Any] = {}
    if feature_name is not None:
        updates["feature_name"] = feature_name
    if project_dir is not None:
        updates["project_dir"] = Path(project_dir).resolve().as_posix()
    if updates:
        _session.set(replace(current, **updates))


def clear_dart_error_session() -> None:
    """Clear the bound Dart error session."""
    _session.set(None)


def _truncate_log_text(value: str, *, limit: int = _LOG_FIELD_MAX_BYTES) -> str:
    if len(value.encode("utf-8")) <= limit:
        return value
    return value[: limit // 2] + "…[truncated]"


def _coerce_log_payload(value: Any) -> Any:
    """Coerce arbitrary values into JSON-serializable log payload fragments."""
    if value is None or isinstance(value, (bool, int, float, str)):
        if isinstance(value, str):
            return _truncate_log_text(value)
        return value
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, BaseException):
        return _truncate_log_text(f"{type(value).__name__}: {value}")
    if isinstance(value, dict):
        return {str(key): _coerce_log_payload(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_coerce_log_payload(item) for item in value]
    return _truncate_log_text(str(value))


def _load_dart_errors_document(path: Path, session: DartErrorSession) -> dict[str, Any]:
    if path.is_file():
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            document = None
        else:
            if isinstance(document, dict) and document.get("runId") == session.run_id:
                return document
    return {
        "runId": session.run_id,
        "featureName": session.feature_name,
        "projectDir": session.project_dir,
        "events": [],
    }


def _write_dart_errors_document(path: Path, document: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(document, ensure_ascii=False, indent=2, default=str)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(body, encoding="utf-8")
    temp_path.replace(path)
    return path


def record_dart_analyze_failure(
    *,
    stage: str,
    detail: str,
    errors: tuple[str, ...] = (),
    analyze_output: str = "",
    attempt: int | None = None,
    passed: bool = False,
    extra: dict[str, Any] | None = None,
) -> Path | None:
    """Append one Dart analyze event to ``.debug/<feature>/dart-errors.json``.

    Args:
        stage: Pipeline stage slug (for example ``write``, ``llm_repair``).
        detail: Human-readable outcome summary.
        errors: Parsed analyzer error lines.
        analyze_output: Raw analyzer stdout/stderr when available.
        attempt: One-based attempt index for repair/refine loops.
        passed: When True, records a passing analyze check (default: failures only).
        extra: Optional additional JSON fields.

    Returns:
        Path to ``dart-errors.json`` when written, otherwise ``None``.
    """
    session = _session.get()
    if session is None:
        return None
    if passed:
        return None

    parsed_errors, warnings = summarize_analyze_diagnostics(analyze_output, detail=detail)
    merged_errors = tuple(errors) or parsed_errors or (detail,)

    event: dict[str, Any] = {
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "stage": stage,
        "detail": detail,
        "errors": list(merged_errors),
        "warnings": list(warnings),
        "passed": passed,
    }
    if attempt is not None:
        event["attempt"] = attempt
    if analyze_output:
        event["analyzeOutput"] = _truncate_log_text(
            analyze_output,
            limit=_ANALYZE_OUTPUT_MAX_BYTES,
        )
    if extra:
        event.update(_coerce_log_payload(extra))

    log_path = dart_error_log_path(session.log_stem, project_dir=session.project_dir)
    if log_path is None:
        logger.warning(
            "Dart analyzer errors for session {} were not logged (feature_name missing)",
            session.run_id,
        )
        return None

    try:
        document = _load_dart_errors_document(log_path, session)
        document["updatedAt"] = datetime.now(tz=UTC).isoformat()
        if session.feature_name is not None:
            document["featureName"] = session.feature_name
        if session.project_dir is not None:
            document["projectDir"] = session.project_dir
        events = document.setdefault("events", [])
        if not isinstance(events, list):
            events = []
            document["events"] = events
        events.append(event)
        written = _write_dart_errors_document(log_path, document)
        append_terminal_output(
            f"dart analyze ({stage})",
            stdout=f"Recorded {len(merged_errors)} analyzer error(s) in {written.name}\n",
            project_dir=Path(session.project_dir) if session.project_dir else None,
            feature_name=session.feature_name,
        )
    except Exception:
        logger.exception(
            "Failed to write Dart analyzer error log for session {}",
            session.run_id,
        )
        return None

    logger.bind(
        run_id=session.run_id,
        stage=stage,
        dart_error_log=written.as_posix(),
    ).info("Recorded {} Dart analyzer error(s) for session {}", len(merged_errors), session.run_id)
    return written
