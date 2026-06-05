"""Minified (single-line) screen body bracket repairs."""

from __future__ import annotations

from figma_flutter_agent.generator.dart.syntax_repairs import sanitize_emit_screen_syntax


def test_sanitize_minified_log_in_garbage_tail() -> None:
    broken = (
        "return Stack(children: ["
        "Positioned(child: Semantics(child: Material(type: MaterialType.transparency, child: "
        "MouseRegion(child: GestureDetector(child: Text.rich(TextSpan(children: ["
        "TextSpan(text: 'LOG IN', recognizer: TapGestureRecognizer()..onTap = () {})"
        "]), textScaler: textScaler, textAlign: TextAlign.left)), )))]))), "
        "Positioned(left: 58.0, child: Text('x'))]);"
    )
    fixed = sanitize_emit_screen_syntax(broken)
    assert ")))]))))," not in fixed
    assert ")))])))))" not in fixed
    assert ")))])))," not in fixed
    assert "textAlign: TextAlign.left)), )), Positioned" in fixed
