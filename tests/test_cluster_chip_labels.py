"""Cluster chip widget label tests."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.widgets import render_node_body
from figma_flutter_agent.generator.widget_extractor import (
    collect_cluster_widget_specs,
    render_cluster_widgets,
)
from figma_flutter_agent.parser.interaction.chip_variant import chip_component_label
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    ComponentVariant,
    NodeStyle,
    NodeType,
    Sizing,
)


def _tag_chip(
    node_id: str,
    *,
    label: str,
    cluster_id: str = "cluster_tag",
    selected: bool = False,
) -> CleanDesignTreeNode:
    style_axis = "Focus" if selected else "Default"
    return CleanDesignTreeNode(
        id=node_id,
        name="Tag",
        type=NodeType.ROW,
        cluster_id=cluster_id,
        sizing=Sizing(width=120.0, height=24.0),
        style=NodeStyle(
            background_color="0xFFBFAFF3" if selected else "0xFFFFFFFF",
            border_radius=12.0,
            text_case="UPPER",
        ),
        variant=ComponentVariant(
            component_id="6:2279",
            variant_properties={
                "Text#109:4": label,
                "Style": style_axis,
            },
        ),
        children=[],
    )


def test_chip_component_label_reads_text_variant_axis() -> None:
    node = _tag_chip("1", label="only english", selected=True)

    assert chip_component_label(node) == "only english"


def test_wrap_cluster_chips_emit_distinct_instance_labels() -> None:
    chips = [
        _tag_chip("1", label="could have more components"),
        _tag_chip("2", label="complex"),
        _tag_chip("3", label="only english", selected=True),
        _tag_chip("4", label="helpful"),
    ]
    wrap = CleanDesignTreeNode(
        id="wrap",
        name="Chip Wrap",
        type=NodeType.ROW,
        sizing=Sizing(width=320.0, height=80.0),
        children=chips,
    )
    cluster_classes = {"cluster_tag": "TagWidget"}
    bodies = [
        render_node_body(
            chip,
            uses_svg=False,
            parent_type=NodeType.ROW,
            cluster_classes=cluster_classes,
        )
        for chip in chips
    ]
    combined = "\n".join(bodies)

    assert "TagWidget(label: 'COULD HAVE MORE COMPONENTS')" in combined
    assert "TagWidget(label: 'COMPLEX')" in combined
    assert "TagWidget(label: 'ONLY ENGLISH', isSelected: true)" in combined
    assert "TagWidget(label: 'HELPFUL')" in combined
    assert "const TagWidget()" not in combined

    representative = CleanDesignTreeNode(
        id="rep",
        name="Tag",
        type=NodeType.ROW,
        cluster_id="cluster_tag",
        sizing=Sizing(width=95.0, height=24.0),
        style=NodeStyle(background_color="0xFFFFFFFF", border_radius=12.0),
        variant=ComponentVariant(
            variant_properties={"Text#109:4": "helpful", "Style": "Default"},
        ),
        children=[
            CleanDesignTreeNode(
                id="rep:text",
                name="Label",
                type=NodeType.TEXT,
                text="helpful",
                style=NodeStyle(
                    text_color="0xFF8B84FC",
                    font_size=12.0,
                    text_case="UPPER",
                ),
            ),
        ],
    )
    screen = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.COLUMN,
        children=[representative, *chips],
    )
    specs = collect_cluster_widget_specs(screen, {"cluster_tag": 5})
    result = render_cluster_widgets(specs, uses_svg=False, clean_trees=[screen])
    widget_source = result.files["lib/widgets/tag_widget.dart"]

    assert "final String label;" in widget_source
    assert "final bool isSelected;" in widget_source
    assert "this.label = 'HELPFUL'" in widget_source
    assert "Text(label" in widget_source
    assert "Text('HELPFUL'" not in widget_source

    layout_body = render_node_body(
        wrap,
        uses_svg=False,
        cluster_classes=result.cluster_classes,
    )
    assert "const TagWidget()" not in layout_body


def test_tag_chip_widget_hugs_content_without_fixed_representative_width() -> None:
    narrow = _tag_chip("1", label="helpful")
    narrow.sizing = Sizing(width=72.0, height=24.0)
    wide = _tag_chip("2", label="could have more components")
    wide.sizing = Sizing(width=209.0, height=24.0)
    representative = CleanDesignTreeNode(
        id="rep",
        name="Tag",
        type=NodeType.ROW,
        cluster_id="cluster_tag",
        sizing=Sizing(width=72.0, height=24.0),
        style=NodeStyle(background_color="0xFFFFFFFF", border_radius=12.0),
        variant=ComponentVariant(
            variant_properties={"Text#109:4": "helpful", "Style": "Default"},
        ),
        children=[
            CleanDesignTreeNode(
                id="rep:text",
                name="Label",
                type=NodeType.TEXT,
                text="helpful",
                style=NodeStyle(
                    text_color="0xFF8B84FC",
                    font_size=12.0,
                    text_case="UPPER",
                ),
            ),
        ],
    )
    screen = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.COLUMN,
        children=[representative, narrow, wide],
    )
    specs = collect_cluster_widget_specs(screen, {"cluster_tag": 3})
    result = render_cluster_widgets(specs, uses_svg=False, clean_trees=[screen])
    widget_source = result.files["lib/widgets/tag_widget.dart"]

    assert "width: 72" not in widget_source
    assert "FittedBox" not in widget_source
    assert "BoxFit.scaleDown" not in widget_source

    wide_body = render_node_body(
        wide,
        uses_svg=False,
        cluster_classes=result.cluster_classes,
    )
    assert "TagWidget(label: 'COULD HAVE MORE COMPONENTS')" in wide_body
    assert "FittedBox" not in wide_body
    assert "SizedBox(width: 209.0" in wide_body


def test_option_chip_emits_interactive_surface() -> None:
    representative = CleanDesignTreeNode(
        id="rep",
        name="Tag",
        type=NodeType.ROW,
        cluster_id="cluster_tag",
        sizing=Sizing(width=95.0, height=24.0),
        style=NodeStyle(background_color="0xFFFFFFFF", border_radius=12.0),
        variant=ComponentVariant(
            variant_properties={"Text#109:4": "helpful", "Style": "Default"},
        ),
        children=[],
    )
    screen = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.COLUMN,
        children=[representative, _tag_chip("1", label="helpful")],
    )
    specs = collect_cluster_widget_specs(screen, {"cluster_tag": 2})
    result = render_cluster_widgets(specs, uses_svg=False, clean_trees=[screen])
    widget_source = result.files["lib/widgets/tag_widget.dart"]

    assert "InkWell(" in widget_source
    assert "onTap:" in widget_source
    assert "chip-choice" in widget_source
    assert "Semantics(button: true" in widget_source.replace("\n", "")
    assert "FittedBox" not in widget_source
    assert "width: 48" not in widget_source
