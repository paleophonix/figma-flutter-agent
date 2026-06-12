"""Resolve Flutter project directory for offline fixture golden capture."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.config import Settings
from figma_flutter_agent.dev.project import (
    default_flutter_project_candidate,
    is_flutter_project_root,
    resolve_project_dir,
)


def resolve_fixture_project_dir(settings: Settings | None = None) -> Path | None:
    """Return a warm Flutter project root for fixture golden capture when available.

    Args:
        settings: Agent settings; defaults to ``Settings()`` when omitted.

    Returns:
        Resolved project root, or ``None`` when no valid Flutter project is configured.
    """
    resolved = settings or Settings()
    workspace = resolved.default_project_dir.expanduser().resolve()
    candidate = default_flutter_project_candidate(env_project_dir=workspace)
    if not is_flutter_project_root(candidate):
        return None
    try:
        return resolve_project_dir(candidate)
    except Exception:
        return None
