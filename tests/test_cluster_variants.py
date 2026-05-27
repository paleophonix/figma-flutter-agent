"""Cluster widget variant detection tests."""

from figma_flutter_agent.generator.cluster_variants import (
    cluster_reference_args,
    collect_cluster_vector_variants,
    detect_vector_flip_variant,
    primary_vector_asset,
)
from figma_flutter_agent.generator.widget_extractor import (
    collect_cluster_widget_specs,
    render_cluster_widgets,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeStyle, NodeType, Sizing


def _skip_cluster(*, forward: bool) -> CleanDesignTreeNode:
    asset = "assets/icons/vector_forward.svg" if forward else "assets/icons/vector_backward.svg"
    return CleanDesignTreeNode(
        id="fwd" if forward else "back",
        name="Skip",
        type=NodeType.STACK,
        cluster_id="cluster_0",
        sizing=Sizing(width=31.0, height=36.0),
        children=[
            CleanDesignTreeNode(
                id=f"{'f' if forward else 'b'}:1",
                name="Arrow",
                type=NodeType.VECTOR,
                vector_asset_key=asset,
                sizing=Sizing(width=31.0, height=36.0),
                style=NodeStyle(has_stroke=True),
            ),
            CleanDesignTreeNode(
                id=f"{'f' if forward else 'b'}:2",
                name="15",
                type=NodeType.TEXT,
                text="15",
                sizing=Sizing(width=12.0, height=12.0),
            ),
        ],
    )


def test_detect_vector_flip_variant_for_mirrored_skip_buttons() -> None:
    forward = _skip_cluster(forward=True)
    backward = _skip_cluster(forward=False)
    screen = CleanDesignTreeNode(
        id="1",
        name="Screen",
        type=NodeType.STACK,
        children=[forward, backward],
    )

    variant = detect_vector_flip_variant([screen], "cluster_0", representative=forward)

    assert variant is not None
    assert variant.forward_asset == "assets/icons/vector_forward.svg"
    assert variant.backward_asset == "assets/icons/vector_backward.svg"
    assert cluster_reference_args(backward, variant) == "isForward: false"
    assert cluster_reference_args(forward, variant) == ""


def test_render_cluster_widgets_emits_forward_backward_parameter() -> None:
    forward = _skip_cluster(forward=True)
    backward = _skip_cluster(forward=False)
    screen = CleanDesignTreeNode(
        id="1",
        name="Screen",
        type=NodeType.STACK,
        children=[forward, backward],
    )
    specs = collect_cluster_widget_specs(screen, {"cluster_0": 2})
    result = render_cluster_widgets(specs, uses_svg=True, clean_trees=[screen])
    widget_source = result.files["lib/widgets/skip_widget.dart"]

    assert "final bool isForward;" in widget_source
    assert "isForward ? 'assets/icons/vector_forward.svg'" in widget_source
    assert "'assets/icons/vector_backward.svg'" in widget_source
    assert "BoxFit.contain" in widget_source


def test_primary_vector_asset_finds_nested_icon() -> None:
    node = _skip_cluster(forward=True)
    assert primary_vector_asset(node) == "assets/icons/vector_forward.svg"


def test_collect_cluster_vector_variants_maps_representatives() -> None:
    forward = _skip_cluster(forward=True)
    backward = _skip_cluster(forward=False)
    screen = CleanDesignTreeNode(
        id="1",
        name="Screen",
        type=NodeType.STACK,
        children=[forward, backward],
    )
    variants = collect_cluster_vector_variants([screen], {"cluster_0": forward})
    assert "cluster_0" in variants
