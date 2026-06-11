"""Load kind-level fidelity promotion manifest for EPIC 3.3."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from figma_flutter_agent.schemas import FidelityTier, WidgetIrKind

_DEFAULT_MANIFEST = (
    Path(__file__).resolve().parents[4]
    / "tests"
    / "fixtures"
    / "semantics"
    / "fidelity_manifest.yaml"
)


@dataclass(frozen=True)
class KindFidelityEntry:
    """Manifest row for one semantic kind."""

    kind: WidgetIrKind
    default_tier: FidelityTier
    fixture_ids: tuple[str, ...]
    epsilon: float | None = None


@dataclass(frozen=True)
class FidelityManifest:
    """Kind-level default tiers for semantic IR stamping."""

    kinds: dict[WidgetIrKind, KindFidelityEntry]

    def tier_for_kind(self, kind: WidgetIrKind) -> FidelityTier:
        entry = self.kinds.get(kind)
        if entry is None:
            return FidelityTier.NATIVE_UNVERIFIED
        return entry.default_tier


def load_fidelity_manifest(path: Path | None = None) -> FidelityManifest:
    """Load fidelity manifest YAML from disk."""
    manifest_path = path or _DEFAULT_MANIFEST
    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    kinds: dict[WidgetIrKind, KindFidelityEntry] = {}
    for kind_name, payload in (raw.get("kinds") or {}).items():
        kind = WidgetIrKind(kind_name)
        kinds[kind] = KindFidelityEntry(
            kind=kind,
            default_tier=FidelityTier(payload.get("default_tier", "native_unverified")),
            fixture_ids=tuple(payload.get("fixture_ids") or ()),
            epsilon=payload.get("epsilon"),
        )
    return FidelityManifest(kinds=kinds)


@lru_cache(maxsize=1)
def default_fidelity_manifest() -> FidelityManifest:
    """Cached default manifest for production materialize."""
    if not _DEFAULT_MANIFEST.is_file():
        return FidelityManifest(kinds={})
    return load_fidelity_manifest(_DEFAULT_MANIFEST)
