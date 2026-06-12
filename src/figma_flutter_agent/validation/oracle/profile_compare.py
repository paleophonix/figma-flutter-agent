"""Compare corpus soft-invariant counts across settings profiles."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from figma_flutter_agent.config import Settings, apply_production_profile
from figma_flutter_agent.fixtures.screens_manifest import (
    ScreenFixtureEntry,
    load_layout_tree,
    load_screens_manifest,
)
from figma_flutter_agent.generator.geometry.invariants.reporting import (
    partition_geometry_violations,
)
from figma_flutter_agent.generator.geometry.invariants.validate import (
    validate_geometry_invariants,
)
from figma_flutter_agent.generator.normalize import normalize_clean_tree


@dataclass(frozen=True)
class ProfileSoftInvariantDiff:
    """Soft-invariant profile diff for one corpus screen."""

    screen_id: str
    dev_counts: dict[str, int]
    production_counts: dict[str, int]
    regressions: dict[str, dict[str, int]]
    hard_failures: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return not self.regressions and not self.hard_failures

    def to_dict(self) -> dict[str, Any]:
        return {
            "screen_id": self.screen_id,
            "dev_counts": self.dev_counts,
            "production_counts": self.production_counts,
            "regressions": self.regressions,
            "hard_failures": list(self.hard_failures),
            "passed": self.passed,
        }


@dataclass(frozen=True)
class ProfileComparisonReport:
    """Aggregate dev-vs-production soft-invariant comparison."""

    passed: bool
    results: tuple[ProfileSoftInvariantDiff, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "results": [item.to_dict() for item in self.results],
        }


def _regressions(
    dev_counts: dict[str, int],
    production_counts: dict[str, int],
) -> dict[str, dict[str, int]]:
    """Return invariant codes whose production count exceeds dev."""
    keys = set(dev_counts) | set(production_counts)
    return {
        key: {
            "dev": dev_counts.get(key, 0),
            "production": production_counts.get(key, 0),
        }
        for key in sorted(keys)
        if production_counts.get(key, 0) > dev_counts.get(key, 0)
    }


def _soft_invariant_counts(
    entry: ScreenFixtureEntry,
    *,
    settings: Settings,
) -> tuple[dict[str, int], tuple[str, ...]]:
    tree = load_layout_tree(entry)
    generation = settings.agent.generation
    try:
        normalized = normalize_clean_tree(
            tree,
            apply_render_safety=True,
            use_geometry_planner=generation.use_geometry_planner,
            strict_geometry_invariants=generation.strict_geometry_invariants,
        )
        violations = validate_geometry_invariants(
            normalized,
            require_layout_slots=generation.use_geometry_planner,
            strict_invariants=generation.strict_geometry_invariants,
        )
    except Exception as exc:
        return {}, (f"{type(exc).__name__}: {exc}",)
    hard, soft = partition_geometry_violations(violations)
    hard_failures = tuple(f"{item.code}@{item.node_id}" for item in hard)
    counts = Counter(item.code for item in soft)
    return dict(sorted(counts.items())), hard_failures


def compare_profile_soft_invariants(
    *,
    screen_ids: list[str] | None = None,
    settings: Settings | None = None,
) -> ProfileComparisonReport:
    """Compare soft invariant counts for dev settings vs production profile."""
    dev_settings = settings or Settings()
    production_settings = apply_production_profile(dev_settings)
    manifest = load_screens_manifest()
    entries = manifest.screens
    if screen_ids is not None:
        wanted = frozenset(screen_ids)
        entries = [entry for entry in entries if entry.id in wanted]

    results: list[ProfileSoftInvariantDiff] = []
    for entry in entries:
        dev_counts, dev_hard = _soft_invariant_counts(entry, settings=dev_settings)
        prod_counts, prod_hard = _soft_invariant_counts(
            entry,
            settings=production_settings,
        )
        hard_failures = dev_hard + tuple(
            failure for failure in prod_hard if failure not in dev_hard
        )
        results.append(
            ProfileSoftInvariantDiff(
                screen_id=entry.id,
                dev_counts=dev_counts,
                production_counts=prod_counts,
                regressions=_regressions(dev_counts, prod_counts),
                hard_failures=hard_failures,
            )
        )
    result_tuple = tuple(results)
    return ProfileComparisonReport(
        passed=all(item.passed for item in result_tuple),
        results=result_tuple,
    )
