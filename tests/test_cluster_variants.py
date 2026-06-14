"""Cluster widget variant detection tests."""

from pathlib import Path

from figma_flutter_agent.generator.cluster_variants import (
    cluster_reference_args,
    cluster_skip_backward_by_placement,
    collect_cluster_vector_variants,
    detect_vector_flip_variant,
    primary_vector_asset,
)
from figma_flutter_agent.generator.widget_extractor import (
    collect_cluster_widget_specs,
    render_cluster_widgets,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    StackPlacement,
)


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


def test_cluster_skip_backward_by_placement_uses_right_anchor() -> None:
    node = CleanDesignTreeNode(
        id="1:4019",
        name="Rewind",
        type=NodeType.STACK,
        cluster_id="cluster_0",
        sizing=Sizing(width=38.8, height=39.0),
        stack_placement=StackPlacement(right=247.8, width=38.8, height=39.0),
    )
    assert cluster_skip_backward_by_placement(node) is True


def test_detect_vector_flip_variant_infers_backward_asset_from_placement() -> None:
    forward = CleanDesignTreeNode(
        id="1:4016",
        name="Skip",
        type=NodeType.STACK,
        cluster_id="cluster_0",
        sizing=Sizing(width=38.8, height=39.0),
        stack_placement=StackPlacement(left=247.8, width=38.8, height=39.0),
        children=[
            CleanDesignTreeNode(
                id="1:4017",
                name="Vector",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/vector_1_4017.svg",
            )
        ],
    )
    backward = CleanDesignTreeNode(
        id="1:4019",
        name="Rewind",
        type=NodeType.STACK,
        cluster_id="cluster_0",
        sizing=Sizing(width=38.8, height=39.0),
        stack_placement=StackPlacement(right=247.8, width=38.8, height=39.0),
        children=[],
    )
    screen = CleanDesignTreeNode(
        id="1",
        name="Screen",
        type=NodeType.STACK,
        children=[forward, backward],
    )
    variant = detect_vector_flip_variant([screen], "cluster_0", representative=forward)
    assert variant is not None
    assert variant.backward_asset == "assets/icons/vector_1_4020.svg"
    assert cluster_reference_args(backward, variant) == "isForward: false"


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


def test_render_cluster_widgets_resolves_discovered_svg(tmp_path: Path) -> None:
    icons = tmp_path / "assets" / "icons"
    icons.mkdir(parents=True)
    node_id = "star:1"
    (icons / "star_star_1.svg").write_text("<svg></svg>", encoding="utf-8")
    representative = CleanDesignTreeNode(
        id=node_id,
        name="Star",
        type=NodeType.VECTOR,
        cluster_id="cluster_0",
        sizing=Sizing(width=16.0, height=16.0),
        style=NodeStyle(has_stroke=True),
        children=[],
    )
    duplicate = representative.model_copy(deep=True)
    screen = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.ROW,
        children=[representative, duplicate],
    )
    specs = collect_cluster_widget_specs(screen, {"cluster_0": 2})
    result = render_cluster_widgets(
        specs,
        uses_svg=True,
        clean_trees=[screen],
        project_dir=tmp_path,
    )
    widget_source = next(iter(result.files.values()))
    assert "SvgPicture.asset" in widget_source
    assert "calendar_today" not in widget_source
