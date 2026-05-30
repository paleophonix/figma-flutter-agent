"""InkWell stack button label colors synced from the clean tree."""

from __future__ import annotations

from figma_flutter_agent.generator.llm_dart import (
    _patch_stack_filled_buttons_from_tree,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeStyle, NodeType, Sizing


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
    assert "theme.colorScheme.onPrimary" in patched


def test_patch_stack_filled_button_low_contrast_label_on_opaque_fill() -> None:
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
    assert "Color(0xFF000000)" not in patched
    assert "theme.colorScheme.onPrimary" in patched
