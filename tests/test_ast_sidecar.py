"""Tests for AST sidecar rule application."""

from __future__ import annotations

from figma_flutter_agent.tools.ast_sidecar import apply_ast_rules


def test_apply_ast_rules_unwraps_scaled_layout_builder() -> None:
    source = """
    Stack(
      children: [
        LayoutBuilder(
          builder: (context, constraints) {
            final double scaleX = constraints.maxWidth / designWidth;
            final double scaleY = constraints.maxHeight / designHeight;
            return SingleChildScrollView(
              child: SizedBox(
                width: constraints.maxWidth,
                height: designHeight * scaleY,
                child: Stack(
                  children: [
                    Positioned(
                      left: 20.0 * scaleX,
                      top: 100.0 * scaleY,
                      child: Text('Hi'),
                    ),
                  ],
                ),
              ),
            );
          },
        ),
      ],
    );
    """
    result = apply_ast_rules(source)
    assert result.backend == "subprocess"
    assert "LayoutBuilder" not in result.source
    assert "scaleX" not in result.source
    assert "left: 20.0" in result.source
    assert "top: 100.0" in result.source


def test_apply_ast_rules_unscale_expressions() -> None:
    source = "Positioned(left: 12.0 * scaleX, top: 8.0 * scaleY, child: Text('x')),"
    result = apply_ast_rules(
        source,
        ("unscale_design_expressions",),
        prefer_subprocess=False,
    )
    assert "scaleX" not in result.source
    assert "left: 12.0" in result.source


def test_apply_ast_rules_strip_viewport_scale_ignores_child_inside_string() -> None:
    source = """
    final double screenScale = screenWidth / canvasWidth;
    Transform.scale(
      scale: screenScale,
      child: Text('child: decoy (parens) inside string'),
    )
    """
    result = apply_ast_rules(
        source,
        ("strip_viewport_scale_transform",),
    )
    assert "Transform.scale" not in result.source
    assert "child: decoy" in result.source


def test_apply_ast_rules_wraps_rigid_row_children() -> None:
    source = """
    Row(
      children: [
        Text('Hello'),
        Expanded(child: Text('Fill')),
      ],
    );
    """
    result = apply_ast_rules(
        source,
        ("wrap_flex_row_column_children",),
    )
    assert "Flexible(fit: FlexFit.loose, child: Text('Hello'))" in result.source
    assert result.source.count("Flexible(") == 1


def test_apply_ast_rules_codegen_pass_with_child_decoy_in_string() -> None:
    source = """
    import 'package:flutter/material.dart';

    class SignInScreen extends StatelessWidget {
      const SignInScreen({super.key});

      @override
      Widget build(BuildContext context) {
        final double screenScale = MediaQuery.of(context).size.width / 375.0;
        return Transform.scale(
          scale: screenScale,
          child: Text('child: not a real param'),
        );
      }
    }
    """
    result = apply_ast_rules(source, ("codegen_pass",))
    assert "Transform.scale" not in result.source
    assert "child: not a real param" in result.source


def test_codegen_pass_repairs_duplicate_child_stutter() -> None:
    source = "ElevatedButton(onPressed: () {}, child: child: child: Text('x'))"
    result = apply_ast_rules(source, ("llm_syntax_repairs",))
    assert "child: child:" not in result.source
    assert "child: Text('x')" in result.source


def test_apply_ast_rules_strip_viewport_scale_with_parens_in_string() -> None:
    source = """
    final double screenScale = screenWidth / canvasWidth;
    Transform.scale(
      scale: screenScale,
      child: Text('note (demo) with parens'),
    )
    """
    result = apply_ast_rules(
        source,
        ("strip_viewport_scale_transform",),
    )
    assert "Transform.scale" not in result.source
    assert "screenScale" not in result.source
    assert "note (demo) with parens" in result.source


def test_llm_syntax_repairs_scales_linearly_on_large_source() -> None:
    """Guard against the O(n^2) scan-state regression in child-param repair rules.

    A ~55KB widget body (just under the sidecar size gate) must complete well
    under a second; the former rebuild-from-zero scan made a 43KB file take ~43s
    (quadratic in file size — the dominant cost of a whole reconcile pass).
    """
    import time

    chunk = (
        "Container(padding: const EdgeInsets.all(8), "
        "child: Text('item', style: TextStyle(fontSize: 14, "
        "color: Color(0xFF333333)))),\n"
    )
    big = (
        "import 'package:flutter/material.dart';\n"
        "Widget build() => Column(children: [\n" + chunk * 450 + "]);\n"
    )
    size = len(big.encode("utf-8"))
    assert 50_000 < size < 65_536, f"fixture must sit under the sidecar gate, got {size}B"
    started = time.monotonic()
    result = apply_ast_rules(big, ("llm_syntax_repairs",))
    elapsed = time.monotonic() - started
    assert result.backend == "subprocess"
    assert elapsed < 5.0, (
        f"llm_syntax_repairs took {elapsed:.1f}s on {size}B (quadratic regression)"
    )
