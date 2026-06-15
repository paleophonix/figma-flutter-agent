"""Pixel fidelity profile policy (Wave E / U2)."""

from __future__ import annotations

from figma_flutter_agent.config.profiles import (
    apply_pixel_fidelity_overrides,
    apply_pixel_fidelity_profile,
    apply_production_profile,
)
from figma_flutter_agent.config.settings import Settings


def test_pixel_fidelity_profile_static_responsive() -> None:
    settings = apply_pixel_fidelity_profile(Settings())
    responsive = settings.agent.responsive
    assert responsive.mode == "static"
    assert responsive.enabled is False
    assert settings.agent.layout.snap_device_pixels is True
    generation = settings.agent.generation
    assert generation.pixel_fidelity is True
    assert generation.geometry_precision == "full"
    assert generation.preserve_placement is True
    assert generation.promote_soft_pixel_invariants is True


def test_production_profile_keeps_responsive_reflow() -> None:
    settings = apply_production_profile(Settings())
    assert settings.agent.responsive.mode == "responsive"
    assert settings.agent.responsive.enabled is True
    assert settings.agent.generation.pixel_fidelity is False


def test_pixel_fidelity_overrides_on_top_of_production() -> None:
    settings = apply_pixel_fidelity_overrides(apply_production_profile(Settings()))
    assert settings.agent.responsive.mode == "static"
    assert settings.agent.quality.strict_contrast is True
    assert settings.agent.generation.pixel_fidelity is True
