"""Regression tests for cluster spacer widget shrink-shell emit."""

from __future__ import annotations

from figma_flutter_agent.generator.dart.static_contract_gates import run_static_contract_gates
from figma_flutter_agent.generator.widget_extractor import (
    _bound_cluster_widget_root,
    render_cluster_widgets,
)
from figma_flutter_agent.generator.widget_models import ClusterWidgetSpec
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing


def _padding_spacer_node() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="2310:16382",
        name="padding",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=16.0, height=16.0),
        component_ref="6:35",
        cluster_id="component_6_35",
    )


def test_bound_cluster_spacer_emits_dimensioned_box_without_shrink_child() -> None:
    """Law: ExtractedWidgetFixedBoundsLaw — shrink-only spacer roots stay finite without shrink."""
    node = _padding_spacer_node()
    bounded = _bound_cluster_widget_root(node, "const SizedBox.shrink()")
    assert bounded == "SizedBox(width: 16.0, height: 16.0)"
    assert "shrink" not in bounded


def test_bound_cluster_widget_root_preserves_nonempty_child() -> None:
    node = _padding_spacer_node()
    bounded = _bound_cluster_widget_root(node, "const Text('x')")
    assert "child: const Text('x')" in bounded


def test_cluster_spacer_widget_passes_static_contract_gate() -> None:
    node = _padding_spacer_node()
    spec = ClusterWidgetSpec(
        cluster_id="component_6_35",
        class_name="PaddingWidget",
        file_name="padding_widget",
        representative=node,
    )
    result = render_cluster_widgets([spec], uses_svg=True, clean_trees=[node])
    planned = result.files
    source = planned["lib/widgets/padding_widget.dart"]
    assert "SizedBox(width: 16.0, height: 16.0)" in source
    assert "SizedBox.shrink()" not in source
    run_static_contract_gates(planned)
