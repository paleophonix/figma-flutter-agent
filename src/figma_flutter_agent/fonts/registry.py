"""Load and query the declarative font substitution registry."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

_REGISTRY_PATH = Path(__file__).resolve().parent / "data" / "font-registry.v1.yaml"

_WEIGHT_SUFFIX_RE = re.compile(
    r"(?i)[-_\s]?(thin|extralight|ultralight|light|regular|book|medium|semibold|demibold|"
    r"bold|extrabold|ultrabold|black|heavy|italic|oblique)$"
)
_LINOTYPE_NUMBER_RE = re.compile(r"(?i)\s+\d{2,3}\s+(bold|light|medium|regular)$")
_VARIABLE_TAG_RE = re.compile(r"(?i)\s+(variable|vf)\b")
_COMMERCE_SUFFIX_RE = re.compile(r"(?i)\s+(pro|std|com|neue)$")
_BRACKET_AXIS_RE = re.compile(r"\s*\[[^\]]+\]")
_PROJECT_PREFIX_RE = re.compile(r"^[a-z0-9]+[-_]", re.IGNORECASE)
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class NormalizationRule:
    """One regex replacement applied during family normalization."""

    id: str
    pattern: str
    replacement: str


@dataclass(frozen=True)
class WeightProfile:
    """Maps Figma/Flutter weight tokens to download and codegen overrides."""

    id: str
    download_weight_map: dict[str, str] = field(default_factory=dict)
    pubspec_weight_map: dict[str, int] = field(default_factory=dict)
    dart_weight_overrides: dict[str, str] = field(default_factory=dict)

    def effective_download_weight_token(self, font_weight: str) -> str:
        """Return the weight token used when fetching a font file."""
        return self.download_weight_map.get(font_weight, font_weight)

    def effective_pubspec_weight(self, font_weight: str) -> int:
        """Return the pubspec.yaml weight for a Flutter weight token."""
        if font_weight in self.pubspec_weight_map:
            return self.pubspec_weight_map[font_weight]
        return int(font_weight.removeprefix("w"))

    def dart_weight_override(self, font_weight: str) -> str | None:
        """Return a Dart ``FontWeight`` override token such as ``w700``."""
        return self.dart_weight_overrides.get(font_weight)


@dataclass(frozen=True)
class BundledWeightSpec:
    """Direct URL bundle entry for one weight/style pair."""

    url: str
    weight: int
    asset_name: str
    style: str | None = None


@dataclass(frozen=True)
class FontFamilyEntry:
    """Registry row for one substitute family."""

    id: str
    keys: tuple[str, ...]
    pubspec_family: str
    strategy: str
    profile_id: str
    priority: str
    substitute_name: str | None = None
    gwfh_slug: str | None = None
    bundled_weights: dict[str, BundledWeightSpec] = field(default_factory=dict)


@dataclass(frozen=True)
class FontRegistry:
    """Parsed font-registry.v1.yaml payload."""

    version: str
    global_fallback_slug: str
    normalization_rules: tuple[NormalizationRule, ...]
    profiles: dict[str, WeightProfile]
    families: tuple[FontFamilyEntry, ...]
    key_index: dict[str, FontFamilyEntry]
    pubspec_index: dict[str, FontFamilyEntry]

    def lookup(self, raw_family: str) -> FontFamilyEntry | None:
        """Find a registry row for a raw or normalized Figma family key."""
        normalized = normalize_figma_family_key(raw_family, self.normalization_rules)
        compact = _NON_ALNUM_RE.sub("", normalized)
        for candidate in (normalized, compact):
            entry = self.key_index.get(candidate)
            if entry is not None:
                return entry
        return None

    def profile_for_family(self, raw_family: str) -> WeightProfile | None:
        """Return the weight profile bound to a Figma family, if any."""
        entry = self.lookup(raw_family)
        if entry is None:
            return None
        return self.profiles.get(entry.profile_id)

    def profile_for_pubspec_family(self, pubspec_family: str) -> WeightProfile | None:
        """Return the weight profile for a pubspec family name."""
        entry = self.pubspec_index.get(pubspec_family.strip().lower())
        if entry is None:
            return None
        return self.profiles.get(entry.profile_id)

    def google_slug_aliases(self) -> dict[str, str]:
        """Build normalized-key → gwfh slug map for resolver lookups."""
        aliases: dict[str, str] = {}
        for family in self.families:
            if not family.gwfh_slug:
                continue
            for key in family.keys:
                aliases[_NON_ALNUM_RE.sub("", key)] = family.gwfh_slug
                aliases[key.strip().lower()] = family.gwfh_slug
        return aliases

    def pubspec_family_aliases(self) -> dict[str, str]:
        """Build normalized-key → pubspec family map for Google substitutes."""
        aliases: dict[str, str] = {}
        for family in self.families:
            if family.strategy not in {"google_substitute", "noto_fallback", "bundled"}:
                continue
            for key in family.keys:
                aliases[_NON_ALNUM_RE.sub("", key)] = family.pubspec_family
                aliases[key.strip().lower()] = family.pubspec_family
        return aliases

    def figma_to_pubspec_aliases(self) -> dict[str, str]:
        """Build alias map for ``normalize_figma_family`` (display names)."""
        aliases: dict[str, str] = {}
        for family in self.families:
            for key in family.keys:
                aliases[key.strip().lower()] = family.pubspec_family
                aliases[_NON_ALNUM_RE.sub("", key)] = family.pubspec_family
        return aliases


def normalize_figma_family_key(
    raw: str,
    rules: tuple[NormalizationRule, ...] | None = None,
) -> str:
    """Normalize a Figma ``fontFamily`` string for registry lookup.

    Args:
        raw: Raw family string from Figma metadata.
        rules: Optional rule set; defaults to the loaded registry rules.

    Returns:
        Normalized lowercase lookup key.
    """
    registry = load_font_registry()
    active_rules = rules if rules is not None else registry.normalization_rules
    value = raw.strip().lower()
    if value.startswith("."):
        value = value.lstrip(".")
    value = _NON_ALNUM_RE.sub(" ", value)
    value = re.sub(r"\s+", " ", value).strip()
    if value in {"system-ui", "-apple-system"}:
        value = "sf pro text"
    value = _MONOSPACE_ALIASES.get(value, value)
    for rule in active_rules:
        value = re.sub(rule.pattern, rule.replacement, value).strip()
    value = _WEIGHT_SUFFIX_RE.sub("", value).strip()
    value = _VARIABLE_TAG_RE.sub("", value).strip()
    value = _COMMERCE_SUFFIX_RE.sub("", value).strip()
    value = _LINOTYPE_NUMBER_RE.sub("", value).strip()
    value = _BRACKET_AXIS_RE.sub("", value).strip()
    value = _PROJECT_PREFIX_RE.sub("", value).strip()
    value = re.sub(r"\s+", " ", value).strip()
    return value


_MONOSPACE_ALIASES = {
    "sfmono-regular": "sf mono",
    "sfmono": "sf mono",
    "couriernewpsmt": "courier new",
}


def _parse_bundled_weights(raw: dict[str, Any]) -> dict[str, BundledWeightSpec]:
    parsed: dict[str, BundledWeightSpec] = {}
    for token, spec in raw.items():
        parsed[token] = BundledWeightSpec(
            url=str(spec["url"]),
            weight=int(spec["weight"]),
            asset_name=str(spec["asset_name"]),
            style=spec.get("style"),
        )
    return parsed


def _parse_registry_payload(payload: dict[str, Any]) -> FontRegistry:
    rules = tuple(
        NormalizationRule(
            id=str(item["id"]),
            pattern=str(item["pattern"]),
            replacement=str(item.get("replacement", "")),
        )
        for item in payload.get("normalization_rules", [])
    )
    profiles: dict[str, WeightProfile] = {}
    for profile_id, item in payload.get("profiles", {}).items():
        profiles[profile_id] = WeightProfile(
            id=profile_id,
            download_weight_map={
                str(k): str(v) for k, v in item.get("download_weight_map", {}).items()
            },
            pubspec_weight_map={
                str(k): int(v) for k, v in item.get("pubspec_weight_map", {}).items()
            },
            dart_weight_overrides={
                str(k): str(v) for k, v in item.get("dart_weight_overrides", {}).items()
            },
        )
    families: list[FontFamilyEntry] = []
    key_index: dict[str, FontFamilyEntry] = {}
    pubspec_index: dict[str, FontFamilyEntry] = {}
    for item in payload.get("families", []):
        entry = FontFamilyEntry(
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
        families.append(entry)
        for key in entry.keys:
            normalized = key.strip().lower()
            key_index[normalized] = entry
            key_index[_NON_ALNUM_RE.sub("", normalized)] = entry
        pubspec_index[entry.pubspec_family.strip().lower()] = entry
    return FontRegistry(
        version=str(payload.get("version", "1.0.0")),
        global_fallback_slug=str(payload.get("global_fallback_slug", "noto-sans")),
        normalization_rules=rules,
        profiles=profiles,
        families=tuple(families),
        key_index=key_index,
        pubspec_index=pubspec_index,
    )


@lru_cache(maxsize=1)
def load_font_registry(path: Path | None = None) -> FontRegistry:
    """Load and cache the font registry YAML file.

    Args:
        path: Optional override path (used in tests).

    Returns:
        Parsed ``FontRegistry`` instance.
    """
    registry_path = path or _REGISTRY_PATH
    yaml = YAML(typ="safe")
    with registry_path.open(encoding="utf-8") as handle:
        payload = yaml.load(handle)
    if not isinstance(payload, dict):
        msg = f"Font registry at {registry_path} must be a mapping."
        raise ValueError(msg)
    return _parse_registry_payload(payload)


def clear_registry_cache() -> None:
    """Clear cached registry data (for tests)."""
    load_font_registry.cache_clear()
