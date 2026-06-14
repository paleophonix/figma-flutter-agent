"""Vector export eligibility diagnostics."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.assets.collect import collect_exportable_nodes
from figma_flutter_agent.assets.eligibility import explain_export_block
from figma_flutter_agent.assets.screen_frame import build_screen_frame_exclude_ids

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "raw" / "feedback_interactive_icons.json"
_STAR_VECTOR_ID = "211:5818"
_BACK_VECTOR_ID = "109:1874"
_BACK_ICON_PARENT_ID = "164:2038"
_STAR_ICON_PARENT_ID = "259:6571"
_SCREEN_ID = "281:7179"


def _load_fixture() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def test_feedback_vectors_are_composite_skipped_with_export_parent() -> None:
    raw = _load_fixture()
    excludes = set(build_screen_frame_exclude_ids(_SCREEN_ID, set()))

    star_reason = explain_export_block(
        raw,
        _STAR_VECTOR_ID,
        flatten_excludes=set(),
        excludes=excludes,
        boundary_ids=set(),
    )
    back_reason = explain_export_block(
        raw,
        _BACK_VECTOR_ID,
        flatten_excludes=set(),
        excludes=excludes,
        boundary_ids=set(),
    )

    assert star_reason == f"composite_skip:parent={_STAR_ICON_PARENT_ID}"
    assert back_reason == f"composite_skip:parent={_BACK_ICON_PARENT_ID}"


def test_icon_vector_inside_interactive_parent_is_exported() -> None:
    raw = {
        "id": "0:1",
        "type": "FRAME",
        "visible": True,
        "name": "Screen",
        "children": [
            {
                "id": "1:0",
                "type": "INSTANCE",
                "visible": True,
                "name": "Back Button",
                "absoluteBoundingBox": {"width": 48.0, "height": 48.0},
                "children": [
                    {
                        "id": "1:1",
                        "type": "VECTOR",
                        "visible": True,
                        "name": "Vector",
                        "absoluteBoundingBox": {"width": 16.0, "height": 16.0},
                        "fills": [
                            {
                                "type": "SOLID",
                                "visible": True,
                                "color": {"r": 0, "g": 0, "b": 0, "a": 1},
                            }
                        ],
                    }
                ],
            }
        ],
    }
    items = collect_exportable_nodes(raw, exclude_node_ids={"0:1"})
    icon_ids = {node_id for node_id, _name, kind in items if kind == "icon"}
    assert "1:1" in icon_ids


def test_feedback_icon_parents_are_exportable() -> None:
    raw = _load_fixture()
    excludes = set(build_screen_frame_exclude_ids(_SCREEN_ID, set()))
    items = collect_exportable_nodes(raw, exclude_node_ids=excludes)
    icon_ids = {node_id for node_id, _name, kind in items if kind == "icon"}
    assert _BACK_ICON_PARENT_ID in icon_ids
    assert _STAR_ICON_PARENT_ID in icon_ids
