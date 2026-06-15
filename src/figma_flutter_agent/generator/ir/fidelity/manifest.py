"""Static verification manifest loader and composite tier lookup (EPIC 4.5)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from figma_flutter_agent.schemas import FidelityTier, TierSource, WidgetIrKind

_PACKAGE_MANIFEST = Path(__file__).resolve().parent.parent / "data" / "fidelity_manifest.yaml"
DEFAULT_FEATURE_PROFILE = "material"
WILDCARD_PROFILE = "*"
WILDCARD_VERSION = "*"


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    """Parse a YAML mapping from disk using the project's ruamel dependency."""
    loader = YAML(typ="safe")
    payload = loader.load(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload
    return {}


def feature_profile_from_theme(theme_variant: str) -> str:
    """Map emit theme variant to a manifest feature profile key."""
    lowered = theme_variant.lower()
    if lowered.startswith("cupertino"):
        return "cupertino"
    if "web" in lowered:
        return "web"
    return DEFAULT_FEATURE_PROFILE


@dataclass(frozen=True)
class ManifestEntry:
    """One manifest row keyed by kind, profile, and template version."""

    kind: WidgetIrKind
    feature_profile: str
    template_version: str
    default_tier: FidelityTier
    fixture_ids: tuple[str, ...]
    epsilon: float | None = None


@dataclass(frozen=True)
class ResolvedTier:
    """Tier resolution outcome for stamping."""

    tier: FidelityTier
    tier_source: TierSource
    entry: ManifestEntry | None = None


@dataclass(frozen=True)
class FidelityManifest:
    """Static verification manifest for semantic fidelity tiers."""

    default_tier: FidelityTier
    template_version: str
    entries: tuple[ManifestEntry, ...]
    kinds: dict[WidgetIrKind, ManifestEntry]

    def resolve(
        self,
        kind: WidgetIrKind,
        *,
        feature_profile: str = DEFAULT_FEATURE_PROFILE,
        template_version: str | None = None,
    ) -> ResolvedTier:
        """Resolve tier using composite lookup with profile/version fallbacks."""
        version = template_version or self.template_version
        lookup_keys = (
            (kind, feature_profile, version),
            (kind, feature_profile, WILDCARD_VERSION),
            (kind, WILDCARD_PROFILE, WILDCARD_VERSION),
        )
        index = _entry_index(self.entries)
        for key in lookup_keys:
            entry = index.get(key)
            if entry is not None:
                return ResolvedTier(
                    tier=entry.default_tier,
                    tier_source=TierSource.MANIFEST,
                    entry=entry,
                )
        return ResolvedTier(
            tier=self.default_tier,
            tier_source=TierSource.POLICY_FALLBACK,
            entry=None,
        )

    def tier_for_kind(self, kind: WidgetIrKind) -> FidelityTier:
        """Backward-compatible kind-only lookup using default profile/version."""
        return self.resolve(kind).tier


def _entry_index(
    entries: tuple[ManifestEntry, ...],
) -> dict[tuple[WidgetIrKind, str, str], ManifestEntry]:
    index: dict[tuple[WidgetIrKind, str, str], ManifestEntry] = {}
    for entry in entries:
        index[(entry.kind, entry.feature_profile, entry.template_version)] = entry
    return index


def _parse_entry_row(payload: dict[str, Any]) -> ManifestEntry | None:
    kind_name = payload.get("kind")
    if not kind_name:
        return None
    return ManifestEntry(
        kind=WidgetIrKind(kind_name),
        feature_profile=str(payload.get("feature_profile") or WILDCARD_PROFILE),
        template_version=str(payload.get("template_version") or WILDCARD_VERSION),
        default_tier=FidelityTier(payload.get("default_tier", "native_unverified")),
        fixture_ids=tuple(payload.get("fixture_ids") or ()),
        epsilon=payload.get("epsilon"),
    )


def _parse_legacy_kind_rows(
    kinds_payload: dict[str, Any],
    *,
    feature_profile: str,
    template_version: str,
) -> list[ManifestEntry]:
    rows: list[ManifestEntry] = []
    for kind_name, payload in kinds_payload.items():
        if not isinstance(payload, dict):
            continue
        rows.append(
            ManifestEntry(
                kind=WidgetIrKind(kind_name),
                feature_profile=feature_profile,
                template_version=template_version,
                default_tier=FidelityTier(payload.get("default_tier", "native_unverified")),
                fixture_ids=tuple(payload.get("fixture_ids") or ()),
                epsilon=payload.get("epsilon"),
            ),
        )
    return rows


def load_fidelity_manifest(path: Path | None = None) -> FidelityManifest:
    """Load fidelity manifest YAML from disk."""
    manifest_path = path or _PACKAGE_MANIFEST
    raw = _load_yaml_mapping(manifest_path)
    default_tier = FidelityTier(raw.get("default_tier", "native_unverified"))
    template_version = str(raw.get("template_version", "1"))
    default_profile = str(raw.get("default_feature_profile", DEFAULT_FEATURE_PROFILE))

    entries: list[ManifestEntry] = []
    for row in raw.get("entries") or []:
        if isinstance(row, dict):
            parsed = _parse_entry_row(row)
            if parsed is not None:
                entries.append(parsed)

    legacy_kinds = raw.get("kinds")
    if isinstance(legacy_kinds, dict):
        entries.extend(
            _parse_legacy_kind_rows(
                legacy_kinds,
                feature_profile=default_profile,
                template_version=template_version,
            ),
        )

    kinds_map: dict[WidgetIrKind, ManifestEntry] = {}
    for entry in entries:
        if entry.feature_profile in {DEFAULT_FEATURE_PROFILE, WILDCARD_PROFILE}:
            kinds_map[entry.kind] = entry

    return FidelityManifest(
        default_tier=default_tier,
        template_version=template_version,
        entries=tuple(entries),
        kinds=kinds_map,
    )


def package_fidelity_manifest_path() -> Path:
    """Return the shipped package manifest path."""
    return _PACKAGE_MANIFEST


@lru_cache(maxsize=1)
def default_fidelity_manifest() -> FidelityManifest:
    """Cached default manifest for production materialize."""
    if not _PACKAGE_MANIFEST.is_file():
        return FidelityManifest(
            default_tier=FidelityTier.NATIVE_UNVERIFIED,
            template_version="1",
            entries=(),
            kinds={},
        )
    return load_fidelity_manifest(_PACKAGE_MANIFEST)
