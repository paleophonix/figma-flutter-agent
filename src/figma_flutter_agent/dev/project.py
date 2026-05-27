"""Resolve Flutter project paths for dev run workflows."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.config import resolve_agent_config_path
from figma_flutter_agent.errors import FlutterProjectError


def _agent_repo_root() -> Path:
    from figma_flutter_agent.config import agent_repo_root

    return agent_repo_root()


def is_implicit_project_dir(project_dir: Path) -> bool:
    """Return True when ``project_dir`` is the implicit default (current directory)."""
    return project_dir.expanduser().resolve() == Path(".").resolve()


def env_configured_project_dir() -> Path | None:
    """Return ``FIGMA_FLUTTER_PROJECT_DIR`` from settings when set to a non-cwd path."""
    from figma_flutter_agent.config import load_settings

    configured = load_settings().default_project_dir.expanduser().resolve()
    if is_implicit_project_dir(configured):
        return None
    return configured


def default_flutter_project_candidate(*, env_project_dir: Path | None = None) -> Path:
    """Return the best default Flutter project root before validation.

    Precedence: ``FIGMA_FLUTTER_PROJECT_DIR`` (when valid path) → sibling ``demo_app`` → cwd.
    When no ``pubspec.yaml`` exists, returns the first candidate for use as a prompt default.

    Args:
        env_project_dir: Optional override; when omitted, reads ``FIGMA_FLUTTER_PROJECT_DIR``.
    """
    if env_project_dir is None:
        env_project_dir = env_configured_project_dir()

    ordered: list[Path] = []
    if env_project_dir is not None:
        ordered.append(env_project_dir.expanduser().resolve())
    sibling = (_agent_repo_root().parent / "demo_app").resolve()
    if sibling not in ordered:
        ordered.append(sibling)
    cwd = Path(".").resolve()
    if cwd not in ordered:
        ordered.append(cwd)

    for path in ordered:
        if (path / "pubspec.yaml").is_file():
            return path
    return ordered[0]


def resolve_implicit_project_dir(*, env_project_dir: Path | None = None) -> Path:
    """Resolve implicit ``.`` project dir using env and sibling defaults."""
    candidate = default_flutter_project_candidate(env_project_dir=env_project_dir)
    return resolve_project_dir(candidate)


def resolve_project_dir(project_dir: Path) -> Path:
    """Resolve and validate a Flutter project root."""
    root = project_dir.expanduser().resolve()
    if not (root / "pubspec.yaml").is_file():
        raise FlutterProjectError(f"Flutter project not found at {root}")
    return root


def resolve_manifest_path(project_dir: Path) -> Path:
    """Return ``screens.yaml`` inside ``project_dir``."""
    manifest = project_dir / "screens.yaml"
    if not manifest.is_file():
        raise FlutterProjectError(
            f"Batch manifest not found at {manifest.as_posix()}. "
            "Run `figma-flutter batch dump-file` first."
        )
    return manifest


def ensure_project_config(project_dir: Path) -> Path:
    """Validate the Flutter project and return the agent-repo config path."""
    resolve_project_dir(project_dir)
    return resolve_agent_config_path()
