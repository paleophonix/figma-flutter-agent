"""Persist interactive wizard preferences inside the Flutter project."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ruamel.yaml import YAML

WIZARD_PREFS_DIR = ".figma-flutter"
WIZARD_PREFS_FILE = "wizard-state.yml"


@dataclass(frozen=True)
class WizardPrefs:
    """Disk-backed wizard selections for one Flutter project."""

    active_screen: str | None = None


def wizard_prefs_path(project_dir: Path) -> Path:
    """Return the wizard prefs file path under ``project_dir/.figma-flutter/``."""
    return project_dir / WIZARD_PREFS_DIR / WIZARD_PREFS_FILE


def load_wizard_prefs(project_dir: Path) -> WizardPrefs:
    """Load persisted wizard prefs for ``project_dir``.

    Args:
        project_dir: Flutter project root containing ``pubspec.yaml``.

    Returns:
        Parsed prefs, or empty defaults when the file is missing or invalid.
    """
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
