"""Cluster chip widget label tests."""

from __future__ import annotations

from figma_flutter_agent.generator.cluster_variants import (
    cluster_chip_reference_args,
    cluster_uses_chip_variant_labels,
)
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


def _tag_chip_without_variant_axis(
    node_id: str,
    *,
    text_content: str,
    cluster_id: str = "cluster_tag",
    selected: bool = False,
) -> CleanDesignTreeNode:
    """Tag chip with nested TEXT but no ``Text#`` variant axis."""
    return CleanDesignTreeNode(
        id=node_id,
        name="Tag",
        type=NodeType.ROW,
        cluster_id=cluster_id,
        sizing=Sizing(width=95.0, height=24.0),
        style=NodeStyle(
            background_color="0xFF006FFD" if selected else "0xFFEAF2FF",
            border_radius=12.0,
        ),
        variant=ComponentVariant(
            component_id="6:2279",
            variant_properties={
                "Style": "Focus" if selected else "Default",
            },
        ),
        children=[
            CleanDesignTreeNode(
                id=f"{node_id}:text",
                name="Text",
                type=NodeType.TEXT,
                text=text_content,
                style=NodeStyle(
                    text_color="0xFFFFFFFF" if selected else "0xFF006FFD",
                    font_size=12.0,
                ),
            ),
        ],
    )


def test_cluster_chip_reference_args_none_without_text_variant_axis() -> None:
    """EMITTER_GENERATED_CODE_COMPILATION: no label/isSelected without Text# axis."""
    node = _tag_chip_without_variant_axis("1", text_content="hello")
    assert cluster_chip_reference_args(node) is None


def test_cluster_chip_reference_args_emits_with_text_variant_axis() -> None:
    node = _tag_chip("1", label="hello", selected=True)
    result = cluster_chip_reference_args(node)
    assert result is not None
    assert "label:" in result
    assert "isSelected: true" in result


def _input_field_component(
    node_id: str,
    *,
    placeholder: str = "Lois",
    cluster_id: str = "component_input_field",
) -> CleanDesignTreeNode:
    """Figma Input Field component with ``Text#`` placeholder axis (not a tag chip)."""
    return CleanDesignTreeNode(
        id=node_id,
        name="Input Field",
        type=NodeType.COLUMN,
        cluster_id=cluster_id,
        sizing=Sizing(width=155.5, height=69.0),
        variant=ComponentVariant(
            component_id="3:6008",
            component_name="Input Field",
            variant_properties={
                "Text#664:10": placeholder,
                "Label#664:14": "First Name",
            },
        ),
        children=[
            CleanDesignTreeNode(
                id=f"{node_id}:title",
                name="Title",
                type=NodeType.ROW,
                sizing=Sizing(width=59.0, height=21.0),
                children=[
                    CleanDesignTreeNode(
                        id=f"{node_id}:label",
                        name="Email",
                        type=NodeType.TEXT,
                        text="First Name",
                        style=NodeStyle(font_size=12.0),
                    ),
                ],
            ),
            CleanDesignTreeNode(
                id=f"{node_id}:surface",
                name="Input Area",
                type=NodeType.ROW,
                sizing=Sizing(width=155.5, height=46.0),
                style=NodeStyle(
                    background_color="0xFFFFFFFF",
                    border_color="0xFFEDF1F3",
                    border_width=1.0,
                    border_radius=10.0,
                ),
                children=[
                    CleanDesignTreeNode(
                        id=f"{node_id}:value",
                        name="Value",
                        type=NodeType.TEXT,
                        text=placeholder,
                        style=NodeStyle(font_size=14.0),
                    ),
                ],
            ),
        ],
    )


def test_cluster_chip_reference_args_none_for_input_field_text_axis() -> None:
    """ChipVariantAxisScopeLaw: Input Field placeholder axis is not chip label args."""
    node = _input_field_component("42:3661")
    assert cluster_chip_reference_args(node) is None


def test_cluster_uses_chip_variant_labels_false_for_input_field_cluster() -> None:
    node = _input_field_component("42:3661")
    screen = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.COLUMN,
        children=[node],
    )
    assert not cluster_uses_chip_variant_labels([screen], node.cluster_id or "")


def test_input_field_cluster_delegate_emit_has_no_chip_ctor_args() -> None:
    node = _input_field_component("42:3661")
    body = render_node_body(
        node,
        uses_svg=False,
        cluster_classes={node.cluster_id or "": "InputFieldWidget"},
    )
    assert "InputFieldWidget(label:" not in body
    assert "isSelected" not in body
    assert "TextFormField" in body


def test_cluster_chip_reference_args_aligns_with_widget_parameterization() -> None:
    """Call-site args must match cluster_uses_chip_variant_labels parameterization scope."""
    node_no_axis = _tag_chip_without_variant_axis("1", text_content="hello")
    node_with_axis = _tag_chip("2", label="hello")
    screen = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.COLUMN,
        children=[node_no_axis, node_with_axis],
    )
    has_labels = cluster_uses_chip_variant_labels([screen], "cluster_tag")
    if has_labels:
        assert cluster_chip_reference_args(node_with_axis) is not None
    else:
        assert cluster_chip_reference_args(node_no_axis) is None


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


def test_tag_option_chip_preserves_default_blue_text_and_recovered_font_size() -> None:
    representative = CleanDesignTreeNode(
        id="rep",
        name="Tag",
        type=NodeType.ROW,
        cluster_id="cluster_tag",
        sizing=Sizing(width=95.0, height=24.0),
        style=NodeStyle(background_color="0xFFEAF2FF", border_radius=12.0),
        variant=ComponentVariant(
            variant_properties={"Text#109:4": "easy to use", "Style": "Default"},
        ),
        children=[
            CleanDesignTreeNode(
                id="rep:text",
                name="Text",
                type=NodeType.TEXT,
                text="easy to use",
                style=NodeStyle(
                    text_color="0xFF006FFD",
                    font_size=12.0,
                    font_weight="w600",
                    text_case="UPPER",
                ),
                text_metrics_frame={
                    "fontSize": 10.0,
                    "strutHeightRatio": 1.21,
                },
            ),
        ],
    )
    screen = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.COLUMN,
        children=[
            representative,
            _tag_chip("1", label="easy to use", width=95.0),
            _tag_chip("2", label="selected ref", width=72.0, selected=True),
        ],
    )
    specs = collect_cluster_widget_specs(screen, {"cluster_tag": 3})
    result = render_cluster_widgets(specs, uses_svg=False, clean_trees=[screen])
    widget_source = result.files["lib/widgets/tag_widget.dart"]

    assert "Color(0xFF006FFD)" in widget_source
    assert "colorScheme.onPrimary" in widget_source
    assert "Color(0xFF000000)" not in widget_source
    assert "AppColors.primary" not in widget_source
    assert "fontSize: 10.0" in widget_source
    assert "fontSize: 12.0" not in widget_source
    assert "bodyMedium" not in widget_source
    assert "StrutStyle(fontSize: 10.0" in widget_source


def _purple_tag_chip(
    node_id: str,
    *,
    label: str,
    selected: bool = False,
    width: float = 88.0,
) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name="Tag",
        type=NodeType.ROW,
        cluster_id="cluster_purple",
        sizing=Sizing(width=width, height=28.0),
        style=NodeStyle(
            background_color="0xFF8B84FC" if selected else "0xFFF3E8FF",
            border_radius=14.0,
        ),
        variant=ComponentVariant(
            variant_properties={
                "Text#1": label,
                "Style": "Focus" if selected else "Default",
            },
        ),
        children=[
            CleanDesignTreeNode(
                id=f"{node_id}:text",
                name="Text",
                type=NodeType.TEXT,
                text=label,
                style=NodeStyle(
                    text_color="0xFFFFFFFF" if selected else "0xFF8B84FC",
                    font_size=11.0,
                    font_weight="w600",
                ),
            ),
        ],
    )


def test_chip_cluster_emits_palette_b_without_feedback_hex_leakage() -> None:
    chips = [
        _purple_tag_chip("p1", label="alpha"),
        _purple_tag_chip("p2", label="beta", selected=True),
    ]
    representative = chips[0].model_copy(deep=True)
    representative.id = "rep-purple"
    screen = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.COLUMN,
        children=[representative, *chips],
    )
    specs = collect_cluster_widget_specs(screen, {"cluster_purple": 3})
    result = render_cluster_widgets(specs, uses_svg=False, clean_trees=[screen])
    widget_source = result.files["lib/widgets/tag_widget.dart"]

    assert "Color(0xFF8B84FC)" in widget_source
    assert "Color(0xFFF3E8FF)" in widget_source
    assert "0xFF006FFD" not in widget_source
    assert "0xFFEAF2FF" not in widget_source
    assert "AppColors.primary" not in widget_source
