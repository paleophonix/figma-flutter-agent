"""Tests for raster fallback node id collection."""

from __future__ import annotations

from figma_flutter_agent.assets.eligibility import collect_raster_fallback_node_ids


def test_collect_raster_fallback_node_ids_nested_composite_only() -> None:
    root = {
        "id": "0:0",
        "type": "FRAME",
        "visible": True,
        "children": [
            {
                "id": "1:1",
                "type": "GROUP",
                "name": "Flat",
                "visible": True,
                "absoluteBoundingBox": {"width": 40, "height": 40},
                "children": [
                    {"id": "1:2", "type": "ELLIPSE", "visible": True},
                    {"id": "1:3", "type": "VECTOR", "visible": True},
                ],
            },
            {
                "id": "2:2",
                "type": "GROUP",
                "name": "Nested",
                "visible": True,
                "absoluteBoundingBox": {"width": 40, "height": 40},
                "children": [
                    {"id": "2:3", "type": "ELLIPSE", "visible": True},
                    {
                        "id": "2:4",
                        "type": "GROUP",
                        "visible": True,
                        "children": [
                            {"id": "2:5", "type": "VECTOR", "visible": True},
                        ],
                    },
                ],
            },
        ],
    }
    assert collect_raster_fallback_node_ids(root) == frozenset({"2:2"})
