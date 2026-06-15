"""Tests for LAW-RESPONSIVE-DEFN layout tier classification."""

from __future__ import annotations

from figma_flutter_agent.generator.checks.layout import (
    classify_layout_responsive_tier,
    validate_responsive_reflow_required,
)
from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.schemas import NodeType


def test_classify_preview_tier_when_artboard_defines_present() -> None:
    source = """
    if (_artboardPreviewWidth > 0 && _artboardPreviewHeight > 0) {
      return ClipRect(child: SizedBox(width: _artboardPreviewWidth, child: child));
    }
    return SizedBox(width: 375.0, child: Stack(children: []));
    """
    assert classify_layout_responsive_tier(source) == "preview"


def test_classify_scaled_tier_for_root_fitted_box() -> None:
    source = """
    return LayoutBuilder(builder: (context, constraints) {
      return Align(
        child: FittedBox(
          fit: BoxFit.scaleDown,
          child: SizedBox(width: 375.0, height: 812.0, child: Stack(children: [])),
        ),
      );
    });
    """
    assert classify_layout_responsive_tier(source, root_type=NodeType.STACK) == "scaled"


def test_classify_reflowed_tier_for_scroll_column_without_scale() -> None:
    source = """
    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [Text('hello')],
      ),
    );
    """
    assert classify_layout_responsive_tier(source, root_type=NodeType.COLUMN) == "reflowed"


def test_classify_reflowed_when_preview_branch_has_fitted_box_only() -> None:
    source = """
    if (_artboardPreviewWidth > 0) {
      return FittedBox(fit: BoxFit.scaleDown, child: SizedBox(width: 375.0, child: body));
    }
    return SingleChildScrollView(
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [body]),
    );
    """
    assert classify_layout_responsive_tier(source, root_type=NodeType.COLUMN) == "reflowed"


def test_require_reflow_gate_blocks_scaled_layout() -> None:
    scaled = """
    return LayoutBuilder(builder: (context, constraints) {
      return FittedBox(
        fit: BoxFit.scaleDown,
        child: SizedBox(width: 375.0, height: 812.0, child: Stack(children: [])),
      );
    });
    """
    try:
        validate_responsive_reflow_required(
            {"lib/generated/demo_layout.dart": scaled},
            [],
            require_reflow=True,
            responsive_enabled=True,
        )
        raised = False
    except GenerationError:
        raised = True
    assert raised is True
