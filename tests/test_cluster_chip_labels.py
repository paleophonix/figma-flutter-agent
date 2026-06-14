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
    Padding,
    Sizing,
    StackPlacement,
)


def _tag_chip(
    node_id: str,
    *,
    label: str,
    cluster_id: str = "cluster_tag",
    selected: bool = False,
    width: float = 120.0,
) -> CleanDesignTreeNode:
    style_axis = "Focus" if selected else "Default"
    return CleanDesignTreeNode(
        id=node_id,
        name="Tag",
        type=NodeType.ROW,
        cluster_id=cluster_id,
        sizing=Sizing(width=width, height=24.0),
        style=NodeStyle(
            background_color="0xFF006FFD" if selected else "0xFFEAF2FF",
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


def _tag_chip_with_text_child(
    node_id: str,
    *,
    label: str,
    width: float,
    placement: StackPlacement,
    selected: bool = False,
    cluster_id: str = "cluster_tag",
) -> CleanDesignTreeNode:
    """Tag row with nested TEXT (mirrors absolute-stack chips before cluster prune)."""
    chip = _tag_chip(
        node_id,
        label=label,
        cluster_id=cluster_id,
        selected=selected,
        width=width,
    )
    chip.layout_positioning = "ABSOLUTE"
    chip.stack_placement = placement
    chip.children = [
        CleanDesignTreeNode(
            id=f"{node_id}:text-wrap",
            name="Text",
            type=NodeType.ROW,
            sizing=Sizing(width=max(width - 16.0, 48.0), height=12.0),
            padding=Padding(left=4.0, right=4.0),
            children=[
                CleanDesignTreeNode(
                    id=f"{node_id}:text",
                    name="Text",
                    type=NodeType.TEXT,
                    text=label,
                    sizing=Sizing(width=max(width - 24.0, 40.0), height=12.0),
                    style=NodeStyle(
                        text_color="0xFFFFFFFF" if selected else "0xFF006FFD",
                        font_size=12.0,
                        font_weight="w600",
                        text_case="UPPER",
                    ),
                ),
            ],
        ),
    ]
    return chip


def _chip_cluster_screen(*chips: CleanDesignTreeNode) -> tuple[CleanDesignTreeNode, dict[str, str]]:
    representative = chips[0].model_copy(deep=True)
    representative.id = "rep"
    representative.children = []
    screen = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.COLUMN,
        children=[representative, *chips],
    )
    specs = collect_cluster_widget_specs(screen, {"cluster_tag": len(chips) + 1})
    result = render_cluster_widgets(specs, uses_svg=False, clean_trees=[screen])
    return screen, result.cluster_classes


def _absolute_tag_chip_group() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="chips-abs",
        name="Chips",
        type=NodeType.STACK,
        sizing=Sizing(width=266.0, height=56.0),
        children=[
            _tag_chip_with_text_child(
                "chip-a",
                label="easy to use",
                width=95.0,
                placement=StackPlacement(right=171.0, bottom=32.0, width=95.0, height=24.0),
            ),
            _tag_chip_with_text_child(
                "chip-b",
                label="helpful",
                width=72.0,
                placement=StackPlacement(left=194.0, bottom=32.0, width=72.0, height=24.0),
                selected=True,
            ),
            _tag_chip_with_text_child(
                "chip-c",
                label="complete",
                width=83.0,
                placement=StackPlacement(left=103.0, top=0.0, width=83.0, height=24.0),
            ),
        ],
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

    assert "TagWidget(label: 'COULD HAVE MORE COMPONENTS', isSelected: false)" in combined
    assert "TagWidget(label: 'COMPLEX', isSelected: false)" in combined
    assert "TagWidget(label: 'ONLY ENGLISH', isSelected: true)" in combined
    assert "TagWidget(label: 'HELPFUL', isSelected: false)" in combined
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
    assert "TagWidget(label: 'COULD HAVE MORE COMPONENTS', isSelected: false)" in wide_body
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


def test_narrow_tag_option_chip_uses_cluster_not_fittedbox() -> None:
    narrow = _tag_chip("1", label="complex", width=77.0)
    _, cluster_classes = _chip_cluster_screen(narrow)
    body = render_node_body(
        narrow,
        uses_svg=False,
        cluster_classes=cluster_classes,
    )
    assert "TagWidget(label: 'COMPLEX', isSelected: false)" in body
    assert "FittedBox" not in body
    assert "BoxFit.scaleDown" not in body
    assert "SizedBox(width: 77.0" in body


def test_absolute_tag_chip_stack_emits_interactive_cluster() -> None:
    group = _absolute_tag_chip_group()
    chips = list(group.children)
    _, cluster_classes = _chip_cluster_screen(*chips)
    layout_body = render_node_body(
        group,
        uses_svg=False,
        cluster_classes=cluster_classes,
    )
    for label in ("EASY TO USE", "HELPFUL", "COMPLETE"):
        assert label in layout_body
    assert layout_body.count("TagWidget(") == 3
    assert "FittedBox" not in layout_body
    assert "BoxFit.scaleDown" not in layout_body


def test_tag_widget_call_site_passes_is_selected_false() -> None:
    chips = [
        _tag_chip("1", label="complex", width=77.0),
        _tag_chip("2", label="only english", width=103.0, selected=True),
    ]
    wrap = CleanDesignTreeNode(
        id="wrap",
        name="Chip Wrap",
        type=NodeType.ROW,
        sizing=Sizing(width=320.0, height=80.0),
        children=chips,
    )
    _, cluster_classes = _chip_cluster_screen(*chips)
    layout_body = render_node_body(
        wrap,
        uses_svg=False,
        cluster_classes=cluster_classes,
    )
    assert "TagWidget(label: 'COMPLEX', isSelected: false)" in layout_body
    assert "TagWidget(label: 'ONLY ENGLISH', isSelected: true)" in layout_body


def test_choice_chip_group_all_children_use_interactive_option_recipe() -> None:
    chips = [
        _tag_chip("1", label="could have more components", width=209.0),
        _tag_chip("2", label="complex", width=77.0),
        _tag_chip("3", label="not interactive", width=122.0),
        _tag_chip("4", label="only english", width=103.0, selected=True),
    ]
    wrap = CleanDesignTreeNode(
        id="wrap",
        name="Chips",
        type=NodeType.STACK,
        sizing=Sizing(width=294.0, height=56.0),
        children=chips,
    )
    screen, cluster_classes = _chip_cluster_screen(*chips)
    result = render_cluster_widgets(
        collect_cluster_widget_specs(screen, {"cluster_tag": 5}),
        uses_svg=False,
        clean_trees=[screen],
    )
    widget_source = result.files["lib/widgets/tag_widget.dart"].replace("\n", "")
    assert "InkWell(" in widget_source
    assert "chip-choice" in widget_source
    assert "Semantics(button: true" in widget_source
    assert "FittedBox" not in widget_source
    assert "0xFFEAF2FF" in widget_source
    assert "0xFF006FFD" in widget_source

    layout_body = render_node_body(
        wrap,
        uses_svg=False,
        cluster_classes=result.cluster_classes,
    )
    assert "FittedBox" not in layout_body
    assert "TagWidget(label: 'COULD HAVE MORE COMPONENTS'" in layout_body
    assert "TagWidget(label: 'COMPLEX'" in layout_body
    assert "TagWidget(label: 'NOT INTERACTIVE'" in layout_body
    assert "TagWidget(label: 'ONLY ENGLISH', isSelected: true)" in layout_body
    assert layout_body.count("TagWidget(") == 4
