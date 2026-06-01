"""Resolve Flutter project paths for dev run workflows."""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from figma_flutter_agent.config import resolve_agent_config_path
from figma_flutter_agent.errors import FlutterProjectError

_BATCH_MANIFEST_NAME = "screens.yaml"


def _agent_repo_root() -> Path:
    from figma_flutter_agent.config import agent_repo_root

    return agent_repo_root()


def is_implicit_project_dir(project_dir: Path) -> bool:
    """Return True when ``project_dir`` is the implicit default (current directory)."""
    return project_dir.expanduser().resolve() == Path(".").resolve()


def is_flutter_project_root(path: Path) -> bool:
    """Return True when ``path`` contains a Flutter ``pubspec.yaml``."""
    return (path.expanduser().resolve() / "pubspec.yaml").is_file()


def has_batch_manifest(project_dir: Path) -> bool:
    """Return True when ``project_dir`` contains a batch ``screens.yaml`` manifest."""
    return (project_dir.expanduser().resolve() / _BATCH_MANIFEST_NAME).is_file()


def env_configured_workspace_root() -> Path | None:
    """Return ``FIGMA_FLUTTER_PROJECT_DIR`` when set to a non-cwd workspace path."""
    from figma_flutter_agent.config import load_settings

    configured = load_settings().default_project_dir.expanduser().resolve()
    if is_implicit_project_dir(configured):
        return None
    return configured


def env_configured_project_dir() -> Path | None:
    """Return the configured workspace root (alias for :func:`env_configured_workspace_root`)."""
    return env_configured_workspace_root()


def discover_flutter_projects(workspace_root: Path) -> list[Path]:
    """List Flutter project roots under a workspace directory.

    When ``workspace_root`` itself contains ``pubspec.yaml``, returns only that
    path (single-project layout). Otherwise scans immediate child directories.

    Args:
        workspace_root: Parent directory from ``FIGMA_FLUTTER_PROJECT_DIR``.

    Returns:
        Sorted list of resolved project roots.
    """
    root = workspace_root.expanduser().resolve()
    if not root.is_dir():
        return []
    if is_flutter_project_root(root):
        return [root]
    projects: list[Path] = []
    for child in sorted(root.iterdir(), key=lambda item: item.name.lower()):
        if child.is_dir() and is_flutter_project_root(child):
            projects.append(child.resolve())
    return projects


def active_project_relative_path(workspace_root: Path, project_dir: Path) -> str:
    """Return a stable relative path for persisting ``project_dir`` under ``workspace_root``."""
    workspace = workspace_root.expanduser().resolve()
    project = project_dir.expanduser().resolve()
    try:
        return project.relative_to(workspace).as_posix()
    except ValueError:
        return project.as_posix()


def resolve_active_flutter_project(*, env_workspace: Path | None = None) -> Path | None:
    """Resolve the active Flutter project under a workspace root.

    Precedence: persisted ``active_project`` in workspace prefs → sole child project.

    Args:
        env_workspace: Workspace directory; when omitted, reads settings env.

    Returns:
        Resolved Flutter project root, or ``None`` when unset or ambiguous.
    """
    from figma_flutter_agent.dev.wizard_prefs import load_workspace_prefs

    workspace = env_workspace or env_configured_workspace_root()
    if workspace is None:
        return None
    workspace = workspace.expanduser().resolve()
    if not workspace.is_dir():
        return None

    projects = discover_flutter_projects(workspace)
    prefs = load_workspace_prefs(workspace)
    if prefs.active_project:
        candidate = Path(prefs.active_project)
        if not candidate.is_absolute():
            candidate = workspace / candidate
        candidate = candidate.resolve()
        if is_flutter_project_root(candidate):
            return candidate

    if len(projects) == 1:
        return projects[0]
    return None


def _workspace_root_for_project(
    project_dir: Path,
    *,
    workspace_root: Path | None = None,
) -> Path | None:
    """Return a multi-app workspace parent when ``project_dir`` is an immediate child app."""
    if workspace_root is not None:
        resolved = workspace_root.expanduser().resolve()
        if resolved.is_dir():
            return resolved
    parent = project_dir.expanduser().resolve().parent
    if parent.is_dir() and len(discover_flutter_projects(parent)) >= 1:
        return parent
    return env_configured_workspace_root()


def infer_figma_file_key_for_manifest(
    *,
    workspace_root: Path | None = None,
) -> str | None:
    """Resolve a Figma file key for a new empty batch manifest.

    Precedence: any sibling project's ``screens.yaml`` in the workspace →
    ``FIGMA_SMOKE_FILE_KEY`` → file key parsed from ``FIGMA_DEFAULT_URL``.

    Args:
        workspace_root: Optional workspace directory containing Flutter apps.

    Returns:
        File key string, or ``None`` when no source is configured.
    """
    from figma_flutter_agent.batch.manifest import load_batch_manifest
    from figma_flutter_agent.config import load_settings
    from figma_flutter_agent.figma.url import parse_figma_input

    workspace = workspace_root.expanduser().resolve() if workspace_root is not None else None
    if workspace is not None and workspace.is_dir():
        for project in discover_flutter_projects(workspace):
            manifest_path = project / _BATCH_MANIFEST_NAME
            if manifest_path.is_file():
                return load_batch_manifest(manifest_path).file_key

    settings = load_settings()
    smoke_key = (settings.figma_smoke_file_key or "").strip()
    if smoke_key:
        return smoke_key

    default_url = (settings.figma_default_url or "").strip()
    if default_url:
        from figma_flutter_agent.errors import FigmaUrlError

        try:
            return parse_figma_input(default_url).file_key
        except FigmaUrlError:
            logger.warning("FIGMA_DEFAULT_URL is not a valid Figma URL for batch manifest file_key")

    return None


def ensure_batch_manifest(
    project_dir: Path,
    *,
    workspace_root: Path | None = None,
) -> Path:
    """Create an empty ``screens.yaml`` in ``project_dir`` when it is missing.

    Args:
        project_dir: Flutter project root (must contain ``pubspec.yaml``).
        workspace_root: Optional workspace used to inherit ``file_key`` from a sibling app.

    Returns:
        Path to the existing or newly written manifest.

    Raises:
        FlutterProjectError: When the project root is invalid or no file key can be resolved.
    """
    from figma_flutter_agent.batch.manifest import BatchManifest, write_batch_manifest

    root = resolve_project_dir(project_dir)
    manifest_path = root / _BATCH_MANIFEST_NAME
    if manifest_path.is_file():
        return manifest_path

    workspace = _workspace_root_for_project(root, workspace_root=workspace_root)
    file_key = infer_figma_file_key_for_manifest(workspace_root=workspace)
    if not file_key:
        raise FlutterProjectError(
            f"Cannot create {_BATCH_MANIFEST_NAME} at {manifest_path.as_posix()}: "
            "set FIGMA_SMOKE_FILE_KEY or FIGMA_DEFAULT_URL in the agent .env, "
            "or run fetch / batch dump-file on another app in the same workspace first."
        )

    write_batch_manifest(
        manifest_path,
        BatchManifest(file_key=file_key, project_dir=root, screens=()),
    )
    logger.info(
        "Created empty batch manifest at {} (file_key={}); use fetch or batch dump-file to add screens",
        manifest_path.as_posix(),
        file_key,
    )
    return manifest_path


def default_flutter_project_candidate(*, env_project_dir: Path | None = None) -> Path:
    """Return the best default Flutter project root before validation.

    Precedence: resolved project under ``FIGMA_FLUTTER_PROJECT_DIR`` workspace →
    sibling ``demo_app`` → cwd. When the workspace holds multiple apps and no
    active project is persisted, returns the workspace path as a prompt default.

    Args:
        env_project_dir: Optional workspace override; when omitted, reads env.
    """
    workspace = env_project_dir
    if workspace is None:
        workspace = env_configured_workspace_root()

    if workspace is not None:
        workspace = workspace.expanduser().resolve()
        resolved = resolve_active_flutter_project(env_workspace=workspace)
        if resolved is not None:
            return resolved
        if workspace.is_dir() and not is_flutter_project_root(workspace):
            projects = discover_flutter_projects(workspace)
            if projects:
                return projects[0]

    ordered: list[Path] = []
    if workspace is not None:
        ordered.append(workspace)
    sibling = (_agent_repo_root().parent / "demo_app").resolve()
    if sibling not in ordered:
        ordered.append(sibling)
    cwd = Path(".").resolve()
    if cwd not in ordered:
        ordered.append(cwd)

    for path in ordered:
        if is_flutter_project_root(path):
            return path
    return ordered[0]


def resolve_implicit_project_dir(*, env_project_dir: Path | None = None) -> Path:
    """Resolve implicit ``.`` project dir using env workspace and persisted selection."""
    candidate = default_flutter_project_candidate(env_project_dir=env_project_dir)
    return resolve_project_dir(candidate)


def resolve_project_dir(project_dir: Path) -> Path:
    """Resolve and validate a Flutter project root."""
    root = project_dir.expanduser().resolve()
    if not is_flutter_project_root(root):
        raise FlutterProjectError(f"Flutter project not found at {root}")
    return root


def resolve_manifest_path(
    project_dir: Path,
    *,
    workspace_root: Path | None = None,
) -> Path:
    """Return ``screens.yaml`` inside ``project_dir``, creating an empty manifest when missing."""
    return ensure_batch_manifest(project_dir, workspace_root=workspace_root)


def ensure_project_config(project_dir: Path) -> Path:
    """Validate the Flutter project and return the agent-repo config path."""
    resolve_project_dir(project_dir)
    return resolve_agent_config_path()
