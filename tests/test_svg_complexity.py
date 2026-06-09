"""FID-46 SVG complexity heuristics."""

from __future__ import annotations

from figma_flutter_agent.assets.optimize import svg_path_element_count
from figma_flutter_agent.generator.layout.widgets import (
    SVG_PATH_RASTER_THRESHOLD,
    _vector_needs_baked_raster,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing


def test_svg_path_element_count() -> None:
    content = "<svg><path/><circle/><rect/></svg>"
    assert svg_path_element_count(content) == 3


def test_vector_needs_baked_raster_when_path_count_exceeds_threshold() -> None:
    node = CleanDesignTreeNode(
        id="1:1",
        name="ComplexIcon",
        type=NodeType.VECTOR,
        sizing=Sizing(width=24.0, height=24.0),
        vector_svg_path_count=SVG_PATH_RASTER_THRESHOLD + 1,
    )
    assert _vector_needs_baked_raster(node) is True
