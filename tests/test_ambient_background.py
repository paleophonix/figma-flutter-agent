"""Tests for ambient background responsiveness patching."""

from figma_flutter_agent.generator.ambient_background import (
    collect_ambient_background_children,
    ensure_centered_design_canvas,
    fix_ambient_background_responsiveness,
    patch_scaffold_background_from_tree,
    render_ambient_background_layer,
    resolve_screen_canvas_background_expr,
    sync_ambient_layer_with_foreground_scaling,
)
from figma_flutter_agent.generator.dart.llm_codegen import validate_dart_delimiters
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    StackPlacement,
)


def _sign_in_like_tree() -> CleanDesignTreeNode:
    blob = CleanDesignTreeNode(
        id="1:3572",
        name="Group 6800",
        type=NodeType.STACK,
        sizing=Sizing(width=547.0, height=428.0),
        stack_placement=StackPlacement(left=-41.0, top=-77.0, width=547.0, height=428.0),
        children=[
            CleanDesignTreeNode(
                id="1:3573",
                name="Vector",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/vector_1_3573.svg",
                stack_placement=StackPlacement(left=0.0, top=29.0, width=204.0, height=161.0),
            ),
        ],
    )
    vector = CleanDesignTreeNode(
        id="1:3571",
        name="Vector",
        type=NodeType.VECTOR,
        vector_asset_key="assets/icons/vector_1_3571.svg",
        stack_placement=StackPlacement(left=-101.0, top=92.0, width=255.0, height=258.0),
    )
    button_label = CleanDesignTreeNode(
        id="1:3579",
        name="CONTINUE WITH FACEBOOK",
        type=NodeType.TEXT,
        text="CONTINUE WITH FACEBOOK",
        stack_placement=StackPlacement(left=92.0, top=24.0, width=188.0, height=14.0),
    )
    return CleanDesignTreeNode(
        id="1:3570",
        name="sign in",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[vector, blob, button_label],
    )


def test_collect_ambient_background_children_skips_interactive_rows() -> None:
    tree = _sign_in_like_tree()
    ambient = collect_ambient_background_children(tree)
    assert {node.id for node in ambient} == {"1:3571", "1:3572"}


def test_collect_ambient_background_skips_back_navigation_chrome() -> None:
    back = CleanDesignTreeNode(
        id="1:3603",
        name="Group 6801",
        type=NodeType.STACK,
        sizing=Sizing(width=55.0, height=55.0),
        stack_placement=StackPlacement(left=20.2, top=6.0, width=55.0, height=55.0),
        children=[
            CleanDesignTreeNode(
                id="1:3607",
                name="Vector",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/vector_1_3607.svg",
                stack_placement=StackPlacement(left=18.2, top=18.5, width=18.7, height=18.0),
            ),
        ],
    )
    tree = _sign_in_like_tree()
    tree.children.append(back)
    ambient = collect_ambient_background_children(tree)
    assert "1:3603" not in {node.id for node in ambient}


def test_resolve_screen_canvas_background_ignores_decorative_child_when_root_is_white() -> None:
    tree = _sign_in_like_tree()
    tree.style = NodeStyle(background_color="0xFFFFFFFF")
    tree.children[0].style = NodeStyle(background_color="0xFFFAF8F5")
    assert resolve_screen_canvas_background_expr(tree) is None


def test_patch_scaffold_background_from_tree_keeps_white_when_root_is_white() -> None:
    tree = _sign_in_like_tree()
    tree.style = NodeStyle(background_color="0xFFFFFFFF")
    tree.children[0].style = NodeStyle(background_color="0xFFFAF8F5")
    screen = """
    return Scaffold(
      backgroundColor: const Color(0xFFFFFFFF),
      body: const SizedBox(),
    );
    """
    updated = patch_scaffold_background_from_tree(screen, tree)
    assert "0xFFFAF8F5" not in updated.split("body")[0]
    assert "0xFFFFFFFF" in updated.split("body")[0]


def test_render_ambient_background_layer_uses_centered_design_canvas() -> None:
    tree = _sign_in_like_tree()
    layer = render_ambient_background_layer(tree, uses_svg=True)
    assert layer is not None
    assert "BoxFit.cover" in layer
    assert "clipBehavior: Clip.hardEdge" in layer
    assert "child: SizedBox" in layer
    assert "vector_1_3571.svg" in layer
    assert "Positioned.fill" in layer
    assert "AppColors" not in layer
    assert "ElevatedButton" not in layer


def test_sync_ambient_layer_wraps_legacy_center_sizedbox() -> None:
    screen = """
    return Stack(
      fit: StackFit.expand,
      children: [
        Positioned.fill(
          child: IgnorePointer(
            child: Center(
              child: SizedBox(
                width: 414,
                height: 896,
                child: Stack(
                  children: [
                    Positioned(
                      left: -101.0,
                      child: SvgPicture.asset('assets/icons/vector_1_3571.svg'),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
        Center(
          child: FittedBox(
            fit: BoxFit.contain,
            child: SizedBox(
              width: 414.0,
              height: 896.0,
              child: Stack(children: [Positioned(left: 20.0, child: Text('Hi'))]),
            ),
          ),
        ),
      ],
    );
    """
    synced = sync_ambient_layer_with_foreground_scaling(screen)
    assert synced.count("BoxFit.cover") >= 1
    assert "vector_1_3571.svg" in synced


def test_fix_ambient_background_hoists_layer_behind_centered_canvas() -> None:
    tree = _sign_in_like_tree()
    screen = """
    return Scaffold(
      body: SafeArea(
        top: false,
        bottom: false,
        child: Center(
          child: FittedBox(
            fit: BoxFit.contain,
            child: SizedBox(
              width: 414.0,
              height: 896.0,
              child: Stack(
                children: [
                  Positioned.fill(
                    child: Stack(
                      children: [
                        Positioned(
                          left: -101.0,
                          child: SvgPicture.asset('assets/icons/vector_1_3571.svg'),
                        ),
                      ],
                    ),
                  ),
                  Positioned(
                    left: 20.0,
                    child: Text('CONTINUE WITH FACEBOOK'),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
    """
    patched = fix_ambient_background_responsiveness(screen, tree, uses_svg=True)
    assert "StackFit.expand" in patched
    assert "BoxFit.cover" in patched
    assert "vector_1_3571.svg" in patched
    assert patched.count("vector_1_3571.svg") == 1


def test_ensure_centered_skips_when_ambient_center_layer_already_hoisted() -> None:
    """Hoisted ambient uses ``Center`` (not ``FittedBox`` cover) — must not re-wrap foreground."""
    screen = """
    Widget build(BuildContext context) {
      const double designWidth = 414.0;
      const double designHeight = 896.0;
      return Scaffold(
        body: Stack(
          fit: StackFit.expand,
          children: [
            Positioned.fill(
              child: Center(
                child: SizedBox(
                  width: 414,
                  height: 896,
                  child: Stack(
                    children: [
                      Positioned(
                        left: -101.0,
                        child: SvgPicture.asset('assets/icons/vector_1_3571.svg'),
                      ),
                    ],
                  ),
                ),
              ),
            ),
            Center(
              child: GestureDetector(
                onTap: () {},
                child: SizedBox(
                  width: 414,
                  height: 896,
                  child: Stack(
                    children: [
                      Positioned(left: 20.0, top: 200.0, width: 374.0, height: 63.0, child: Text('Hi')),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      );
    }
    """
    patched = ensure_centered_design_canvas(screen)
    assert patched.count("Positioned.fill") == 1
    assert patched.count("vector_1_3571.svg") == 1


def test_ensure_centered_skips_when_ambient_cover_already_hoisted() -> None:
    """Do not duplicate nested Positioned blocks from inside the cover layer."""
    screen = """
    Widget build(BuildContext context) {
      const double designWidth = 414.0;
      const double designHeight = 896.0;
      return Scaffold(
      body: SafeArea(
        child: Stack(
          fit: StackFit.expand,
          children: [
            Positioned.fill(
              child: FittedBox(
                fit: BoxFit.cover,
                child: SizedBox(
                  width: 414,
                  height: 896,
                  child: Stack(
                    children: [
                      Positioned(
                        left: -101.0,
                        child: SvgPicture.asset('assets/icons/vector_1_3571.svg'),
                      ),
                    ],
                  ),
                ),
              ),
            ),
            Positioned(left: 20.0, top: 200.0, width: 374.0, height: 63.0, child: Text('Hi')),
          ],
        ),
      ),
    );
    }
    """
    patched = ensure_centered_design_canvas(screen)
    assert patched.count("vector_1_3571.svg") == 1
    assert patched.count("Positioned.fill") == 1
    assert "Text('Hi')" in patched


def test_ensure_centered_design_canvas_wraps_absolute_stack() -> None:
    screen = """
    Widget build(BuildContext context) {
      const double designWidth = 414.0;
      const double designHeight = 896.0;
      return Scaffold(
        body: Stack(
          children: [
            Positioned(left: 20.0, top: 200.0, width: 374.0, height: 63.0, child: Text('Hi')),
          ],
        ),
      );
    }
    """
    patched = ensure_centered_design_canvas(screen)
    assert "Positioned.fill" in patched
    assert "child: Center" in patched
    assert "width: 414" in patched


def test_fix_ambient_hoist_safe_area_center_has_no_double_close_parens() -> None:
    tree = _sign_in_like_tree()
    screen = """
    return Scaffold(
      body: SafeArea(
        top: false,
        bottom: false,
        child: Center(
          child: FittedBox(
            fit: BoxFit.contain,
            child: SizedBox(
              width: 414.0,
              height: 896.0,
              child: Stack(
                clipBehavior: Clip.none,
                children: [
                  Positioned(
                    left: -101.0,
                    child: SvgPicture.asset('assets/icons/vector_1_3571.svg'),
                  ),
                  Positioned(left: 20.0, child: Text('Hi')),
                ],
              ),
            ),
          ),
        ),
      ),
    );
    """
    patched = fix_ambient_background_responsiveness(screen, tree, uses_svg=True)
    assert validate_dart_delimiters(patched) is None
    assert "\n        )),\n" not in patched
    assert patched.count("vector_1_3571.svg") == 1
    assert "Positioned.fill" in patched


def test_fix_ambient_injects_layer_when_child_already_expand_stack() -> None:
    tree = _sign_in_like_tree()
    screen = """
    return Scaffold(
      body: SafeArea(
        child: Stack(
          fit: StackFit.expand,
          children: [
            Center(
              child: SizedBox(
                width: 414.0,
                height: 896.0,
                child: Stack(
                  children: [
                    Positioned(
                      left: -101.0,
                      child: SvgPicture.asset('assets/icons/vector_1_3571.svg'),
                    ),
                    Positioned(left: 20.0, child: Text('Hi')),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
    """
    patched = fix_ambient_background_responsiveness(screen, tree, uses_svg=True)
    assert validate_dart_delimiters(patched) is None
    assert patched.count("vector_1_3571.svg") == 1
    assert "Positioned.fill" in patched
    assert patched.count("Positioned(left: 20.0") == 1


def test_fix_ambient_background_hoists_behind_scaffold_body_without_safe_area() -> None:
    tree = _sign_in_like_tree()
    screen = """
    return Scaffold(
      backgroundColor: const Color(0xFFFFFFFF),
      body: Center(
        child: SizedBox(
          width: 414.0,
          height: 896.0,
          child: Stack(
            children: [
              Positioned(
                left: -101.0,
                child: SvgPicture.asset('assets/icons/vector_1_3571.svg'),
              ),
              Positioned(
                left: 20.0,
                child: Text('CONTINUE WITH FACEBOOK'),
              ),
            ],
          ),
        ),
      ),
    );
    """
    patched = fix_ambient_background_responsiveness(screen, tree, uses_svg=True)
    assert "StackFit.expand" in patched
    assert "vector_1_3571.svg" in patched
    assert "body: Stack(\n          fit: StackFit.expand" in patched

