"""Persist interactive wizard preferences for workspace and Flutter projects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ruamel.yaml import YAML

from figma_flutter_agent.debug.migrate import (
    ensure_project_debug_layout,
    ensure_workspace_debug_layout,
)
from figma_flutter_agent.debug.paths import (
    legacy_workspace_prefs_path,
    project_wizard_prefs_path,
    workspace_prefs_path,
)


@dataclass(frozen=True)
class WizardPrefs:
    """Disk-backed wizard selections for one Flutter project."""

    active_screen: str | None = None


@dataclass(frozen=True)
class WorkspacePrefs:
    """Disk-backed active Flutter project under a workspace root."""

    active_project: str | None = None


def wizard_prefs_path(project_dir: Path) -> Path:
    """Return the wizard prefs file path at the Flutter project root."""
    return project_wizard_prefs_path(project_dir)


def load_wizard_prefs(project_dir: Path) -> WizardPrefs:
    """Load persisted wizard prefs for ``project_dir``.

    Args:
        project_dir: Flutter project root containing ``pubspec.yaml``.

    Returns:
        Parsed prefs, or empty defaults when the file is missing or invalid.
    """
    ensure_project_debug_layout(project_dir)
    path = wizard_prefs_path(project_dir)
    if not path.is_file():
        return WizardPrefs()
    yaml = YAML(typ="safe")
    payload = yaml.load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return WizardPrefs()
    raw = payload.get("active_screen")
    if raw is None:
        return WizardPrefs()
    active = str(raw).strip()
    return WizardPrefs(active_screen=active or None)


def load_workspace_prefs(workspace_root: Path) -> WorkspacePrefs:
    """Load persisted active Flutter project for a workspace directory.

    Args:
        workspace_root: Directory from ``FIGMA_FLUTTER_PROJECT_DIR`` (may contain
            multiple Flutter apps as immediate child folders).

    Returns:
        Parsed prefs, or empty defaults when the file is missing or invalid.
    """
    ensure_workspace_debug_layout(workspace_root)
    path = workspace_prefs_path(workspace_root)
    if not path.is_file():
        legacy_path = legacy_workspace_prefs_path(workspace_root)
        if legacy_path.is_file():
            path = legacy_path
        else:
            return WorkspacePrefs()
    yaml = YAML(typ="safe")
    payload = yaml.load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return WorkspacePrefs()
    raw = payload.get("active_project")
    if raw is None:
        return WorkspacePrefs()
    active = str(raw).strip()
    return WorkspacePrefs(active_project=active or None)


def save_workspace_prefs(workspace_root: Path, *, active_project: str | None) -> None:
    """Persist the active Flutter project slug/path for a workspace.

    Args:
        workspace_root: Parent directory that contains one or more Flutter apps.
        active_project: Path relative to ``workspace_root``, or ``None`` to clear.
    """
    path = workspace_prefs_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    yaml.default_flow_style = False
    payload: dict[str, str] = {}
    if active_project:
        payload["active_project"] = active_project
    with path.open("w", encoding="utf-8") as handle:
        yaml.dump(payload, handle)


def save_wizard_prefs(project_dir: Path, *, active_screen: str | None) -> None:
    """Persist wizard prefs for ``project_dir``.

    Args:
        project_dir: Flutter project root containing ``pubspec.yaml``.
        active_screen: Feature slug to remember, or ``None`` to clear it.
    """
    path = wizard_prefs_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    yaml.default_flow_style = False
    payload: dict[str, str] = {}
    if active_screen:
        payload["active_screen"] = active_screen
    with path.open("w", encoding="utf-8") as handle:
        yaml.dump(payload, handle)
