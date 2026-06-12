"""Oracle fields on tests/fixtures/screens.yaml manifest."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from figma_flutter_agent.fixtures.screens_manifest import (
    ScreenFixtureEntry,
    blocking_screens,
    load_screens_manifest,
)


def test_manifest_loads_with_oracle_defaults() -> None:
    manifest = load_screens_manifest()
    assert len(manifest.screens) == 10
    bounded = next(item for item in manifest.screens if item.id == "bounded_order_card")
    assert bounded.corpus_tier == "advisory_pixel"
    assert bounded.thresholds.non_text_pixel_max == 0.05


def test_blocking_screens_have_goldens() -> None:
    blocking = blocking_screens()
    assert len(blocking) == 4
    assert all(item.golden_id is not None for item in blocking)


def test_strict_blocking_requires_golden_id() -> None:
    with pytest.raises(ValidationError):
        ScreenFixtureEntry(
            id="bad",
            layout="layouts/x.json",
            feature="x",
            corpus_tier="strict_pixel_blocking",
        )


def test_semantic_only_defaults_to_semantic_oracle_mode() -> None:
    manifest = load_screens_manifest()
    consent = next(item for item in manifest.screens if item.id == "consent_checkbox")
    assert consent.corpus_tier == "semantic_only"
    assert consent.oracle_modes == ["semantic"]


def test_semantic_only_rejects_explicit_pixel_oracle_modes() -> None:
    with pytest.raises(ValidationError):
        ScreenFixtureEntry(
            id="bad",
            layout="layouts/x.json",
            feature="x",
            corpus_tier="semantic_only",
            oracle_modes=["semantic", "strict_pixel"],
        )
