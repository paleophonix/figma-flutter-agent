"""Tests for Figma ValueKey anchors in generated Dart."""

from __future__ import annotations

import re

from figma_flutter_agent.fixtures.screens_manifest import load_layout_tree
from figma_flutter_agent.generator.figma_anchor import (
    _finalize_spliced_dart_fragment,
    _normalize_layout_block_for_screen_embed,
    _sanitize_stack_children_segment,
    ensure_screen_stack_paint_order,
    inject_figma_keys_into_screen,
    inject_missing_layout_positioned,
)
from figma_flutter_agent.generator.layout_widget import _apply_stack_position
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    StackPlacement,
)


def test_apply_stack_position_includes_figma_value_key() -> None:
    node = CleanDesignTreeNode(
        id="1:99",
        name="x",
        type=NodeType.TEXT,
        text="Hi",
        stack_placement=StackPlacement(left=10.0, top=20.0, width=100.0, height=20.0),
    )
    positioned = _apply_stack_position(
        node,
        "Text('Hi')",
        parent_type=NodeType.STACK,
    )
    assert "key: ValueKey('figma-1_99')" in positioned
    assert positioned.startswith("Positioned(left:")


def test_inject_figma_keys_into_llm_screen() -> None:
    tree = load_layout_tree("sign_up_and_sign_in")
    screen = """
    Stack(
      children: [
        Positioned(
          left: 40.0,
          top: 380.0,
          width: 334.0,
          height: 56.0,
          child: Text('GOOGLE'),
        ),
      ],
    );
    """
    updated = inject_figma_keys_into_screen(screen, tree)
    assert "ValueKey('figma-social-row')" in updated or "ValueKey('figma-social_row')" in updated or "ValueKey('figma-social-row-bg')" in updated


def test_inject_missing_layout_button_from_deterministic_layout() -> None:
    facebook = CleanDesignTreeNode(
        id="1:10",
        name="Facebook",
        type=NodeType.BUTTON,
        stack_placement=StackPlacement(left=20.0, top=200.0, width=374.0, height=63.0),
        children=[],
    )
    google = CleanDesignTreeNode(
        id="1:20",
        name="Google",
        type=NodeType.BUTTON,
        stack_placement=StackPlacement(left=20.0, top=280.0, width=374.0, height=63.0),
        children=[],
    )
    root = CleanDesignTreeNode(
        id="1:1",
        name="screen",
        type=NodeType.STACK,
        children=[facebook, google],
    )
    layout = """
    Stack(
      children: [
        Positioned(
          left: 20.0,
          top: 200.0,
          width: 374.0,
          height: 63.0,
          key: ValueKey('figma-1_10'),
          child: Text('CONTINUE WITH FACEBOOK'),
        ),
        Positioned(
          left: 20.0,
          top: 280.0,
          width: 374.0,
          height: 63.0,
          key: ValueKey('figma-1_20'),
          child: Text('CONTINUE WITH GOOGLE'),
        ),
      ],
    );
    """
    screen = """
    Stack(
      children: [
        Positioned(
          left: 20.0,
          top: 200.0,
          width: 374.0,
          height: 63.0,
          key: ValueKey('figma-1_10'),
          child: Text('CONTINUE WITH FACEBOOK'),
        ),
      ],
    );
    """
    updated = inject_missing_layout_positioned(screen, layout, root)
    assert "figma-1_20" in updated
    assert updated.index("figma-1_10") < updated.index("figma-1_20")


def test_inject_missing_large_illustration_from_layout() -> None:
    hero = CleanDesignTreeNode(
        id="1:3662",
        name="Hero",
        type=NodeType.STACK,
        stack_placement=StackPlacement(left=-3.0, top=0.0, width=423.0, height=504.0),
        children=[],
    )
    footer = CleanDesignTreeNode(
        id="1:3974",
        name="Copy",
        type=NodeType.TEXT,
        stack_placement=StackPlacement(left=58.0, top=534.0, width=200.0, height=40.0),
        text="We are what we do",
    )
    root = CleanDesignTreeNode(
        id="1:3661",
        name="screen",
        type=NodeType.STACK,
        children=[hero, footer],
    )
    layout = """
    Stack(
      children: [
        Positioned(
          left: -3.0,
          top: 0.0,
          width: 423.0,
          height: 504.0,
          key: ValueKey('figma-1_3662'),
          child: SvgPicture.asset('assets/icons/hero.svg'),
        ),
        Positioned(
          left: 58.0,
          top: 534.0,
          width: 200.0,
          height: 40.0,
          key: ValueKey('figma-1_3974'),
          child: Text('We are what we do'),
        ),
      ],
    );
    """
    screen = """
    Stack(
      children: [
        Positioned(
          left: 58.0,
          top: 534.0,
          width: 200.0,
          height: 40.0,
          key: ValueKey('figma-1_3974'),
          child: Text('We are what we do'),
        ),
      ],
    );
    """
    updated = inject_missing_layout_positioned(screen, layout, root)
    assert "figma-1_3662" in updated
    assert updated.index("figma-1_3662") < updated.index("figma-1_3974")


def test_inject_missing_layout_text_from_deterministic_layout() -> None:
    forgot = CleanDesignTreeNode(
        id="1:3600",
        name="Forgot Password?",
        type=NodeType.TEXT,
        text="Forgot Password?",
        stack_placement=StackPlacement(left=139.7, top=703.5, width=120.0, height=14.0),
    )
    root = CleanDesignTreeNode(
        id="1:1",
        name="screen",
        type=NodeType.STACK,
        children=[forgot],
    )
    layout = """
    Stack(
      children: [
        Positioned(
          left: 139.7,
          top: 703.5,
          key: ValueKey('figma-1_3600'),
          child: Text('Forgot Password?'),
        ),
      ],
    );
    """
    screen = """
    Stack(
      children: [
        Positioned(
          left: 20.0,
          top: 200.0,
          key: ValueKey('figma-1_10'),
          child: Text('LOG IN'),
        ),
      ],
    );
    """
    updated = inject_missing_layout_positioned(screen, layout, root)
    assert "figma-1_3600" in updated
    assert "Forgot Password?" in updated


def test_inject_missing_layout_text_skips_when_copy_already_present() -> None:
    forgot = CleanDesignTreeNode(
        id="1:3600",
        name="Forgot Password?",
        type=NodeType.TEXT,
        text="Forgot Password?",
        stack_placement=StackPlacement(left=139.7, top=703.5),
    )
    welcome = CleanDesignTreeNode(
        id="1:3589",
        name="Welcome Back!",
        type=NodeType.TEXT,
        text="Welcome Back!",
        stack_placement=StackPlacement(left=103.0, top=133.5),
    )
    root = CleanDesignTreeNode(
        id="1:1",
        name="screen",
        type=NodeType.STACK,
        children=[welcome, forgot],
    )
    layout = """
    Stack(
      children: [
        Positioned(left: 103.0, top: 133.5, key: ValueKey('figma-1_3589'), child: Text('Welcome Back!')),
        Positioned(left: 139.7, top: 703.5, key: ValueKey('figma-1_3600'), child: Text('Forgot Password?')),
      ],
    );
    """
    screen = """
    Stack(
      children: [
        Positioned(
          left: 103.0,
          top: 133.5,
          key: ValueKey('figma-1_3589'),
          child: Text('Welcome Back!'),
        ),
      ],
    );
    """
    updated = inject_missing_layout_positioned(screen, layout, root)
    assert updated.count("Welcome Back!") == 1
    assert "Forgot Password?" in updated


def test_ensure_screen_stack_paint_order_puts_background_first() -> None:
    screen = """
    return Stack(
      fit: StackFit.expand,
      children: [
        Positioned(left: 0, top: 10, child: Text('LOG IN')),
        const SignInBackground(),
        SignInMainContent(onTap: () {}),
      ],
    );
    """
    updated = ensure_screen_stack_paint_order(screen)
    bg_index = updated.find("SignInBackground")
    content_index = updated.find("SignInMainContent")
    overlay_index = updated.find("Positioned(left: 0, top: 10")
    assert 0 <= bg_index < content_index < overlay_index


def test_normalize_layout_block_inlines_orphan_text_scaler_refs() -> None:
    block = "Text('LOG IN', textScaler: textScaler, style: s)"
    normalized = _normalize_layout_block_for_screen_embed(block)
    assert "textScaler: MediaQuery.textScalerOf(context)" in normalized
    assert "textScaler: textScaler" not in normalized


def test_upgrade_incomplete_layout_back_button_circle() -> None:
    back = CleanDesignTreeNode(
        id="1:3603",
        name="Group 6801",
        type=NodeType.STACK,
        stack_placement=StackPlacement(left=38.0, top=64.0, width=55.0, height=55.0),
        children=[
            CleanDesignTreeNode(
                id="1:3607",
                name="arrow",
                type=NodeType.VECTOR,
                vector_asset_key="vector_1_3607",
                stack_placement=StackPlacement(left=20.0, top=18.0, width=15.0, height=12.0),
            ),
        ],
    )
    root = CleanDesignTreeNode(
        id="1:1",
        name="screen",
        type=NodeType.STACK,
        children=[back],
    )
    layout = """
    Stack(
      children: [
        Positioned(
          left: 38.0,
          top: 64.0,
          width: 55.0,
          height: 55.0,
          key: ValueKey('figma-1_3603'),
          child: Container(
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(color: Color(0xFFE5E7EB)),
            ),
            child: Center(child: Icon(Icons.arrow_back)),
          ),
        ),
      ],
    );
    """
    screen = """
    Stack(
      children: [
        Positioned(
          left: 38.0,
          top: 64.0,
          width: 55.0,
          height: 55.0,
          key: ValueKey('figma-1_3603'),
          child: SvgPicture.asset('assets/vectors/vector_1_3607.svg'),
        ),
      ],
    );
    """
    updated = inject_missing_layout_positioned(screen, layout, root)
    assert "BoxShape.circle" in updated
    assert "Border.all" in updated


def test_inject_missing_layout_skips_entirely_when_main_content_widget_present() -> None:
    root = CleanDesignTreeNode(
        id="1:1",
        name="screen",
        type=NodeType.STACK,
        children=[
            CleanDesignTreeNode(
                id="1:3576",
                name="Facebook",
                type=NodeType.BUTTON,
                stack_placement=StackPlacement(left=20.0, top=204.5, width=374.0, height=63.0),
            ),
        ],
    )
    layout = """
    Stack(
      children: [
        Positioned(left: 20.0, top: 204.5, width: 374.0, height: 63.0, key: ValueKey('figma-1_3576'), child: Text('FB')),
      ],
    );
    """
    screen = """
    Stack(
      children: [
        const SignInBackground(),
        SignInMainContent(emailController: c),
      ],
    );
    """
    updated = inject_missing_layout_positioned(
        screen,
        layout,
        root,
        companion_sources=(),
    )
    assert updated.strip() == screen.strip()
    assert "figma-1_3576" not in updated


def test_inject_missing_layout_skips_when_copy_only_in_extracted_widget() -> None:
    welcome = CleanDesignTreeNode(
        id="1:3589",
        name="Welcome Back!",
        type=NodeType.TEXT,
        text="Welcome Back!",
        stack_placement=StackPlacement(left=103.0, top=133.5),
    )
    facebook = CleanDesignTreeNode(
        id="1:3576",
        name="Facebook",
        type=NodeType.BUTTON,
        stack_placement=StackPlacement(left=20.0, top=204.5, width=374.0, height=63.0),
        children=[
            CleanDesignTreeNode(
                id="1:3577",
                name="CONTINUE WITH FACEBOOK",
                type=NodeType.TEXT,
                text="CONTINUE WITH FACEBOOK",
                stack_placement=StackPlacement(left=92.0, top=24.5, width=200.0, height=14.0),
            ),
        ],
    )
    root = CleanDesignTreeNode(
        id="1:1",
        name="screen",
        type=NodeType.STACK,
        children=[welcome, facebook],
    )
    layout = """
    Stack(
      children: [
        Positioned(left: 103.0, top: 133.5, key: ValueKey('figma-1_3589'), child: Text('Welcome Back!')),
        Positioned(left: 20.0, top: 204.5, width: 374.0, height: 63.0, key: ValueKey('figma-1_3576'), child: Text('CONTINUE WITH FACEBOOK')),
      ],
    );
    """
    screen = """
    Stack(
      children: [
        const SignInBackground(),
        SignInMainContent(
          emailController: _emailController,
          passwordController: _passwordController,
        ),
      ],
    );
    """
    widget_source = """
    class SignInMainContent extends StatelessWidget {
      Widget build(BuildContext context) {
        return Stack(
          children: [
            Positioned(
              left: 103.0,
              top: 133.5,
              child: Text('Welcome Back!'),
            ),
            Positioned(
              left: 20.0,
              top: 204.5,
              width: 374.0,
              height: 63.0,
              child: ElevatedButton(
                child: Text('CONTINUE WITH FACEBOOK'),
              ),
            ),
          ],
        );
      }
    }
    """
    updated = inject_missing_layout_positioned(
        screen,
        layout,
        root,
        companion_sources=(widget_source,),
    )
    assert "figma-1_3589" not in updated
    assert "figma-1_3576" not in updated
    assert updated.count("Welcome Back!") == 0
    assert "SignInMainContent" in updated


def test_upgrade_incomplete_layout_social_row_from_deterministic_layout() -> None:
    google = CleanDesignTreeNode(
        id="1:3590",
        name="Group 6796",
        type=NodeType.BUTTON,
        stack_placement=StackPlacement(left=20.0, top=287.5, width=374.0, height=63.0),
        children=[
            CleanDesignTreeNode(
                id="1:3592",
                name="Rectangle 210",
                type=NodeType.CONTAINER,
                style=NodeStyle(border_color="0xFFEBEAEC", border_width=1.0),
                stack_placement=StackPlacement(left=0.0, top=0.0, width=374.0, height=63.0),
            ),
            CleanDesignTreeNode(
                id="1:3593",
                name="CONTINUE WITH GOOGLE",
                type=NodeType.TEXT,
                text="CONTINUE WITH GOOGLE",
                stack_placement=StackPlacement(left=92.6, top=24.5, width=188.5, height=14.0),
            ),
        ],
    )
    root = CleanDesignTreeNode(
        id="1:1",
        name="screen",
        type=NodeType.STACK,
        children=[google],
    )
    layout = """
    Stack(
      children: [
        Positioned(
          left: 20.0,
          top: 287.5,
          width: 374.0,
          height: 63.0,
          key: ValueKey('figma-1_3590'),
          child: Material(
            color: Colors.transparent,
            child: InkWell(
              child: Stack(
                clipBehavior: Clip.none,
                children: [
                  Container(
                    decoration: BoxDecoration(
                      color: const Color(0xFFFFFFFF),
                      border: Border.all(color: Color(0xFFEBEAEC)),
                    ),
                  ),
                  Text('CONTINUE WITH GOOGLE'),
                ],
              ),
            ),
          ),
        ),
      ],
    );
    """
    screen = """
    Stack(
      children: [
        Positioned(
          left: 20.0,
          top: 287.5,
          width: 374.0,
          height: 63.0,
          key: ValueKey('figma-1_3590'),
          child: OutlinedButton(
            onPressed: () {},
            style: OutlinedButton.styleFrom(
              side: const BorderSide(color: Color(0xFFEBEAEC)),
            ),
            child: Text('CONTINUE WITH GOOGLE'),
          ),
        ),
      ],
    );
    """
    updated = inject_missing_layout_positioned(screen, layout, root)
    assert "OutlinedButton" not in updated
    assert "InkWell" in updated
    assert "BoxDecoration" in updated


def test_inject_positioned_batch_joins_with_comma_newline() -> None:
    root = CleanDesignTreeNode(
        id="1:1",
        name="screen",
        type=NodeType.STACK,
        children=[
            CleanDesignTreeNode(
                id="1:10",
                name="A",
                type=NodeType.BUTTON,
                stack_placement=StackPlacement(left=1.0, top=10.0, width=10.0, height=10.0),
            ),
            CleanDesignTreeNode(
                id="1:20",
                name="B",
                type=NodeType.BUTTON,
                stack_placement=StackPlacement(left=2.0, top=20.0, width=10.0, height=10.0),
            ),
        ],
    )
    layout = """
    Stack(
      children: [
        Positioned(left: 1.0, top: 10.0, width: 10.0, height: 10.0, key: ValueKey('figma-1_10'), child: Text('A')),
        Positioned(left: 2.0, top: 20.0, width: 20.0, height: 10.0, key: ValueKey('figma-1_20'), child: Text('B')),
      ],
    );
    """
    screen = """
    FittedBox(
      fit: BoxFit.contain,
      child: Stack(
        children: [
          const SignInBackground(),
        ],
      ),
    );
    """
    updated = inject_missing_layout_positioned(screen, layout, root)
    assert "figma-1_10" in updated
    assert "figma-1_20" in updated
    assert updated.index("figma-1_10") < updated.index("figma-1_20")
    between = updated[updated.index("figma-1_10") : updated.index("figma-1_20")]
    assert "), " in between or "),\n" in between


def test_sanitize_stack_children_segment_removes_orphan_commas() -> None:
    dirty = ",\n        const SignInBackground(),\n,\n      const Foo(),\n"
    cleaned = _sanitize_stack_children_segment(dirty)
    assert cleaned.startswith("const SignInBackground()")
    assert "\n,\n" not in cleaned
    assert not cleaned.strip().startswith(",")


def test_inject_decorative_only_when_companion_sources_present() -> None:
    welcome = CleanDesignTreeNode(
        id="1:3589",
        name="Welcome Back!",
        type=NodeType.TEXT,
        text="Welcome Back!",
        stack_placement=StackPlacement(left=103.0, top=133.5),
    )
    facebook = CleanDesignTreeNode(
        id="1:3576",
        name="Facebook",
        type=NodeType.BUTTON,
        stack_placement=StackPlacement(left=20.0, top=204.5, width=374.0, height=63.0),
    )
    root = CleanDesignTreeNode(
        id="1:1",
        name="screen",
        type=NodeType.STACK,
        children=[welcome, facebook],
    )
    layout = """
    Stack(
      children: [
        Positioned(left: 103.0, top: 133.5, key: ValueKey('figma-1_3589'), child: Text('Welcome Back!')),
        Positioned(left: 20.0, top: 204.5, width: 374.0, height: 63.0, key: ValueKey('figma-1_3576'), child: Text('FB')),
      ],
    );
    """
    screen = "Stack(children: [const SignInMainContent()]);"
    companion = """
    class SignInMainContent extends StatelessWidget {
      Widget build(BuildContext context) {
        return Stack(children: [
          Positioned(left: 103.0, top: 133.5, child: Text('Welcome Back!')),
        ]);
      }
    }
    """
    updated = inject_missing_layout_positioned(
        screen,
        layout,
        root,
        companion_sources=(companion,),
    )
    assert "figma-1_3589" not in updated
    assert "figma-1_3576" not in updated


def test_upgrade_incomplete_layout_skips_covered_companion_nodes() -> None:
    from figma_flutter_agent.generator.figma_anchor import upgrade_incomplete_layout_positioned

    root = CleanDesignTreeNode(
        id="1:1",
        name="screen",
        type=NodeType.STACK,
        children=[
            CleanDesignTreeNode(
                id="1:3576",
                name="Facebook",
                type=NodeType.BUTTON,
                stack_placement=StackPlacement(left=20.0, top=204.5, width=374.0, height=63.0),
            ),
        ],
    )
    layout = """
    Positioned(
      left: 20.0,
      top: 204.5,
      width: 374.0,
      height: 63.0,
      key: ValueKey('figma-1_3576'),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: () {},
          child: Stack(children: [Text('CONTINUE WITH FACEBOOK')]),
        ),
      ),
    );
    """
    screen = """
    Positioned(
      left: 20.0,
      top: 204.5,
      width: 374.0,
      height: 63.0,
      key: ValueKey('figma-1_3576'),
      child: Text('CONTINUE WITH FACEBOOK'),
    );
    """
    companion = """
    Positioned(
      key: ValueKey('figma-1_3576'),
      child: Material(
        child: InkWell(
          child: Stack(children: [Text('CONTINUE WITH FACEBOOK')]),
        ),
      ),
    );
    """
    updated = upgrade_incomplete_layout_positioned(
        screen,
        layout,
        root,
        companion_sources=(companion,),
    )
    assert updated == screen


def test_inject_missing_layout_comma_between_existing_child_and_batch() -> None:
    root = CleanDesignTreeNode(
        id="1:1",
        name="screen",
        type=NodeType.STACK,
        children=[
            CleanDesignTreeNode(
                id="1:3601",
                name="sign up link",
                type=NodeType.TEXT,
                text="SIGN UP",
                stack_placement=StackPlacement(left=60.4, top=822.0, width=200.0, height=20.0),
            ),
        ],
    )
    layout = """
    Stack(
      children: [
        Positioned(
          left: 60.4,
          top: 822.0,
          width: 200.0,
          height: 20.0,
          key: ValueKey('figma-1_3601'),
          child: Text('SIGN UP'),
        ),
      ],
    );
    """
    screen = """
    Stack(
      children: [
        Positioned(
          left: 20.0,
          top: 100.0,
          width: 374.0,
          height: 63.0,
          key: ValueKey('figma-1_1000'),
          child: Text('LOG IN'),
        )
      ],
    );
    """
    updated = inject_missing_layout_positioned(screen, layout, root)
    assert "figma-1_3601" in updated
    assert "figma-1_1000" in updated
    assert not re.search(r"\)\s*\n\s*Positioned\(\s*\n\s*left:\s*60\.4", updated)
    assert re.search(r"\)\s*,\s*\n\s*Positioned\(\s*\n\s*left:\s*60\.4", updated)


def test_inject_missing_layout_strips_leading_comma_before_positioned_batch() -> None:
    root = CleanDesignTreeNode(
        id="1:1",
        name="screen",
        type=NodeType.STACK,
        children=[
            CleanDesignTreeNode(
                id="1:10",
                name="A",
                type=NodeType.BUTTON,
                stack_placement=StackPlacement(left=1.0, top=10.0, width=10.0, height=10.0),
            ),
        ],
    )
    layout = """
    Stack(
      children: [
        Positioned(left: 1.0, top: 10.0, width: 10.0, height: 10.0, key: ValueKey('figma-1_10'), child: Text('A')),
      ],
    );
    """
    screen = """
    FittedBox(
      fit: BoxFit.contain,
      child: Stack(
        children: [
    ,
          const SignInBackground(),
        ],
      ),
    );
    """
    updated = inject_missing_layout_positioned(screen, layout, root)
    assert "figma-1_10" in updated
    assert "\n,\n" not in updated
    assert "children: [\n    ," not in updated


def test_finalize_spliced_dart_fragment_reverts_unbalanced_splice() -> None:
    prior = "return Stack(children: [const Text('ok')]);"
    broken = "return Stack(children: [const Text('ok'),));"
    assert (
        _finalize_spliced_dart_fragment(prior, broken, label="test splice")
        == prior
    )
