"""Patch project ``.ai-figma-flutter.yml`` with the showcase optional-features profile."""

from __future__ import annotations

from pathlib import Path

from ruamel.yaml import YAML

_SHOWCASE_PATCH: dict[str, object] = {
    "state_management": {"type": "riverpod"},
    "dark_mode": {"enabled": True},
    "ux": {"suggestions": True, "write_report": True},
    "animations": {"write_manifest": True},
    "routing": {"type": "go_router", "generate_destinations": True},
}


def apply_showcase_yaml(project_dir: Path) -> Path:
    """Merge showcase settings into the Flutter project agent config."""
    config_path = project_dir / ".ai-figma-flutter.yml"
    if not config_path.is_file():
        msg = f"Missing {config_path.name} in {project_dir.as_posix()}"
        raise FileNotFoundError(msg)

    yaml = YAML()
    yaml.preserve_quotes = True
    data = yaml.load(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        msg = f"Invalid YAML root in {config_path.as_posix()}"
        raise ValueError(msg)

    for key, value in _SHOWCASE_PATCH.items():
        section = data.get(key)
        if isinstance(section, dict) and isinstance(value, dict):
            section.update(value)
        else:
            data[key] = value

    with config_path.open("w", encoding="utf-8", newline="\n") as handle:
        yaml.dump(data, handle)
    return config_path
