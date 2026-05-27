"""Tests for deterministic subtree widget guardrails."""

from figma_flutter_agent.generator.layout_widget import render_node_body
from figma_flutter_agent.generator.llm_dart import validate_dart_delimiters
from figma_flutter_agent.generator.subtree_widgets import (
    SubtreeWidgetResult,
    SubtreeWidgetSpec,
    _collect_labeled_social_button_stacks,
    build_subtree_widget_hints,
    collect_subtree_widget_specs,
    fix_llm_social_button_inner_stacks,
    force_subtree_widgets_at_placement,
    merge_thin_llm_widgets_with_subtrees,
    reconcile_llm_screen_with_subtrees,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    StackPlacement,
)


def _vector_subtree(node_id: str, *, width: float, height: float, count: int) -> CleanDesignTreeNode:
    vectors = [
        CleanDesignTreeNode(id=f"{node_id}:{index}", name=f"Vector {index}", type=NodeType.VECTOR)
        for index in range(count)
    ]
    return CleanDesignTreeNode(
        id=node_id,
        name="Illustration Group",
        type=NodeType.STACK,
        sizing=Sizing(width=width, height=height),
        children=vectors,
    )


def test_collect_labeled_social_stacks_picks_outermost_google_row() -> None:
    """Google label nested in Group 6794 must resolve to the full-width button stack."""
    google_icon = CleanDesignTreeNode(
        id="1:3594",
        name="Group 6795",
        type=NodeType.STACK,
        sizing=Sizing(width=23.58, height=24.06),
        children=[
            CleanDesignTreeNode(id="1:3595", name="Vector", type=NodeType.VECTOR)
            for _ in range(4)
        ],
    )
    inner = CleanDesignTreeNode(
        id="1:3591",
        name="Group 6794",
        type=NodeType.STACK,
        sizing=Sizing(width=374.0, height=63.0),
        children=[
            CleanDesignTreeNode(
                id="1:3593",
                name="CONTINUE WITH GOOGLE",
                type=NodeType.TEXT,
                text="CONTINUE WITH GOOGLE",
            ),
        ],
    )
    button = CleanDesignTreeNode(
        id="1:3590",
        name="Group 6796",
        type=NodeType.STACK,
        sizing=Sizing(width=374.0, height=63.0),
        stack_placement=StackPlacement(left=20.0, top=287.0, width=374.0, height=63.0),
        children=[inner, google_icon],
    )
    root = CleanDesignTreeNode(id="1:1", name="Screen", type=NodeType.STACK, children=[button])
    stacks = _collect_labeled_social_button_stacks(root)
    assert len(stacks) == 1
    assert stacks[0][1].id == "1:3590"


def test_fix_social_button_removes_duplicate_google_widget_placement() -> None:
    google_stack = CleanDesignTreeNode(
        id="1:3590",
        name="Group 6796",
        type=NodeType.STACK,
        sizing=Sizing(width=374.0, height=63.0),
        stack_placement=StackPlacement(left=20.0, top=287.0, width=374.0, height=63.0),
        children=[
            CleanDesignTreeNode(
                id="1:3591",
                name="Group 6794",
                type=NodeType.STACK,
                sizing=Sizing(width=374.0, height=63.0),
                children=[
                    CleanDesignTreeNode(
                        id="1:3593",
                        name="CONTINUE WITH GOOGLE",
                        type=NodeType.TEXT,
                        text="CONTINUE WITH GOOGLE",
                    ),
                ],
            ),
            CleanDesignTreeNode(
                id="1:3594",
                name="Group 6795",
                type=NodeType.STACK,
                sizing=Sizing(width=23.58, height=24.06),
                children=[
                    CleanDesignTreeNode(
                        id="1:3595",
                        name="Vector",
                        type=NodeType.VECTOR,
                        vector_asset_key="assets/icons/vector_1_3595.svg",
                    )
                    for _ in range(4)
                ],
            ),
        ],
    )
    root = CleanDesignTreeNode(id="1:1", name="Screen", type=NodeType.STACK, children=[google_stack])
    screen = """
    Positioned(
      left: 20,
      top: 287,
      width: 374,
      height: 63,
      child: const Group6795Widget(),
    ),
    const Positioned(
      left: 49,
      top: 306,
      width: 23,
      height: 24,
      child: Group6795Widget(),
    ),
    """
    patched = fix_llm_social_button_inner_stacks(
        screen,
        root,
        uses_svg=True,
        subtree_widget_classes=frozenset({"Group6795Widget"}),
    )
    assert patched.count("Group6795Widget") == 0
    assert "CONTINUE WITH GOOGLE" in patched
    assert "vector_1_3595.svg" in patched


def test_collect_subtree_widget_specs_skips_compact_icon_inside_social_button() -> None:
    vectors = [
        CleanDesignTreeNode(
            id=f"1:g:{index}",
            name=f"Vector {index}",
            type=NodeType.VECTOR,
            vector_asset_key=f"assets/icons/vector_{index}.svg",
        )
        for index in range(4)
    ]
    google_icon = CleanDesignTreeNode(
        id="1:google",
        name="Group 6795",
        type=NodeType.STACK,
        sizing=Sizing(width=23.58, height=24.06),
        stack_placement=StackPlacement(left=29.0, top=19.5, width=23.58, height=24.06),
        children=vectors,
    )
    button = CleanDesignTreeNode(
        id="1:btn",
        name="Group 6796",
        type=NodeType.STACK,
        sizing=Sizing(width=374.0, height=63.0),
        stack_placement=StackPlacement(left=20.0, top=287.0, width=374.0, height=63.0),
        children=[
            google_icon,
            CleanDesignTreeNode(
                id="1:txt",
                name="CONTINUE WITH GOOGLE",
                type=NodeType.TEXT,
                text="CONTINUE WITH GOOGLE",
            ),
        ],
    )
    root = CleanDesignTreeNode(
        id="1:1",
        name="Screen",
        type=NodeType.STACK,
        children=[button],
    )
    specs = collect_subtree_widget_specs(root, widget_suffix="Widget")
    assert not [spec for spec in specs if spec.node_id == "1:google"]


def test_composite_icon_stack_keeps_absolute_vector_offsets() -> None:
    vectors = [
        CleanDesignTreeNode(
            id=f"1:g:{index}",
            name=f"Vector {index}",
            type=NodeType.VECTOR,
            vector_asset_key=f"assets/icons/vector_{index}.svg",
            stack_placement=StackPlacement(
                left=float(index * 4),
                top=float(index * 3),
                width=10.0,
                height=10.0,
            ),
        )
        for index in range(4)
    ]
    icon = CleanDesignTreeNode(
        id="1:google",
        name="Group 6795",
        type=NodeType.STACK,
        sizing=Sizing(width=24.0, height=24.0),
        children=vectors,
    )
    body = render_node_body(icon, uses_svg=True, parent_type=NodeType.STACK)
    assert "Positioned.fill" not in body
    assert "left: 4.0" in body or "left: 4," in body


def test_fix_llm_social_replaces_scaled_container_google_row() -> None:
    google_stack = CleanDesignTreeNode(
        id="1:3590",
        name="Group 6796",
        type=NodeType.STACK,
        sizing=Sizing(width=374.0, height=63.0),
        stack_placement=StackPlacement(left=20.0, top=287.0, width=374.0, height=63.0),
        children=[
            CleanDesignTreeNode(
                id="1:fill",
                name="Rectangle",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=374.0, height=63.0),
                style=NodeStyle(backgroundColor="0xFFFFFFFF"),
                stack_placement=StackPlacement(left=0.0, top=0.0, width=374.0, height=63.0),
            ),
            CleanDesignTreeNode(
                id="1:3594",
                name="Group 6795",
                type=NodeType.STACK,
                sizing=Sizing(width=23.58, height=24.06),
                stack_placement=StackPlacement(left=29.0, top=19.5, width=23.58, height=24.06),
                children=[
                    CleanDesignTreeNode(
                        id="1:3595",
                        name="Vector",
                        type=NodeType.VECTOR,
                        vector_asset_key="assets/icons/vector_1_3595.svg",
                    )
                ],
            ),
            CleanDesignTreeNode(
                id="1:txt",
                name="CONTINUE WITH GOOGLE",
                type=NodeType.TEXT,
                text="CONTINUE WITH GOOGLE",
                stack_placement=StackPlacement(left=92.0, top=24.0, width=190.0, height=14.0),
            ),
        ],
    )
    root = CleanDesignTreeNode(id="1:1", name="Screen", type=NodeType.STACK, children=[google_stack])
    llm_screen = """
    Positioned(
      left: 20.0 * scaleX,
      right: 20.0 * scaleX,
      top: 287.47 * scaleY,
      height: 63.0,
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(38.0),
          border: Border.all(color: const Color(0xFFEBEAEC)),
        ),
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            child: Stack(
              alignment: Alignment.center,
              children: [
                Padding(
                  padding: EdgeInsets.only(left: 40.0),
                  child: Text('CONTINUE WITH GOOGLE'),
                ),
              ],
            ),
          ),
        ),
      ),
    ),
    """
    from figma_flutter_agent.generator.dart_postprocess import strip_llm_responsive_layout_builder

    unscaled = strip_llm_responsive_layout_builder(llm_screen)
    patched = fix_llm_social_button_inner_stacks(unscaled, root, uses_svg=True)
    assert "Color(0xFFFFFFFF)" in patched
    assert "left: 29.0" in patched or "left: 29," in patched
    assert "left: 92.0" in patched or "left: 92," in patched
    assert "vector_1_3595.svg" in patched
    assert "padding: EdgeInsets.only(left: 40.0)" not in patched


def test_fix_llm_social_button_inner_stacks_replaces_centered_overlap() -> None:
    facebook_stack = CleanDesignTreeNode(
        id="1:3576",
        name="Group 6793",
        type=NodeType.STACK,
        sizing=Sizing(width=374.0, height=63.0),
        children=[
            CleanDesignTreeNode(
                id="1:3577",
                name="Rectangle 210",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=374.0, height=63.0),
                style=NodeStyle(backgroundColor="0xFF7583CA"),
                stack_placement=StackPlacement(
                    left=0.0, top=0.0, width=374.0, height=63.0
                ),
            ),
            CleanDesignTreeNode(
                id="1:3578",
                name="Vector",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/vector_1_3578.svg",
                stack_placement=StackPlacement(
                    left=34.84, top=19.47, width=12.03, height=24.06
                ),
            ),
            CleanDesignTreeNode(
                id="1:3579",
                name="CONTINUE WITH FACEBOOK",
                type=NodeType.TEXT,
                text="CONTINUE WITH FACEBOOK",
                stack_placement=StackPlacement(
                    left=92.65, top=24.5, width=188.54, height=14.0
                ),
            ),
        ],
    )
    root = CleanDesignTreeNode(
        id="1:1",
        name="Screen",
        type=NodeType.STACK,
        children=[facebook_stack],
    )
    llm_screen = """
return FilledButton(
  onPressed: () {},
  child: Stack(
    alignment: Alignment.center,
    children: [
      Positioned(
        left: 34.8,
        child: SvgPicture.asset('assets/icons/vector_1_3578.svg'),
      ),
      Text('CONTINUE WITH FACEBOOK'),
    ],
  ),
);
"""
    patched = fix_llm_social_button_inner_stacks(
        llm_screen,
        root,
        uses_svg=True,
    )
    assert "FilledButton" not in patched
    assert "InkWell" in patched
    assert "left: 34.84" in patched or "left: 34.841" in patched
    assert "left: 92.65" in patched or "left: 92.649" in patched
    assert "vector_1_3578.svg" in patched


def test_collect_subtree_widget_specs_detects_shallow_logo_child() -> None:
    vectors = [
        CleanDesignTreeNode(
            id=f"1:logo:{index}",
            name=f"Vector {index}",
            type=NodeType.VECTOR,
            vector_asset_key=f"assets/icons/vector_{index}.svg",
        )
        for index in range(7)
    ]
    logo = CleanDesignTreeNode(
        id="1:logo",
        name="Group 17",
        type=NodeType.STACK,
        sizing=Sizing(width=168.0, height=30.0),
        stack_placement=StackPlacement(left=123.0, top=50.0, width=168.0, height=30.0),
        children=vectors,
    )
    root = CleanDesignTreeNode(
        id="1:1",
        name="Screen",
        type=NodeType.STACK,
        children=[logo],
    )
    specs = collect_subtree_widget_specs(root, widget_suffix="Widget")
    assert len(specs) == 1
    assert specs[0].node_id == "1:logo"


def test_build_subtree_widget_hints_includes_placement() -> None:
    spec = SubtreeWidgetSpec(
        node_id="1:10",
        class_name="HeroIllustrationWidget",
        file_name="hero_illustration_widget",
        representative=CleanDesignTreeNode(
            id="1:10",
            name="Hero",
            type=NodeType.STACK,
            stack_placement=StackPlacement(left=40.7, top=160.0, width=332.2, height=242.7),
            children=[],
        ),
        vector_count=12,
    )
    hints = build_subtree_widget_hints([spec])
    assert len(hints) == 1
    assert "left: 40.7" in hints[0]
    assert "const HeroIllustrationWidget()" in hints[0]


def test_force_subtree_skips_animated_positioned_and_nested_helper_classes() -> None:
    illustration = CleanDesignTreeNode(
        id="1:3677",
        name="Group",
        type=NodeType.STACK,
        sizing=Sizing(width=332.2, height=242.7),
        stack_placement=StackPlacement(left=40.7, top=160.0, width=332.2, height=242.7),
        children=[
            CleanDesignTreeNode(id="1:1", name="Vector", type=NodeType.VECTOR)
            for _ in range(10)
        ],
    )
    spec = SubtreeWidgetSpec(
        node_id="1:3677",
        class_name="RelaxIllustrationWidget",
        file_name="relax_illustration_widget",
        representative=illustration,
        vector_count=10,
    )
    subtree_result = SubtreeWidgetResult(
        files={"lib/widgets/relax_illustration_widget.dart": "class RelaxIllustrationWidget {}"},
        specs=(spec,),
    )
    screen = """
class CentralIllustration extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return AnimatedPositioned(
      left: 40.7,
      top: 160.0,
      width: 332.2,
      height: 242.7,
      duration: Duration.zero,
      child: SvgPicture.asset('assets/icons/vector_1_3681.svg'),
    );
  }
}

class DemoScreen extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Stack(children: [
      Positioned(
        left: 40.7,
        top: 160.0,
        width: 332.2,
        height: 242.7,
        child: Stack(children: [
          SvgPicture.asset('assets/icons/vector_1_3681.svg'),
        ]),
      ),
    ]);
  }
}
"""
    patched = force_subtree_widgets_at_placement(
        screen,
        subtree_result=subtree_result,
        planned_files=subtree_result.files,
    )
    assert validate_dart_delimiters(patched) is None
    assert "const RelaxIllustrationWidget()" in patched
    assert "AnimatedPositioned(" in patched
    assert "class CentralIllustration" in patched


def test_force_subtree_widget_replaces_partial_llm_inlining() -> None:
    illustration = CleanDesignTreeNode(
        id="1:3677",
        name="Group",
        type=NodeType.STACK,
        sizing=Sizing(width=332.2, height=242.7),
        stack_placement=StackPlacement(left=40.7, top=160.0, width=332.2, height=242.7),
        children=[
            CleanDesignTreeNode(id="1:1", name="Vector", type=NodeType.VECTOR)
            for _ in range(10)
        ],
    )
    spec = SubtreeWidgetSpec(
        node_id="1:3677",
        class_name="RelaxIllustrationWidget",
        file_name="relax_illustration_widget",
        representative=illustration,
        vector_count=10,
    )
    subtree_result = SubtreeWidgetResult(
        files={"lib/widgets/relax_illustration_widget.dart": "class RelaxIllustrationWidget {}"},
        specs=(spec,),
    )
    screen = """
    Positioned(
      left: 40.7,
      top: 160.0,
      width: 332.2,
      height: 242.7,
      child: Stack(children: [
        SvgPicture.asset('assets/icons/vector_1_3681.svg'),
        SvgPicture.asset('assets/icons/vector_1_3912.svg'),
      ]),
    ),
    """
    patched = force_subtree_widgets_at_placement(
        screen,
        subtree_result=subtree_result,
        planned_files=subtree_result.files,
    )
    assert "const RelaxIllustrationWidget()" in patched
    assert "SvgPicture.asset" not in patched


def test_collect_subtree_widget_specs_detects_vector_rich_child() -> None:
    root = CleanDesignTreeNode(
        id="1:1",
        name="Screen",
        type=NodeType.STACK,
        children=[
            _vector_subtree("1:10", width=330, height=240, count=12),
            CleanDesignTreeNode(
                id="1:20",
                name="Button",
                type=NodeType.BUTTON,
                sizing=Sizing(width=374, height=63),
            ),
        ],
    )
    specs = collect_subtree_widget_specs(root, widget_suffix="Widget")
    assert len(specs) == 1
    assert specs[0].node_id == "1:10"
    assert specs[0].vector_count == 12


def test_collect_subtree_widget_specs_suffixes_class_when_file_reserved() -> None:
    root = CleanDesignTreeNode(
        id="1:1",
        name="Screen",
        type=NodeType.STACK,
        children=[_vector_subtree("1:10", width=330, height=240, count=12)],
    )
    specs = collect_subtree_widget_specs(
        root,
        widget_suffix="Widget",
        reserved_file_names={"illustration_group_widget"},
    )
    assert len(specs) == 1
    assert specs[0].file_name == "illustration_group_widget_2"
    assert specs[0].class_name == "IllustrationGroupWidget2"


def test_merge_thin_llm_widgets_replaces_under_specified_illustration() -> None:
    subtree_source = """
class RichIllustrationWidget extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Stack(children: [
      SvgPicture.asset('assets/icons/vector_a.svg'),
      SvgPicture.asset('assets/icons/vector_b.svg'),
      SvgPicture.asset('assets/icons/vector_c.svg'),
      SvgPicture.asset('assets/icons/vector_d.svg'),
      SvgPicture.asset('assets/icons/vector_e.svg'),
      SvgPicture.asset('assets/icons/vector_f.svg'),
    ]);
  }
}
"""
    llm_source = """
class RelaxIllustration extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Stack(children: [
      SvgPicture.asset('assets/icons/vector_a.svg'),
      SvgPicture.asset('assets/icons/vector_b.svg'),
    ]);
  }
}
"""
    spec = SubtreeWidgetSpec(
        node_id="1:10",
        class_name="RichIllustrationWidget",
        file_name="rich_illustration_widget",
        representative=_vector_subtree("1:10", width=330, height=240, count=12),
        vector_count=12,
    )
    subtree_result = SubtreeWidgetResult(
        files={"lib/widgets/rich_illustration_widget.dart": subtree_source},
        specs=(spec,),
    )
    planned = {"lib/widgets/relax_illustration.dart": llm_source}
    merged = merge_thin_llm_widgets_with_subtrees(planned, subtree_result)
    assert merged["lib/widgets/relax_illustration.dart"].count("SvgPicture.asset") == 6
    assert "class RelaxIllustration" in merged["lib/widgets/relax_illustration.dart"]


def test_merge_replaces_llm_subset_matching_all_llm_assets() -> None:
    subtree_source = """
class RichIllustrationWidget extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Stack(children: [
      SvgPicture.asset('assets/icons/vector_a.svg'),
      SvgPicture.asset('assets/icons/vector_b.svg'),
      SvgPicture.asset('assets/icons/vector_c.svg'),
      SvgPicture.asset('assets/icons/vector_d.svg'),
      SvgPicture.asset('assets/icons/vector_e.svg'),
      SvgPicture.asset('assets/icons/vector_f.svg'),
      SvgPicture.asset('assets/icons/vector_g.svg'),
      SvgPicture.asset('assets/icons/vector_h.svg'),
      SvgPicture.asset('assets/icons/vector_i.svg'),
      SvgPicture.asset('assets/icons/vector_j.svg'),
    ]);
  }
}
"""
    llm_source = """
class RelaxIllustration extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Row(children: [
      SvgPicture.asset('assets/icons/vector_a.svg'),
      SvgPicture.asset('assets/icons/vector_b.svg'),
      SvgPicture.asset('assets/icons/vector_c.svg'),
      SvgPicture.asset('assets/icons/vector_d.svg'),
      SvgPicture.asset('assets/icons/vector_e.svg'),
      SvgPicture.asset('assets/icons/vector_f.svg'),
    ]);
  }
}
"""
    spec = SubtreeWidgetSpec(
        node_id="1:10",
        class_name="RichIllustrationWidget",
        file_name="rich_illustration_widget",
        representative=_vector_subtree("1:10", width=330, height=240, count=12),
        vector_count=12,
    )
    subtree_result = SubtreeWidgetResult(
        files={"lib/widgets/rich_illustration_widget.dart": subtree_source},
        specs=(spec,),
    )
    planned = {"lib/widgets/relax_illustration.dart": llm_source}
    merged = merge_thin_llm_widgets_with_subtrees(planned, subtree_result)
    assert "Row(" not in merged["lib/widgets/relax_illustration.dart"]
    assert merged["lib/widgets/relax_illustration.dart"].count("SvgPicture.asset") == 10
    assert "class RelaxIllustration" in merged["lib/widgets/relax_illustration.dart"]


def test_merge_restores_subtree_file_when_llm_overwrites_same_path() -> None:
    subtree_source = """
class RelaxIllustration extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Stack(children: [
      SvgPicture.asset('assets/icons/vector_a.svg'),
      SvgPicture.asset('assets/icons/vector_b.svg'),
    ]);
  }
}
"""
    llm_source = """
class RelaxIllustration extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Row(children: [SvgPicture.asset('assets/icons/vector_a.svg')]);
  }
}
"""
    spec = SubtreeWidgetSpec(
        node_id="1:10",
        class_name="RelaxIllustration",
        file_name="relax_illustration",
        representative=_vector_subtree("1:10", width=330, height=240, count=2),
        vector_count=2,
    )
    subtree_result = SubtreeWidgetResult(
        files={"lib/widgets/relax_illustration.dart": subtree_source},
        specs=(spec,),
    )
    planned = {"lib/widgets/relax_illustration.dart": llm_source}
    merged = merge_thin_llm_widgets_with_subtrees(planned, subtree_result)
    assert "Row(" not in merged["lib/widgets/relax_illustration.dart"]
    assert merged["lib/widgets/relax_illustration.dart"].count("SvgPicture.asset") == 2


def test_merge_keeps_distinct_class_when_cluster_widget_already_exists() -> None:
    cluster_source = """
class GroupWidget extends StatelessWidget {
  const GroupWidget({super.key});
  @override
  Widget build(BuildContext context) => const SizedBox();
}
"""
    subtree_source = """
class GroupWidget2 extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Stack(children: [
      SvgPicture.asset('assets/icons/vector_a.svg'),
      SvgPicture.asset('assets/icons/vector_b.svg'),
      SvgPicture.asset('assets/icons/vector_c.svg'),
      SvgPicture.asset('assets/icons/vector_d.svg'),
      SvgPicture.asset('assets/icons/vector_e.svg'),
      SvgPicture.asset('assets/icons/vector_f.svg'),
      SvgPicture.asset('assets/icons/vector_g.svg'),
      SvgPicture.asset('assets/icons/vector_h.svg'),
    ]);
  }
}
"""
    llm_source = """
class GroupWidget extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Row(children: [SvgPicture.asset('assets/icons/vector_a.svg')]);
  }
}
"""
    spec = SubtreeWidgetSpec(
        node_id="1:10",
        class_name="GroupWidget2",
        file_name="group_widget_2",
        representative=_vector_subtree("1:10", width=330, height=240, count=12),
        vector_count=12,
    )
    subtree_result = SubtreeWidgetResult(
        files={"lib/widgets/group_widget_2.dart": subtree_source},
        specs=(spec,),
    )
    planned = {
        "lib/widgets/group_widget.dart": cluster_source,
        "lib/widgets/group_widget_2.dart": llm_source,
    }
    merged = merge_thin_llm_widgets_with_subtrees(planned, subtree_result)
    assert "class GroupWidget2" in merged["lib/widgets/group_widget_2.dart"]
    assert "class GroupWidget extends" in merged["lib/widgets/group_widget.dart"]


def test_reconcile_llm_screen_wires_subtree_and_logo_widgets() -> None:
    illustration = CleanDesignTreeNode(
        id="1:3677",
        name="Group",
        type=NodeType.STACK,
        sizing=Sizing(width=332.2, height=242.7),
        stack_placement=StackPlacement(left=40.7, top=160.0, width=332.2, height=242.7),
        children=[
            CleanDesignTreeNode(id="1:1", name="Vector", type=NodeType.VECTOR)
            for _ in range(10)
        ],
    )
    spec = SubtreeWidgetSpec(
        node_id="1:3677",
        class_name="GroupWidget",
        file_name="group_widget",
        representative=illustration,
        vector_count=10,
    )
    subtree_result = SubtreeWidgetResult(
        files={"lib/widgets/group_widget.dart": "class GroupWidget extends StatelessWidget {}"},
        specs=(spec,),
    )
    planned = {
        "lib/widgets/group_widget.dart": "class GroupWidget extends StatelessWidget {}",
        "lib/widgets/silent_moon_logo_icon.dart": """
class SilentMoonLogoIcon extends StatelessWidget {
  Widget build(BuildContext context) {
    return SvgPicture.asset('assets/icons/vector_1_3671.svg');
  }
}
""",
    }
    logo_asset = "assets/icons/vector_1_3671.svg"
    header = CleanDesignTreeNode(
        id="1:9",
        name="Header",
        type=NodeType.STACK,
        stack_placement=StackPlacement(left=0.0, top=50.0, width=200.0, height=30.0),
        children=[
            CleanDesignTreeNode(
                id="1:10",
                name="LogoVector",
                type=NodeType.VECTOR,
                vector_asset_key=logo_asset,
            ),
        ],
    )
    screen = f"""
return Stack(children: [
  Positioned(left: 0, top: 50.0, width: 200.0, height: 30.0, child: Stack(children: [
    SvgPicture.asset('{logo_asset}'),
    Text('Title'),
  ])),
  Positioned(left: 40.7, top: 160.0, width: 332.2, height: 242.7, child: const SizedBox()),
]);
"""
    root = CleanDesignTreeNode(
        id="1:1",
        name="Screen",
        type=NodeType.STACK,
        children=[
            header,
            illustration,
            CleanDesignTreeNode(
                id="1:2",
                name="Subtitle",
                type=NodeType.TEXT,
                text="Thousand of people are usign silent moon  \\nfor smalls meditation ",
            ),
        ],
    )
    patched = reconcile_llm_screen_with_subtrees(
        screen,
        subtree_result=subtree_result,
        planned_files=planned,
        clean_tree=root,
    )
    assert "const GroupWidget()" in patched
    assert "const SilentMoonLogoIcon()" in patched
    assert "SvgPicture.asset" not in patched


def test_replace_inlined_planned_widget_by_asset_overlap() -> None:
    from figma_flutter_agent.generator.subtree_widgets import replace_inlined_planned_widgets
    from figma_flutter_agent.schemas import StackPlacement

    asset = "assets/icons/brand_mark.svg"
    header = CleanDesignTreeNode(
        id="1:10",
        name="Header",
        type=NodeType.STACK,
        stack_placement=StackPlacement(left=12.0, top=8.0, width=120.0, height=24.0),
        children=[
            CleanDesignTreeNode(
                id="1:11",
                name="Mark",
                type=NodeType.VECTOR,
                vector_asset_key=asset,
            ),
        ],
    )
    tree = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        children=[header],
    )
    planned = {
        "lib/widgets/brand_mark.dart": f"""
class BrandMark extends StatelessWidget {{
  Widget build(BuildContext context) {{
    return SvgPicture.asset('{asset}');
  }}
}}
""",
    }
    screen = f"""
    Positioned(
      left: 12.0,
      top: 8.0,
      width: 120.0,
      height: 24.0,
      child: Stack(children: [
        SvgPicture.asset('{asset}'),
        Text('Brand'),
      ]),
    ),
    """
    patched = replace_inlined_planned_widgets(screen, planned_files=planned, clean_tree=tree)
    assert "const BrandMark()" in patched
    assert "SvgPicture.asset" not in patched
    assert "Text('Brand')" not in patched
