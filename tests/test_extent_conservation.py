"""T2 extent conservation and prefix rounding."""

from __future__ import annotations

from figma_flutter_agent.generator.geometry_planner import extent_conservation_error
from figma_flutter_agent.parser.numeric_rounding import round_axis_prefix


def test_round_axis_prefix_conserves_parent_span() -> None:
    parent = 100.0
    children = [33.333, 33.333, 33.334]
    boundaries = [0.0]
    cursor = 0.0
    for span in children:
        cursor += span
        boundaries.append(cursor)
    boundaries[-1] = parent
    rounded = round_axis_prefix(boundaries)
    segments = [rounded[i + 1] - rounded[i] for i in range(len(rounded) - 1)]
    assert abs(sum(segments) - rounded[-1]) < 1e-9


def test_extent_conservation_error_within_tolerance() -> None:
    parent = 100.0
    children = [50.0, 50.0]
    assert extent_conservation_error(parent, children) <= 0.5


def test_extent_conservation_error_detects_drift() -> None:
    parent = 100.0
    children = [40.0, 40.0]
    assert extent_conservation_error(parent, children) > 0.5
