"""Regression tests for compact published component drawable export coverage."""

from __future__ import annotations

import pytest

from figma_flutter_agent.assets.collect import collect_exportable_nodes
from figma_flutter_agent.assets.composite_icons import (
    collect_figma_composite_icon_groups,
    drawable_asset_covers_descendant_vectors,
    is_figma_compact_component_drawable_node,
)
from figma_flutter_agent.assets.vector_binding import collect_unbound_visible_vector_ids
from figma_flutter_agent.errors import MissingVectorAssetError
from figma_flutter_agent.generator.widget_extractor import render_cluster_widgets
from figma_flutter_agent.generator.widget_models import ClusterWidgetSpec
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeStyle, NodeType, Sizing


def _status_icon_instance(
    *,
    instance_id: str,
    vector_id: str,
    component_id: str,
    name: str,
) -> dict:
    return {
        "id": instance_id,
        "type": "INSTANCE",
        "visible": True,
        "name": name,
        "componentId": component_id,
        "absoluteBoundingBox": {"width": 16.0, "height": 16.0},
        "children": [
            {
                "id": vector_id,
                "type": "VECTOR",
                "visible": True,
                "name": "Vector",
                "absoluteBoundingBox": {"width": 13.3, "height": 13.3},
                "fills": [
                    {
                        "type": "SOLID",
                        "visible": True,
                        "color": {"r": 1.0, "g": 1.0, "b": 1.0, "a": 1.0},
                    }
                ],
            }
        ],
    }


def test_compact_component_instance_detected_as_drawable_export_root() -> None:
    """Law: CompactComponentDrawableCoverageLaw — single-vector component instances export whole."""
    node = _status_icon_instance(
        instance_id="I2399:42783;266:1499;266:1646",
        vector_id="I2399:42783;266:1499;266:1646;339:8061",
        component_id="282:23327",
        name="Signal",
    )
    assert is_figma_compact_component_drawable_node(node)


def test_status_icon_cohort_exports_component_hosts_not_leaf_vectors() -> None:
    """Law: status icon cohort exports Wifi/Signal/Battery hosts, not nested vectors."""
    signal = _status_icon_instance(
        instance_id="I2399:42783;266:1499;266:1646",
        vector_id="I2399:42783;266:1499;266:1646;339:8061",
        component_id="282:23327",
        name="Signal",
    )
    wifi = _status_icon_instance(
        instance_id="I2399:42783;266:1499;266:1645",
        vector_id="I2399:42783;266:1499;266:1645;346:8257",
        component_id="282:23343",
        name="Wifi",
    )
    battery = _status_icon_instance(
        instance_id="I2399:42783;266:1499;266:1648",
        vector_id="I2399:42783;266:1499;266:1648;348:8871",
        component_id="282:23346",
        name="Battery",
    )
    root = {
        "id": "0:1",
        "type": "FRAME",
        "visible": True,
        "name": "Status Icons",
        "children": [signal, wifi, battery],
    }
    parents, skip = collect_figma_composite_icon_groups(root)
    assert parents == frozenset(
        {
            "I2399:42783;266:1499;266:1646",
            "I2399:42783;266:1499;266:1645",
            "I2399:42783;266:1499;266:1648",
        }
    )
    assert skip == frozenset(
        {
            "I2399:42783;266:1499;266:1646;339:8061",
            "I2399:42783;266:1499;266:1645;346:8257",
            "I2399:42783;266:1499;266:1648;348:8871",
        }
    )
    items = collect_exportable_nodes(root, exclude_node_ids={"0:1"})
    icon_ids = {node_id for node_id, _name, kind in items if kind == "icon"}
    assert icon_ids == set(parents)
    assert skip.isdisjoint(icon_ids)


def test_ancestor_drawable_asset_covers_descendant_vectors() -> None:
    """Law: ancestor drawable SVG covers baked descendant vector paint."""
    host = CleanDesignTreeNode(
        id="I_test;signal",
        name="Signal",
        type=NodeType.STACK,
        sizing=Sizing(width=16.0, height=16.0),
        component_ref="282:23327",
        vector_asset_key="assets/icons/signal_host.svg",
        children=[
            CleanDesignTreeNode(
                id="I_test;signal;vector",
                name="Vector",
                type=NodeType.VECTOR,
                sizing=Sizing(width=13.3, height=13.3),
                style=NodeStyle(background_color="0xFFFFFFFF"),
            )
        ],
    )
    assert drawable_asset_covers_descendant_vectors(host)
    assert collect_unbound_visible_vector_ids(host) == []


def test_cluster_widget_parent_asset_materializes_without_child_key() -> None:
    """Law: cluster compact component host SVG satisfies descendant vector conservation."""
    host = CleanDesignTreeNode(
        id="I_test;signal",
        name="Signal",
        type=NodeType.STACK,
        sizing=Sizing(width=16.0, height=16.0),
        component_ref="282:23327",
        vector_asset_key="assets/icons/signal_host.svg",
        children=[
            CleanDesignTreeNode(
                id="I_test;signal;vector",
                name="Vector",
                type=NodeType.VECTOR,
                sizing=Sizing(width=13.3, height=13.3),
                style=NodeStyle(background_color="0xFFFFFFFF"),
            )
        ],
    )
    spec = ClusterWidgetSpec(
        cluster_id="component_282_23327",
        class_name="CellularSignalIconWidget",
        file_name="cellular_signal_icon_widget",
        representative=host,
    )
    result = render_cluster_widgets([spec], uses_svg=True, clean_trees=[host])
    source = result.files["lib/widgets/cellular_signal_icon_widget.dart"]
    assert "SvgPicture" in source
    assert "SizedBox.shrink()" not in source


def _quantity_stepper_control(
    *,
    control_id: str,
    icon_id: str,
    vector_id: str,
    control_component_id: str,
    icon_component_id: str,
    icon_name: str,
) -> dict:
    return {
        "id": control_id,
        "type": "INSTANCE",
        "visible": True,
        "name": "Add product",
        "componentId": control_component_id,
        "absoluteBoundingBox": {"width": 36.0, "height": 36.0},
        "fills": [
            {
                "type": "SOLID",
                "visible": True,
                "color": {"r": 0.23, "g": 0.23, "b": 0.24, "a": 1.0},
            }
        ],
        "children": [
            {
                "id": icon_id,
                "type": "INSTANCE",
                "visible": True,
                "name": icon_name,
                "componentId": icon_component_id,
                "absoluteBoundingBox": {"width": 28.0, "height": 28.0},
                "children": [
                    {
                        "id": vector_id,
                        "type": "VECTOR",
                        "visible": True,
                        "name": "Vector",
                        "absoluteBoundingBox": {"width": 18.7, "height": 18.7},
                        "fills": [
                            {
                                "type": "SOLID",
                                "visible": True,
                                "color": {"r": 1.0, "g": 1.0, "b": 1.0, "a": 1.0},
                            }
                        ],
                    }
                ],
            }
        ],
    }


def test_nested_quantity_stepper_exports_icon_hosts_not_control_wrappers() -> None:
    """Law: nested compact control defers export root to inner Icons/* component hosts."""
    minus = _quantity_stepper_control(
        control_id="I_test;stepper;minus_control",
        icon_id="I_test;stepper;minus_icon",
        vector_id="I_test;stepper;minus_icon;vector",
        control_component_id="1149:9478",
        icon_component_id="910:3262",
        icon_name="Icons/28/Minus",
    )
    plus = _quantity_stepper_control(
        control_id="I_test;stepper;plus_control",
        icon_id="I_test;stepper;plus_icon",
        vector_id="I_test;stepper;plus_icon;vector",
        control_component_id="1149:9480",
        icon_component_id="910:3249",
        icon_name="Icons/28/Plus",
    )
    root = {
        "id": "0:1",
        "type": "FRAME",
        "visible": True,
        "name": "Stepper",
        "children": [minus, plus],
    }
    parents, skip = collect_figma_composite_icon_groups(root)
    assert parents == frozenset(
        {
            "I_test;stepper;minus_icon",
            "I_test;stepper;plus_icon",
        }
    )
    assert "I_test;stepper;minus_control" not in parents
    assert "I_test;stepper;plus_control" not in parents
    assert skip == frozenset(
        {
            "I_test;stepper;minus_icon;vector",
            "I_test;stepper;plus_icon;vector",
        }
    )
    items = collect_exportable_nodes(root, exclude_node_ids={"0:1"})
    icon_ids = {node_id for node_id, _name, kind in items if kind == "icon"}
    assert icon_ids == set(parents)
    assert skip.isdisjoint(icon_ids)
    from figma_flutter_agent.assets.eligibility import figma_images_api_skip_export

    assert not figma_images_api_skip_export(
        minus["children"][0],
        node_id=minus["children"][0]["id"],
        composite_parent_ids=parents,
    )
    assert not figma_images_api_skip_export(
        plus["children"][0],
        node_id=plus["children"][0]["id"],
        composite_parent_ids=parents,
    )


def test_cluster_widget_without_any_asset_still_raises() -> None:
    host = CleanDesignTreeNode(
        id="I_test;signal",
        name="Signal",
        type=NodeType.STACK,
        sizing=Sizing(width=16.0, height=16.0),
        component_ref="282:23327",
        children=[
            CleanDesignTreeNode(
                id="I_test;signal;vector",
                name="Vector",
                type=NodeType.VECTOR,
                sizing=Sizing(width=13.3, height=13.3),
                style=NodeStyle(background_color="0xFFFFFFFF"),
            )
        ],
    )
    spec = ClusterWidgetSpec(
        cluster_id="component_282_23327",
        class_name="CellularSignalIconWidget",
        file_name="cellular_signal_icon_widget",
        representative=host,
    )
    with pytest.raises(MissingVectorAssetError, match="I_test;signal;vector"):
        render_cluster_widgets([spec], uses_svg=True, clean_trees=[host])
