"""Tests for SVG optimization helpers."""

from figma_flutter_agent.assets.optimize import optimize_svg


def test_optimize_svg_strips_comments_and_whitespace() -> None:
    raw = """<?xml version="1.0"?>
<!-- icon -->
<svg width="24" height="24">
  <rect width="24" height="24"/>
</svg>
"""
    optimized = optimize_svg(raw)

    assert "<?xml" not in optimized
    assert "<!--" not in optimized
    assert "><" in optimized or optimized.count(" ") < raw.count(" ")
