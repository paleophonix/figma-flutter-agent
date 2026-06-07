"""InkWell stack button label colors synced from the clean tree."""

from __future__ import annotations

from figma_flutter_agent.generator.dart.llm_codegen import (
    _ensure_theme_color_scheme_in_scope,
    _patch_stack_filled_buttons_from_tree,
    _patch_theme_wrapped_color_scheme,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeStyle, NodeType


def test_patch_theme_wrapped_skips_without_local_theme_binding() -> None:
    source = """
    Widget build(BuildContext context) {
      return Theme(
        data: ThemeData(),
        child: Text('x', style: TextStyle(color: Theme.of(context).colorScheme.onPrimary)),
      );
    }
    """
    assert _patch_theme_wrapped_color_scheme(source) == source


def test_ensure_theme_color_scheme_in_scope_without_local_theme() -> None:
    source = """
    Widget build(BuildContext context) {
      return Text('SIGN UP', style: TextStyle(color: theme.colorScheme.onPrimary));
    }
    """
    fixed = _ensure_theme_color_scheme_in_scope(source)
    assert "theme.colorScheme" not in fixed
    assert "Theme.of(context).colorScheme.onPrimary" in fixed


def test_patch_stack_filled_button_label_color() -> None:
    clean = CleanDesignTreeNode(
        id="1:1",
        name="Screen",
        type=NodeType.STACK,
        children=[
            CleanDesignTreeNode(
                id="1:2",
                name="Row",
                type=NodeType.STACK,
                children=[
                    CleanDesignTreeNode(
                        id="1:3",
                        name="Fill",
                        type=NodeType.CONTAINER,
                        style=NodeStyle(background_color="0xFF8E97FD"),
                    ),
                    CleanDesignTreeNode(
                        id="1:4",
                        name="Label",
                        type=NodeType.TEXT,
                        text="SIGN UP",
                        style=NodeStyle(text_color="0xFFFFFFFF"),
                    ),
                ],
            ),
        ],
    )
    screen = """
    Positioned(
      child: Material(
        child: InkWell(
          child: Stack(
            children: [
              Container(
                decoration: BoxDecoration(color: Color(0xFF8E97FD)),
              ),
              Text(
                'SIGN UP',
                style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                  color: Color(0xFF000000),
                ),
              ),
            ],
          ),
        ),
      ),
    ),
    """
    patched = _patch_stack_filled_buttons_from_tree(screen, clean)
    assert "Color(0xFFFFFFFF)" in patched


def test_patch_stack_filled_button_by_value_key() -> None:
    from figma_flutter_agent.generator.figma_anchor import figma_key_token

    clean = CleanDesignTreeNode(
        id="1:1",
        name="Screen",
        type=NodeType.STACK,
        children=[
            CleanDesignTreeNode(
                id="1:2",
                name="Footer",
                type=NodeType.STACK,
                children=[
                    CleanDesignTreeNode(
                        id="1:3",
                        name="Fill",
                        type=NodeType.CONTAINER,
                        style=NodeStyle(background_color="0xFF8E97FD"),
                    ),
                    CleanDesignTreeNode(
                        id="1:4",
                        name="Label",
                        type=NodeType.TEXT,
                        text="SIGN UP",
                        style=NodeStyle(text_color="0xFF000000"),
                    ),
                ],
            ),
        ],
    )
    token = figma_key_token("1:4")
    screen = f"""
    InkWell(
      child: Stack(
        children: [
          Container(decoration: BoxDecoration(color: Color(0xFF8E97FD))),
          Text(
            'SIGN UP',
            key: ValueKey('{token}'),
            style: Theme.of(context).textTheme.bodyLarge?.copyWith(
              color: Color(0xFFFFFFFF),
            ),
          ),
        ],
      ),
    ),
    """
    patched = _patch_stack_filled_buttons_from_tree(screen, clean)
    assert "Color(0xFF000000)" in patched
    assert "Theme.of(context).colorScheme.onPrimary" not in patched


def test_patch_stack_filled_button_preserves_figma_label_color() -> None:
    clean = CleanDesignTreeNode(
        id="1:1",
        name="Screen",
        type=NodeType.STACK,
        children=[
            CleanDesignTreeNode(
                id="1:2",
                name="Footer",
                type=NodeType.STACK,
                children=[
                    CleanDesignTreeNode(
                        id="1:3",
                        name="Fill",
                        type=NodeType.CONTAINER,
                        style=NodeStyle(background_color="0xFF8E97FD"),
                    ),
                    CleanDesignTreeNode(
                        id="1:4",
                        name="Label",
                        type=NodeType.TEXT,
                        text="SIGN UP",
                        style=NodeStyle(text_color="0xFF000000"),
                    ),
                ],
            ),
        ],
    )
    screen = """
    Positioned(
      child: Material(
        child: InkWell(
          child: Stack(
            children: [
              Container(
                decoration: BoxDecoration(color: Color(0xFF8E97FD)),
              ),
              Text(
                'SIGN UP',
                style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                  color: Color(0xFF000000),
                ),
              ),
            ],
          ),
        ),
      ),
    ),
    """
    patched = _patch_stack_filled_buttons_from_tree(screen, clean)
    assert "Color(0xFF000000)" in patched
