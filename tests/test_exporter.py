from figma_flutter_agent.assets.exporter import (
    _asset_filename,
    _classify_raster_kind,
    collect_exportable_nodes,
)


def test_asset_filename_includes_node_id_suffix() -> None:
    assert _asset_filename("Home Icon", "12:34", "svg") == "home_icon_12_34.svg"


def test_classify_raster_kind_detects_illustrations() -> None:
    assert _classify_raster_kind("Hero Illustration", illustrations_enabled=True) == "illustration"
    assert _classify_raster_kind("Photo", illustrations_enabled=True) == "image"


def test_collect_exportable_nodes_skips_hidden_nodes() -> None:
    root = {
        "type": "FRAME",
        "id": "1:1",
        "name": "Root",
        "children": [
            {"type": "VECTOR", "id": "2:2", "name": "Visible", "visible": True},
            {"type": "VECTOR", "id": "3:3", "name": "Hidden", "visible": False},
        ],
    }

    items = collect_exportable_nodes(root)

    assert items == [("2:2", "Visible", "icon")]
