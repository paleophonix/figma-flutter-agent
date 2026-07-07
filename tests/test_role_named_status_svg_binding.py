"""Regression tests for role-named status icon SVG discovery."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from figma_flutter_agent.generator.widget_extractor import render_cluster_widgets
from figma_flutter_agent.generator.widget_models import ClusterWidgetSpec
from figma_flutter_agent.parser.boundaries.assets import (
    discover_role_named_svg,
    resolve_discovered_vector_asset_keys,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeStyle, NodeType, Sizing


def _status_vector(*, node_id: str, name: str) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name=name,
        type=NodeType.VECTOR,
        sizing=Sizing(width=18.0, height=13.0),
        style=NodeStyle(background_color="0xFF000000"),
        accessibility_label=name,
    )


def test_discover_role_named_svg_maps_status_bar_vectors(tmp_path: Path) -> None:
    icons = tmp_path / "assets" / "icons"
    icons.mkdir(parents=True)
    (icons / "wifi.svg").write_text("<svg></svg>", encoding="utf-8")
    (icons / "connection.svg").write_text("<svg></svg>", encoding="utf-8")
    (icons / "battery.svg").write_text("<svg></svg>", encoding="utf-8")

    wifi = _status_vector(node_id="1:wifi", name="Wifi")
    cellular = _status_vector(node_id="1:cell", name="Cellular Connection")
    cap = _status_vector(node_id="1:cap", name="Cap")

    assert discover_role_named_svg(tmp_path, wifi) == "assets/icons/wifi.svg"
    assert discover_role_named_svg(tmp_path, cellular) == "assets/icons/connection.svg"
    assert discover_role_named_svg(tmp_path, cap) == "assets/icons/battery.svg"


def test_status_bar_cluster_materializes_with_role_named_svgs(tmp_path: Path) -> None:
    icons = tmp_path / "assets" / "icons"
    icons.mkdir(parents=True)
    (icons / "wifi.svg").write_text("<svg></svg>", encoding="utf-8")
    (icons / "connection.svg").write_text("<svg></svg>", encoding="utf-8")
    (icons / "battery.svg").write_text("<svg></svg>", encoding="utf-8")

    representative = CleanDesignTreeNode(
        id="I_test;status",
        name="Status Bar Dynamic Island",
        type=NodeType.STACK,
        sizing=Sizing(width=393.0, height=54.0),
        component_ref="118:6158",
        children=[
            _status_vector(node_id="I_test;wifi", name="Wifi"),
            _status_vector(node_id="I_test;cell", name="Cellular Connection"),
            _status_vector(node_id="I_test;cap", name="Cap"),
        ],
    )
    resolve_discovered_vector_asset_keys(representative, tmp_path)
    spec = ClusterWidgetSpec(
        cluster_id="component_118_6158",
        class_name="StatusBarDynamicIslandWidget",
        file_name="status_bar_dynamic_island_widget",
        representative=representative,
    )
    result = render_cluster_widgets(
        [spec],
        uses_svg=True,
        clean_trees=[representative],
        project_dir=tmp_path,
    )
    source = result.files["lib/widgets/status_bar_dynamic_island_widget.dart"]
    assert "assets/icons/wifi.svg" in source
    assert "assets/icons/connection.svg" in source
    assert "assets/icons/battery.svg" in source
    assert "SizedBox.shrink()" not in source


def test_verbatica_player_status_bar_binds_project_svgs() -> None:
    debug_root = Path(".debug/screen/test/verbatica_player")
    project = Path("apps/test")
    if not (debug_root / "processed.json").is_file():
        pytest.skip("verbatica_player debug bundle unavailable")
    if not (project / "assets/icons/wifi.svg").is_file():
        pytest.skip("role-named status SVGs not present in apps/test")

    proc = json.loads((debug_root / "processed.json").read_text(encoding="utf-8"))
    tree = CleanDesignTreeNode.model_validate(proc["cleanTree"])

    def find(node_id: str) -> CleanDesignTreeNode | None:
        stack = [tree]
        while stack:
            node = stack.pop()
            if node.id == node_id:
                return node
            stack.extend(node.children)
        return None

    host = find("I981:66796;185:29822")
    assert host is not None
    resolve_discovered_vector_asset_keys(host, project)
    wifi = find("I981:66796;185:29822;118:6156")
    cellular = find("I981:66796;185:29822;118:6157")
    cap = find("I981:66796;185:29822;118:6154")
    assert wifi is not None and wifi.vector_asset_key == "assets/icons/wifi.svg"
    assert cellular is not None and cellular.vector_asset_key == "assets/icons/connection.svg"
    assert cap is not None and cap.vector_asset_key == "assets/icons/battery.svg"

    spec = ClusterWidgetSpec(
        cluster_id="component_118_6158_f8acca7f",
        class_name="StatusBarDynamicIslandWidget",
        file_name="status_bar_dynamic_island_widget",
        representative=host,
    )
    result = render_cluster_widgets(
        [spec],
        uses_svg=True,
        clean_trees=[tree],
        project_dir=project,
    )
    source = result.files["lib/widgets/status_bar_dynamic_island_widget.dart"]
    assert "SizedBox.shrink()" not in source
