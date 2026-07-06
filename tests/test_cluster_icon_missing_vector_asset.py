"""Regression tests for extracted icon clusters without vector assets."""

from __future__ import annotations

import pytest

from figma_flutter_agent.errors import MissingVectorAssetError
from figma_flutter_agent.generator.dart.static_contract_gates import run_static_contract_gates
from figma_flutter_agent.generator.widget_extractor import (
    _bound_cluster_widget_root,
    render_cluster_widgets,
)
from figma_flutter_agent.generator.widget_models import ClusterWidgetSpec
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeStyle, NodeType, Sizing


def _status_icon_stack(*, vector_asset_key: str | None = None) -> CleanDesignTreeNode:
    vector = CleanDesignTreeNode(
        id="I_test;signal;vector",
        name="Vector",
        type=NodeType.VECTOR,
        sizing=Sizing(width=13.3, height=13.3),
        style=NodeStyle(background_color="0xFFFFFFFF"),
        vector_asset_key=vector_asset_key,
    )
    return CleanDesignTreeNode(
        id="I_test;signal",
        name="Signal",
        type=NodeType.STACK,
        sizing=Sizing(width=16.0, height=16.0),
        component_ref="282:23327",
        children=[vector],
    )


def test_cluster_icon_without_asset_raises_missing_vector_asset_error() -> None:
    """Law: visible vectors must not silently shrink inside extracted cluster widgets."""
    node = _status_icon_stack()
    spec = ClusterWidgetSpec(
        cluster_id="component_282_23327",
        class_name="CellularSignalIconWidget",
        file_name="cellular_signal_icon_widget",
        representative=node,
    )
    with pytest.raises(MissingVectorAssetError, match="I_test;signal;vector"):
        render_cluster_widgets([spec], uses_svg=True, clean_trees=[node])


def test_bound_cluster_semantics_shrink_strips_to_dimensioned_box() -> None:
    node = _status_icon_stack()
    bounded = _bound_cluster_widget_root(
        node,
        "Semantics(label: 'Vector', child: const SizedBox.shrink())",
    )
    assert bounded == "SizedBox(width: 16.0, height: 16.0)"
    assert "shrink" not in bounded


def test_cluster_icon_with_vector_asset_passes_static_contract_gate() -> None:
    node = _status_icon_stack(vector_asset_key="assets/icons/test_signal.svg")
    spec = ClusterWidgetSpec(
        cluster_id="component_282_23327",
        class_name="CellularSignalIconWidget",
        file_name="cellular_signal_icon_widget",
        representative=node,
    )
    result = render_cluster_widgets([spec], uses_svg=True, clean_trees=[node])
    source = result.files["lib/widgets/cellular_signal_icon_widget.dart"]
    assert "SvgPicture" in source
    assert "SizedBox.shrink()" not in source
    run_static_contract_gates(result.files)
