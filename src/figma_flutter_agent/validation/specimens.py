"""Typography validation specimen registry (Table E)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

_SPECIMENS_PATH = Path(__file__).resolve().parent / "data" / "font-specimens.v1.yaml"


@dataclass(frozen=True)
class FontValidationSpecimen:
    """One typography specimen block for golden / pixel QA."""

    id: str
    pubspec_family: str
    font_weight: str
    font_size: float
    text: str
    width: int
    height: int
    line_height: float | None = None
    letter_spacing: float | None = None
    max_changed_pixel_ratio: float = 0.05


@dataclass(frozen=True)
class FontSpecimenRegistry:
    """Loaded typography specimen definitions."""

    version: str
    specimens: tuple[FontValidationSpecimen, ...]


def _parse_specimen(item: dict[str, Any]) -> FontValidationSpecimen:
    return FontValidationSpecimen(
        id=str(item["id"]),
        pubspec_family=str(item["pubspec_family"]),
        font_weight=str(item["font_weight"]),
        font_size=float(item["font_size"]),
        text=str(item["text"]),
        width=int(item["width"]),
        height=int(item["height"]),
        line_height=float(item["line_height"]) if item.get("line_height") is not None else None,
        letter_spacing=float(item["letter_spacing"])
        if item.get("letter_spacing") is not None
        else None,
        max_changed_pixel_ratio=float(item.get("max_changed_pixel_ratio", 0.05)),
    )


@lru_cache(maxsize=1)
def load_font_specimens(path: Path | None = None) -> FontSpecimenRegistry:
    """Load and cache typography validation specimens.

    Args:
        path: Optional override path (for tests).

    Returns:
        Parsed specimen registry.
    """
    specimens_path = path or _SPECIMENS_PATH
    yaml = YAML(typ="safe")
    with specimens_path.open(encoding="utf-8") as handle:
        payload = yaml.load(handle)
    if not isinstance(payload, dict):
        msg = f"Font specimens at {specimens_path} must be a mapping."
        raise ValueError(msg)
    specimens = tuple(_parse_specimen(item) for item in payload.get("specimens", []))
    return FontSpecimenRegistry(
        version=str(payload.get("version", "1.0.0")),
        specimens=specimens,
    )


def clear_specimen_cache() -> None:
    """Clear cached specimen data (for tests)."""
    load_font_specimens.cache_clear()
