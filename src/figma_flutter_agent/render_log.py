"""Persist combat-mode Flutter/Figma render PNGs under ``logs/renders/``."""

from __future__ import annotations

import json
import re
from contextvars import ContextVar
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from loguru import logger

from figma_flutter_agent.config import Settings

RENDER_LOG_DIR = Path("logs/renders")

_session: ContextVar[RenderLogSession | None] = ContextVar("render_log_session", default=None)

_SAFE_LABEL_RE = re.compile(r"[^\w.-]+")


def _format_log_timestamp(when: datetime) -> str:
    """Return a filesystem-safe UTC timestamp prefix for render log folders."""
    return when.astimezone(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")


def _log_stem(*, run_id: str, started_at: datetime) -> str:
    return f"{_format_log_timestamp(started_at)}-{run_id}"


def _safe_label(label: str) -> str:
    return _SAFE_LABEL_RE.sub("_", label.strip()).strip("_") or "render"


@dataclass(frozen=True)
class RenderLogSession:
    """Correlation context for one pipeline run's render artifacts."""

    run_id: str
    log_stem: str
    feature_name: str | None = None
    project_dir: str | None = None


def render_artifacts_dir() -> Path | None:
    """Return the session render directory when a pipeline run is bound."""
    session = _session.get()
    if session is None:
        return None
    return RENDER_LOG_DIR / session.log_stem


def bound_render_log_dir() -> Path | None:
    """Alias for :func:`render_artifacts_dir`."""
    return render_artifacts_dir()


def render_log_enabled_for_pipeline(
    settings: Settings,
    *,
    dry_run: bool,
) -> bool:
    """True when combat render PNG logging should run for this pipeline invocation."""
    if dry_run:
        return False
    return settings.agent.generation.llm_visual_refine


def ensure_render_log_session(
    *,
    run_id: str | None = None,
    feature_name: str | None = None,
    project_dir: str | Path | None = None,
) -> Path | None:
    """Bind a render log session for the active pipeline run when refine needs captures."""
    from figma_flutter_agent.observability.llm_trace import current_llm_trace_context

    trace = current_llm_trace_context()
    resolved_run_id = run_id or (trace.run_id if trace is not None else None)
    if not resolved_run_id:
        from figma_flutter_agent.observability import new_run_id

        resolved_run_id = new_run_id()
    current = _session.get()
    if current is not None and current.run_id == resolved_run_id:
        return render_artifacts_dir()
    if current is not None:
        clear_render_log_session()
    return bind_render_log_session(
        run_id=resolved_run_id,
        feature_name=feature_name,
        project_dir=project_dir,
    )


def expected_render_png_path(
    label: str,
    *,
    attempt: int | None = None,
) -> Path | None:
    """Return the path :func:`record_render_png` would write for ``label`` (session must be bound)."""
    session = _session.get()
    if session is None:
        return None
    stem = _safe_label(label)
    if attempt is not None:
        filename = f"{stem}_{attempt:02d}.png"
    else:
        filename = f"{stem}.png"
    return RENDER_LOG_DIR / session.log_stem / filename


def bind_render_log_session(
    *,
    run_id: str,
    feature_name: str | None = None,
    project_dir: str | Path | None = None,
) -> Path:
    """Bind render artifact logging to the active pipeline/CLI session.

    Args:
        run_id: Short correlation id for this run.
        feature_name: Optional generated feature slug.
        project_dir: Optional Flutter project root (combat-mode capture).

    Returns:
        Session directory path under ``logs/renders/``.
    """
    project = str(project_dir) if project_dir is not None else None
    started_at = datetime.now(tz=UTC)
    stem = _log_stem(run_id=run_id, started_at=started_at)
    session = RenderLogSession(
        run_id=run_id,
        log_stem=stem,
        feature_name=feature_name,
        project_dir=project,
    )
    _session.set(session)
    out_dir = RENDER_LOG_DIR / stem
    out_dir.mkdir(parents=True, exist_ok=True)
    readme = out_dir / "README.txt"
    if not readme.is_file():
        readme.write_text(
            "Combat-mode render captures from figma-flutter generate.\n"
            "- figma_reference.png — Figma export used for visual refine.\n"
            "- flutter_render.png — first Flutter golden capture; flutter_render_XX.png on later refine passes.\n"
            "- diff_heatmap_XX.png — pixel diff overlay when refine runs.\n"
            "manifest.jsonl — one JSON line per artifact.\n",
            encoding="utf-8",
        )
    return out_dir


def update_render_log_session(
    *,
    feature_name: str | None = None,
    project_dir: str | Path | None = None,
) -> None:
    """Update optional fields on the bound render log session."""
    current = _session.get()
    if current is None:
        return
    updates: dict[str, Any] = {}
    if feature_name is not None:
        updates["feature_name"] = feature_name
    if project_dir is not None:
        updates["project_dir"] = str(project_dir)
    if updates:
        _session.set(replace(current, **updates))


def clear_render_log_session() -> None:
    """Clear the bound render log session."""
    _session.set(None)


def record_render_png(
    label: str,
    png: bytes,
    *,
    attempt: int | None = None,
    changed_ratio: float | None = None,
    extra: dict[str, Any] | None = None,
) -> Path | None:
    """Write a PNG artifact for the bound session.

    Args:
        label: Short slug (for example ``figma_reference``, ``flutter_render``).
        png: PNG bytes.
        attempt: Optional zero-based capture attempt index.
        changed_ratio: Optional pixel diff ratio vs Figma reference.
        extra: Optional JSON metadata fields.

    Returns:
        Written file path, or ``None`` when no session is bound.
    """
    session = _session.get()
    if session is None:
        return None

    out_dir = RENDER_LOG_DIR / session.log_stem
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = _safe_label(label)
    if attempt is not None:
        filename = f"{stem}_{attempt:02d}.png"
    else:
        filename = f"{stem}.png"
    out_path = out_dir / filename
    out_path.write_bytes(png)

    payload: dict[str, Any] = {
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "runId": session.run_id,
        "label": label,
        "file": filename,
        "bytes": len(png),
    }
    if session.feature_name is not None:
        payload["featureName"] = session.feature_name
    if session.project_dir is not None:
        payload["projectDir"] = session.project_dir
    if attempt is not None:
        payload["attempt"] = attempt
    if changed_ratio is not None:
        payload["changedRatio"] = changed_ratio
    if extra:
        payload.update(extra)

    manifest_path = out_dir / "manifest.jsonl"
    with manifest_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")

    logger.bind(
        run_id=session.run_id,
        render_artifact=out_path.as_posix(),
        label=label,
    ).info("Saved combat render PNG to {}", out_path.resolve())
    return out_path


def record_render_capture_failure(
    label: str,
    reason: str,
    *,
    attempt: int | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Append a failed capture attempt to ``manifest.jsonl`` when no PNG was written."""
    session = _session.get()
    if session is None:
        return

    out_dir = RENDER_LOG_DIR / session.log_stem
    out_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "runId": session.run_id,
        "label": label,
        "status": "failed",
        "reason": reason,
    }
    if session.feature_name is not None:
        payload["featureName"] = session.feature_name
    if session.project_dir is not None:
        payload["projectDir"] = session.project_dir
    if attempt is not None:
        payload["attempt"] = attempt
    if extra:
        payload.update(extra)

    manifest_path = out_dir / "manifest.jsonl"
    with manifest_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")
