"""Merged font resolution context (global registry + project overrides)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from figma_flutter_agent.fonts.overrides import (
    ProjectFontOverrides,
    load_project_font_overrides,
    merge_weight_profiles,
)
from figma_flutter_agent.fonts.registry import (
    _NON_ALNUM_RE,
    FontFamilyEntry,
    FontRegistry,
    WeightProfile,
    load_font_registry,
    normalize_figma_family_key,
)
from figma_flutter_agent.fonts.sources import (
    BundledFontPackage,
    BundledWeightFile,
    pubspec_family_for_google_alias,
    weight_file_key,
)


@dataclass(frozen=True)
class FontResolutionContext:
    """Effective font registry for one generation run."""

    registry: FontRegistry
    project_overrides: ProjectFontOverrides | None = None

    @classmethod
    def for_project(cls, project_dir: Path | None) -> FontResolutionContext:
        """Build a resolution context for ``project_dir``.

        Args:
            project_dir: Flutter project root, or ``None`` for global registry only.

        Returns:
            Context with optional project overrides applied.
        """
        registry = load_font_registry()
        overrides = load_project_font_overrides(project_dir) if project_dir is not None else None
        return cls(registry=registry, project_overrides=overrides)

    def lookup(self, raw_family: str) -> FontFamilyEntry | None:
        """Find a family entry, preferring project overrides."""
        if self.project_overrides is not None:
            normalized = normalize_figma_family_key(raw_family)
            compact = _NON_ALNUM_RE.sub("", normalized)
            for candidate in (normalized, compact, raw_family.strip().lower()):
                entry = self.project_overrides.key_index.get(candidate)
                if entry is not None:
                    return entry
        return self.registry.lookup(raw_family)

    def profile_for_family(self, raw_family: str) -> WeightProfile | None:
        """Return the merged weight profile for a Figma family."""
        entry = self.lookup(raw_family)
        if entry is None:
            return None
        base = self.registry.profiles.get(entry.profile_id)
        patch = None
        if self.project_overrides is not None:
            patch = self.project_overrides.family_profiles.get(entry.pubspec_family.strip().lower())
        return merge_weight_profiles(base, patch)

    def profile_for_pubspec_family(self, pubspec_family: str) -> WeightProfile | None:
        """Return the merged weight profile for a pubspec family name."""
        lookup_key = pubspec_family.strip().lower()
        entry = None
        if self.project_overrides is not None:
            entry = self.project_overrides.pubspec_index.get(lookup_key)
        if entry is None:
            entry = self.registry.pubspec_index.get(lookup_key)
        if entry is None:
            return None
        base = self.registry.profiles.get(entry.profile_id)
        patch = None
        if self.project_overrides is not None:
            patch = self.project_overrides.family_profiles.get(lookup_key)
        return merge_weight_profiles(base, patch)

    def google_slug_aliases(self) -> dict[str, str]:
        """Build slug alias map with project overrides taking precedence."""
        aliases = self.registry.google_slug_aliases()
        if self.project_overrides is None:
            return aliases
        for entry in self.project_overrides.families:
            if not entry.gwfh_slug:
                continue
            for key in entry.keys:
                aliases[key.strip().lower()] = entry.gwfh_slug
                aliases[_NON_ALNUM_RE.sub("", key)] = entry.gwfh_slug
        return aliases

    def pubspec_family_for_figma(self, raw_family: str, metadata_family: str) -> str:
        """Resolve pubspec family name for a Figma/Google pair."""
        entry = self.lookup(raw_family)
        if entry is not None and entry.strategy != "google_direct":
            return entry.pubspec_family
        return pubspec_family_for_google_alias(raw_family, metadata_family)

    def bundled_package(self, pubspec_family: str) -> BundledFontPackage | None:
        """Build a bundled package from registry or project override entries."""
        lookup_key = pubspec_family.strip().lower()
        entry = None
        if self.project_overrides is not None:
            entry = self.project_overrides.pubspec_index.get(lookup_key)
        if entry is None:
            entry = self.registry.pubspec_index.get(lookup_key)
        if entry is None or entry.strategy != "bundled" or not entry.bundled_weights:
            return None
        profile = self.profile_for_pubspec_family(entry.pubspec_family)
        weight_files: dict[str, BundledWeightFile] = {}
        for token, spec in entry.bundled_weights.items():
            style_key = weight_file_key(token, spec.style)
            pubspec_weight = spec.weight
            if profile is not None:
                pubspec_weight = profile.effective_pubspec_weight(token)
            weight_files[style_key] = BundledWeightFile(
                archive_name=Path(spec.url).name,
                asset_name=spec.asset_name,
                weight=pubspec_weight,
                style=spec.style,
                download_url=spec.url,
            )
        return BundledFontPackage(
            pubspec_family=entry.pubspec_family,
            zip_url=None,
            weight_files=weight_files,
        )

    def dart_weight_overrides_for_bundled(
        self, bundled_names: list[str]
    ) -> dict[str, dict[str, str]]:
        """Collect Dart weight overrides for bundled pubspec families."""
        overrides: dict[str, dict[str, str]] = {}
        for name in bundled_names:
            profile = self.profile_for_pubspec_family(name)
            if profile is None or not profile.dart_weight_overrides:
                continue
            overrides[name] = dict(profile.dart_weight_overrides)
        return overrides
