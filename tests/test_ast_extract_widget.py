"""Tests for AST sidecar widget extract/replace by figma id."""

from __future__ import annotations

from figma_flutter_agent.tools.ast_sidecar import (
    extract_widget_by_figma_id,
    replace_widget_by_figma_id,
)


def test_extract_and_replace_widget_by_figma_id() -> None:
    source = """
    Stack(
      children: [
        Positioned(
          key: ValueKey('figma-social-row'),
          left: 40.0,
          top: 380.0,
          child: Text('OLD'),
        ),
      ],
    );
    """
    snippet = extract_widget_by_figma_id(source, "social-row")
    assert snippet is not None
    assert "Text('OLD')" in snippet
    replacement = (
        "Positioned("
        "key: ValueKey('figma-social-row'), "
        "left: 40.0, top: 380.0, child: Text('NEW'),"
        ")"
    )
    updated = replace_widget_by_figma_id(source, "social-row", replacement)
    assert updated is not None
    assert "Text('NEW')" in updated
    assert "Text('OLD')" not in updated
