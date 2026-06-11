"""Backward-compatible facade for fidelity manifest loading (EPIC 4.5)."""

from figma_flutter_agent.generator.ir.fidelity.manifest import (
    DEFAULT_FEATURE_PROFILE,
    FidelityManifest,
    ManifestEntry,
    ResolvedTier,
    default_fidelity_manifest,
    feature_profile_from_theme,
    load_fidelity_manifest,
    package_fidelity_manifest_path,
)

# Legacy alias used by older imports.
KindFidelityEntry = ManifestEntry

__all__ = [
    "DEFAULT_FEATURE_PROFILE",
    "FidelityManifest",
    "KindFidelityEntry",
    "ManifestEntry",
    "ResolvedTier",
    "default_fidelity_manifest",
    "feature_profile_from_theme",
    "load_fidelity_manifest",
    "package_fidelity_manifest_path",
]
