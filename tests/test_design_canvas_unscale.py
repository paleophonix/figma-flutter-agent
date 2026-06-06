"""Guard against orphan designWidth after unscale passes."""

from figma_flutter_agent.generator.dart.postprocess import (
    repair_orphan_design_canvas_identifiers,
    unscale_design_expressions,
)


def test_unscale_does_not_introduce_orphan_design_width() -> None:
    source = (
        "LayoutBuilder(builder: (context, constraints) {"
        "return SizedBox(width: constraints.maxWidth < 390 ? constraints.maxWidth : 390);"
        "})"
    )
    updated = unscale_design_expressions(source)
    assert "designWidth" not in updated
    assert "constraints.maxWidth" in updated


def test_unscale_keeps_design_width_when_canvas_const_declared() -> None:
    source = (
        "LayoutBuilder(builder: (context, constraints) {"
        "const double designWidth = 390.0;"
        "return SizedBox(width: constraints.maxWidth, height: 844.0);"
        "})"
    )
    updated = unscale_design_expressions(source)
    assert "width: designWidth" in updated


def test_repair_orphan_design_canvas_identifiers() -> None:
    broken = (
        "SizedBox(width: designWidth < 390 ? constraints.maxWidth : 390, "
        "height: designHeight)"
    )
    repaired = repair_orphan_design_canvas_identifiers(broken)
    assert "designWidth" not in repaired
    assert "constraints.maxWidth < 390" in repaired
    assert "constraints.maxHeight" in repaired
