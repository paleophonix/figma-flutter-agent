"""Project-level font registry overrides."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from figma_flutter_agent.fonts.registry import (
    _NON_ALNUM_RE,
    FontFamilyEntry,
    WeightProfile,
    _parse_bundled_weights,
)

PROJECT_OVERRIDES_FILENAME = "project-font-overrides.json"


@dataclass(frozen=True)
class ProjectFontOverrides:
    """Optional per-project font substitution overrides."""

    version: str
    families: tuple[FontFamilyEntry, ...]
    family_profiles: dict[str, WeightProfile]
    key_index: dict[str, FontFamilyEntry] = field(default_factory=dict)
    pubspec_index: dict[str, FontFamilyEntry] = field(default_factory=dict)


def _parse_weight_profile(profile_id: str, raw: dict[str, Any]) -> WeightProfile:
    return WeightProfile(
        id=profile_id,
        download_weight_map={str(k): str(v) for k, v in raw.get("download_weight_map", {}).items()},
        pubspec_weight_map={str(k): int(v) for k, v in raw.get("pubspec_weight_map", {}).items()},
        dart_weight_overrides={
            str(k): str(v) for k, v in raw.get("dart_weight_overrides", {}).items()
        },
    )


def _parse_family_entry(item: dict[str, Any]) -> FontFamilyEntry:
    return FontFamilyEntry(
        id=str(item["id"]),
        keys=tuple(str(key) for key in item["keys"]),
        pubspec_family=str(item["pubspec_family"]),
        strategy=str(item["strategy"]),
        profile_id=str(item["profile_id"]),
        priority=str(item.get("priority", "P2")),
        substitute_name=item.get("substitute_name"),
        gwfh_slug=item.get("gwfh_slug"),
        bundled_weights=_parse_bundled_weights(item.get("bundled_weights", {})),
    )


def _index_families(
    families: tuple[FontFamilyEntry, ...],
) -> tuple[dict[str, FontFamilyEntry], dict[str, FontFamilyEntry]]:
    key_index: dict[str, FontFamilyEntry] = {}
    pubspec_index: dict[str, FontFamilyEntry] = {}
    for entry in families:
        for key in entry.keys:
            normalized = key.strip().lower()
            key_index[normalized] = entry
            key_index[_NON_ALNUM_RE.sub("", normalized)] = entry
        pubspec_index[entry.pubspec_family.strip().lower()] = entry
    return key_index, pubspec_index


def load_project_font_overrides(project_dir: Path) -> ProjectFontOverrides | None:
    """Load ``project-font-overrides.json`` from a Flutter project root.

    Args:
        project_dir: Flutter project directory.

    Returns:
        Parsed overrides, or ``None`` when the file is absent.
    """
    path = project_dir / PROJECT_OVERRIDES_FILENAME
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"{PROJECT_OVERRIDES_FILENAME} must be a JSON object."
        raise ValueError(msg)
    families = tuple(_parse_family_entry(item) for item in payload.get("families", []))
    family_profiles: dict[str, WeightProfile] = {}
    for pubspec_family, profile_raw in payload.get("family_profiles", {}).items():
        if not isinstance(profile_raw, dict):
            continue
        family_profiles[pubspec_family.strip().lower()] = _parse_weight_profile(
            f"project:{pubspec_family}",
            profile_raw,
        )
    key_index, pubspec_index = _index_families(families)
    logger.info(
        "Loaded project font overrides from {} ({} families, {} profile patches)",
        path.as_posix(),
        len(families),
        len(family_profiles),
    )
    return ProjectFontOverrides(
        version=str(payload.get("version", "1")),
        families=families,
        family_profiles=family_profiles,
        key_index=key_index,
        pubspec_index=pubspec_index,
    )


def merge_weight_profiles(
    base: WeightProfile | None,
    patch: WeightProfile | None,
) -> WeightProfile | None:
    """Merge global and project-specific weight profile fields.

    Args:
        base: Registry profile.
        patch: Project override profile.

    Returns:
        Combined profile, or ``None`` when both inputs are absent.
    """
    if base is None and patch is None:
        return None
    if base is None:
        return patch
    if patch is None:
        return base
    return WeightProfile(
        id=base.id,
        download_weight_map={**base.download_weight_map, **patch.download_weight_map},
        pubspec_weight_map={**base.pubspec_weight_map, **patch.pubspec_weight_map},
        dart_weight_overrides={**base.dart_weight_overrides, **patch.dart_weight_overrides},
    )
