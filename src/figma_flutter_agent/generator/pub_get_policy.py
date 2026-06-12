"""When to run ``flutter pub get`` and how to remember resolved pubspec state."""

from __future__ import annotations

import hashlib
from pathlib import Path

from loguru import logger

_PUBSPEC_RESOLVE_STAMP = ".debug/pubspec_resolve.sha256"


def pubspec_digest(project_dir: Path) -> str | None:
    """Return SHA-256 hex digest of ``pubspec.yaml``, or None when missing."""
    pubspec = project_dir / "pubspec.yaml"
    if not pubspec.is_file():
        return None
    return hashlib.sha256(pubspec.read_bytes()).hexdigest()


def _resolve_stamp_path(project_dir: Path) -> Path:
    return project_dir / _PUBSPEC_RESOLVE_STAMP


def read_pubspec_resolve_stamp(project_dir: Path) -> str | None:
    """Return the last recorded pubspec digest after a successful ``pub get``."""
    stamp = _resolve_stamp_path(project_dir)
    if not stamp.is_file():
        return None
    value = stamp.read_text(encoding="utf-8").strip()
    return value or None


def mark_pubspec_resolved(project_dir: Path) -> None:
    """Record that ``pubspec.yaml`` was resolved successfully in this project."""
    digest = pubspec_digest(project_dir)
    if digest is None:
        return
    stamp = _resolve_stamp_path(project_dir)
    stamp.parent.mkdir(parents=True, exist_ok=True)
    stamp.write_text(digest, encoding="utf-8")


def needs_pub_get(
    project_dir: Path,
    *,
    pubspec_changed: bool | None = None,
    force: bool = False,
) -> bool:
    """Return whether dependency resolution should run for ``project_dir``.

    Args:
        project_dir: Flutter project root.
        pubspec_changed: When set, overrides stamp comparison (write stage sets this).
        force: Always resolve (tests or explicit refresh).
    """
    if force:
        return True
    if pubspec_changed is True:
        return True
    if pubspec_changed is False:
        return False
    digest = pubspec_digest(project_dir)
    if digest is None:
        return False
    if read_pubspec_resolve_stamp(project_dir) != digest:
        return True
    package_config = project_dir / ".dart_tool" / "package_config.json"
    return not package_config.is_file()


def log_pub_get_skip(project_dir: Path) -> None:
    logger.info(
        "Skipping pub get for {} (pubspec.yaml unchanged since last resolve)",
        project_dir.as_posix(),
    )
