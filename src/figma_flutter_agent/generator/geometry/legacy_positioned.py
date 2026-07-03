"""Legacy positioned-field geometry (frozen pre-migration consumer path)."""

from __future__ import annotations

import re
from typing import Literal

from figma_flutter_agent.generator.geometry.constraint_algebra import ResolvedAxisGeometry
from figma_flutter_agent.schemas.geometry import StackPlacement

_FIELD_RE = re.compile(r"^\s*(left|right|top|bottom|width|height):\s*([0-9.]+)\s*,?\s*$")


def _parse_positioned_field_map(fields: list[str]) -> dict[str, float]:
    parsed: dict[str, float] = {}
    for field in fields:
        match = _FIELD_RE.match(field)
        if match is not None:
            parsed[match.group(1)] = float(match.group(2))
    return parsed


def _geometry_from_field_map(
    fields: dict[str, float],
    *,
    axis: Literal["horizontal", "vertical"],
    parent_extent: float,
) -> ResolvedAxisGeometry:
    if axis == "horizontal":
        start_keys = ("left",)
        end_keys = ("right",)
        size_key = "width"
    else:
        start_keys = ("top",)
        end_keys = ("bottom",)
        size_key = "height"
    start = fields.get(start_keys[0])
    end_inset = fields.get(end_keys[0])
    extent = fields.get(size_key)
    if start is not None and end_inset is not None:
        end = parent_extent - end_inset
        computed_extent = max(0.0, end - start)
        extent = computed_extent if extent is None else extent
    elif end_inset is not None and extent is not None:
        end = parent_extent - end_inset
        start = end - extent
    elif start is not None and extent is not None:
        end = start + extent
    elif start is not None:
        extent = extent or 0.0
        end = start + extent
    else:
        start = 0.0
        extent = extent or 0.0
        end = start + extent
    center = start + extent / 2.0
    residual = parent_extent - end - start
    return ResolvedAxisGeometry(
        start=start,
        end=end,
        extent=extent,
        center=center,
        residual=residual,
    )


def legacy_axis_geometry_from_positioned(
    placement: StackPlacement,
    *,
    axis: Literal["horizontal", "vertical"],
    target_parent_extent: float,
    parent_height: float | None = None,
) -> ResolvedAxisGeometry:
    """Derive axis geometry via production ``_positioned_fields`` consumer."""
    from figma_flutter_agent.generator.layout.widgets.positioned import _positioned_fields

    fields = _positioned_fields(
        placement,
        parent_height=parent_height if axis == "vertical" else None,
    )
    parsed = _parse_positioned_field_map(fields)
    return _geometry_from_field_map(
        parsed,
        axis=axis,
        parent_extent=target_parent_extent,
    )
