"""Pixel fidelity policy scopes for geometry precision and invariant severity."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from figma_flutter_agent.config.models import GenerationConfig
from figma_flutter_agent.generator.geometry.invariants.models import (
    promote_soft_pixel_invariants_scope,
)
from figma_flutter_agent.parser.numeric_rounding import geometry_precision_scope


@contextmanager
def pixel_generation_policy_scope(generation: GenerationConfig) -> Iterator[None]:
    """Activate geometry precision and soft-invariant promotion for one plan pass."""
    with (
        geometry_precision_scope(generation.geometry_precision),
        promote_soft_pixel_invariants_scope(generation.promote_soft_pixel_invariants),
    ):
        yield
