"""Planner must keep login/form fields inline in deterministic layout emit."""

from __future__ import annotations

from figma_flutter_agent.config import AgentYamlConfig, GenerationConfig, Settings
from figma_flutter_agent.generator.planner import GenerationPlanContext, plan_generation_files
from figma_flutter_agent.generator.subtree import (
    collect_subtree_widget_specs,
    replace_extracted_subtree_nodes_with_refs,
)
from figma_flutter_agent.generator.subtree.spec import SubtreeWidgetSpec
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    DesignTokens,
    ExtractedWidget,
    FlutterGenerationResponse,
    NodeStyle,
    NodeType,
    ScreenIr,
    Sizing,
    WidgetIrKind,
    WidgetIrNode,
    WidgetIrRef,
)


def _vector_leaf(node_id: str) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name="Vector",
        type=NodeType.VECTOR,
        sizing=Sizing(width=4.0, height=4.0),
        style=NodeStyle(),
    )


def _form_input_field(
    node_id: str,
    *,
    label: str,
    extracted_ref: str | None = None,
    nested_input_area: bool = False,
    paint_on_input: bool = False,
) -> CleanDesignTreeNode:
    surface = CleanDesignTreeNode(
        id=f"{node_id}:surf",
        name="Surface",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=327.0, height=46.0),
        style=NodeStyle(
            background_color="0xFFFFFFFF",
            border_color="0xFFEDF1F3",
            border_radius=10.0,
        ),
        children=[_vector_leaf(f"{node_id}:v{i}") for i in range(8)],
    )
    if nested_input_area:
        field_body = CleanDesignTreeNode(
            id=f"{node_id}:area",
            name="Input Area",
            type=NodeType.INPUT,
            sizing=Sizing(width=327.0, height=46.0),
            style=NodeStyle(
                background_color="0xFFFFFFFF",
                border_color="0xFFEDF1F3",
                border_radius=10.0,
            )
            if paint_on_input
            else NodeStyle(),
            children=[] if paint_on_input else [surface],
        )
    else:
        field_body = surface
    return CleanDesignTreeNode(
        id=node_id,
        name="Input Field",
        type=NodeType.INPUT,
        extracted_widget_ref=extracted_ref,
        spacing=2.0,
        sizing=Sizing(width=327.0, height=69.0),
        children=[
            CleanDesignTreeNode(
                id=f"{node_id}:lbl",
                name=label,
                type=NodeType.TEXT,
                text=label,
                sizing=Sizing(width=30.0, height=21.0),
                style=NodeStyle(font_size=12.0, text_color="0xFF6C7278"),
            ),
            field_body,
        ],
    )


def test_collect_subtree_specs_skip_input_nodes() -> None:
    email = _form_input_field("email", label="Email")
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=812.0),
        children=[email],
    )
    specs = collect_subtree_widget_specs(root, widget_suffix="Widget")
    assert not any(spec.node_id == email.id for spec in specs)


def test_replace_extracted_subtree_refs_skip_inline_hosts() -> None:
    email = _form_input_field("email", label="Email", extracted_ref=None)
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=812.0),
        children=[email],
    )
    specs = [
        SubtreeWidgetSpec(
            node_id=email.id,
            class_name="InputFieldWidget",
            file_name="input_field_widget",
            representative=email,
            vector_count=8,
        )
    ]
    replace_extracted_subtree_nodes_with_refs(root, specs)
    assert root.children[0].extracted_widget_ref is None


def test_plan_layout_inlines_form_fields_despite_llm_extracted_widgets() -> None:
    email = _form_input_field("email", label="Email", extracted_ref="InputFieldWidget")
    password = _form_input_field("password", label="Password", extracted_ref="InputFieldWidgetVariant2")
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=812.0),
        children=[
            CleanDesignTreeNode(
                id="content",
                name="Content",
                type=NodeType.COLUMN,
                spacing=16.0,
                sizing=Sizing(width=327.0, height=400.0),
                children=[email, password],
            )
        ],
    )
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id="root",
            kind=WidgetIrKind.STACK,
            children=[
                WidgetIrNode(
                    figma_id="content",
                    kind=WidgetIrKind.COLUMN,
                    children=[
                        WidgetIrNode(
                            figma_id="email",
                            kind=WidgetIrKind.EXTRACTED,
                            ref=WidgetIrRef(widget_name="input_field"),
                        ),
                        WidgetIrNode(
                            figma_id="password",
                            kind=WidgetIrKind.EXTRACTED,
                            ref=WidgetIrRef(widget_name="input_field"),
                        ),
                    ],
                )
            ],
        )
    )
    generation = FlutterGenerationResponse(
        screen_ir=screen_ir,
        extracted_widgets=[
            ExtractedWidget(
                widget_name="input_field",
                code=(
                    "class InputFieldWidget extends StatelessWidget {\n"
                    "  const InputFieldWidget({super.key});\n"
                    "  @override Widget build(BuildContext c) => const Text('Password');\n"
                    "}\n"
                ),
            )
        ],
    )
    settings = Settings(
        agent=AgentYamlConfig(
            generation=GenerationConfig(
                true_subtree_pruning=True,
                use_screen_ir=True,
                use_geometry_planner=False,
            ),
        ),
    )
    context = GenerationPlanContext(
        settings=settings,
        clean_tree=root,
        tokens=DesignTokens(),
        resolved_feature="inline_form_plan",
        node_id="root",
        cluster_summary={},
        generation=generation,
        project_dir=None,
    )
    planned = plan_generation_files(context)
    layout = planned["lib/generated/inline_form_plan_layout.dart"]
    assert "const InputFieldWidget()" not in layout
    assert "const InputFieldWidgetVariant2()" not in layout
    assert "TextFormField" in layout or "TextField" in layout


def test_collect_cluster_specs_skip_inline_form_inputs() -> None:
    from figma_flutter_agent.generator.widget_extractor import collect_cluster_widget_specs

    email = _form_input_field("email", label="Email")
    email = email.model_copy(update={"cluster_id": "component_email"})
    password = _form_input_field("password", label="Password")
    password = password.model_copy(update={"cluster_id": "component_email"})
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=812.0),
        children=[email, password],
    )
    specs = collect_cluster_widget_specs(
        root,
        {"component_email": 2},
        min_count=2,
        widget_suffix="Widget",
    )
    assert specs == []


def test_nested_input_area_renders_single_text_form_field_without_height_overflow() -> None:
    from figma_flutter_agent.generator.layout.file import render_layout_file

    email = _form_input_field("email", label="Email", nested_input_area=True)
    password = _form_input_field("password", label="Password", nested_input_area=True)
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.COLUMN,
        spacing=16.0,
        sizing=Sizing(width=327.0, height=200.0),
        children=[email, password],
    )
    layout = render_layout_file(
        root,
        feature_name="nested_input",
        uses_svg=False,
    )["lib/generated/nested_input_layout.dart"]
    assert layout.count("TextField") == 2
    assert "Text('Email'" in layout
    assert "hintText: 'Email'" not in layout
    assert "height: 46.0" in layout
    assert "height: 69.0" not in layout
    assert "Email" in layout
    assert "Password" in layout


def test_composite_input_emits_external_label_above_bordered_surface() -> None:
    from figma_flutter_agent.generator.layout.file import render_layout_file

    email = _form_input_field(
        "email",
        label="Email",
        nested_input_area=True,
        paint_on_input=True,
    )
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.COLUMN,
        spacing=16.0,
        sizing=Sizing(width=327.0, height=120.0),
        children=[email],
    )
    layout = render_layout_file(
        root,
        feature_name="external_label_input",
        uses_svg=False,
    )["lib/generated/external_label_input_layout.dart"]
    assert "Text('Email'" in layout
    assert "TextFormField" in layout or "TextField" in layout
    assert "Container(" in layout
    assert "decoration: BoxDecoration" in layout
    assert "enabledBorder: InputBorder.none" in layout
    assert "hintText: 'Email'" not in layout
    assert "height: 46.0" in layout
    assert "SizedBox(width: double.infinity, height: 69.0" not in layout


def test_nested_input_area_paint_on_input_emits_bordered_container() -> None:
    from figma_flutter_agent.generator.layout.file import render_layout_file

    email = _form_input_field(
        "email",
        label="Email",
        nested_input_area=True,
        paint_on_input=True,
    )
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.COLUMN,
        spacing=16.0,
        sizing=Sizing(width=327.0, height=120.0),
        children=[email],
    )
    layout = render_layout_file(
        root,
        feature_name="nested_input_paint",
        uses_svg=False,
    )["lib/generated/nested_input_paint_layout.dart"]
    assert "TextField" in layout
    assert "Container(" in layout
    assert "decoration: BoxDecoration" in layout
    assert "enabledBorder: InputBorder.none" in layout
