"""Shape cluster and parameterized widget tests."""

from figma_flutter_agent.config.models import WidgetExtractionConfig
from figma_flutter_agent.generator.variant_topology import compare_variant_topology
from figma_flutter_agent.generator.widget_extraction import collect_widget_specs
from figma_flutter_agent.generator.widget_extraction.props import diff_props
from figma_flutter_agent.generator.widget_extraction.shape import index_shape_clusters
from figma_flutter_agent.generator.widget_extraction.variant_params import variant_reference_args
from figma_flutter_agent.generator.widget_extractor import render_cluster_widgets
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    ComponentVariant,
    NodeType,
    Sizing,
)


def _card(title: str, *, card_id: str) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=card_id,
        name="Product Card",
        type=NodeType.CARD,
        sizing=Sizing(width=168.0, height=200.0),
        children=[
            CleanDesignTreeNode(
                id=f"{card_id}:title",
                name="Title",
                type=NodeType.TEXT,
                text=title,
                sizing=Sizing(width=120.0, height=20.0),
            ),
            CleanDesignTreeNode(
                id=f"{card_id}:price",
                name="Price",
                type=NodeType.TEXT,
                text="$9",
                sizing=Sizing(width=80.0, height=20.0),
            ),
        ],
    )


def test_diff_props_builds_title_param() -> None:
    members = [_card("A", card_id="a"), _card("B", card_id="b"), _card("C", card_id="c")]
    bundle = diff_props(members)
    assert bundle is not None
    assert any(spec.name == "title" for spec in bundle.params)


def test_shape_clusters_split_login_and_signup() -> None:
    login = CleanDesignTreeNode(
        id="login",
        name="Login",
        type=NodeType.BUTTON,
        sizing=Sizing(width=120.0, height=48.0),
        children=[
            CleanDesignTreeNode(
                id="login:text",
                name="Label",
                type=NodeType.TEXT,
                text="Login",
                sizing=Sizing(width=80.0, height=20.0),
            ),
        ],
    )
    signup = CleanDesignTreeNode(
        id="signup",
        name="Sign up",
        type=NodeType.STACK,
        sizing=Sizing(width=120.0, height=48.0),
        children=[
            CleanDesignTreeNode(
                id="signup:text",
                name="Label",
                type=NodeType.TEXT,
                text="Sign up",
                sizing=Sizing(width=80.0, height=20.0),
            ),
            CleanDesignTreeNode(
                id="signup:icon",
                name="Icon",
                type=NodeType.VECTOR,
                sizing=Sizing(width=16.0, height=16.0),
            ),
        ],
    )
    assert compare_variant_topology(login, signup).should_split is True


def test_parameterized_shape_widget_render() -> None:
    screen = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.COLUMN,
        children=[
            _card("Hoodie", card_id="c1"),
            _card("Hat", card_id="c2"),
            _card("Mug", card_id="c3"),
        ],
    )
    config = WidgetExtractionConfig(policy="dedup", parameterize_text=True)
    summary, members = index_shape_clusters(screen, min_count=2)
    assert summary
    specs = collect_widget_specs(screen, summary, config=config)
    shape_specs = [spec for spec in specs if spec.param_bundle is not None]
    assert shape_specs
    result = render_cluster_widgets(shape_specs, uses_svg=False, clean_trees=[screen])
    widget_source = next(iter(result.files.values()))
    assert "final String title" in widget_source
    assert "Text(title" in widget_source


def test_variant_reference_args_disabled_state() -> None:
    button = CleanDesignTreeNode(
        id="btn",
        name="Primary",
        type=NodeType.BUTTON,
        sizing=Sizing(width=120.0, height=48.0),
        variant=ComponentVariant(
            component_id="1:2",
            component_name="Button/Primary",
            variant_properties={"state": "disabled"},
            state="disabled",
        ),
        children=[],
    )
    assert variant_reference_args(button) == "enabled: false"
