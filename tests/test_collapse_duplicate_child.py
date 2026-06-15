"""Tests for duplicate child: parameter collapse."""

from __future__ import annotations

from figma_flutter_agent.generator.dart.syntax_repairs import (
    apply_llm_dart_syntax_repairs,
    collapse_duplicate_child_named_params,
    fix_misplaced_child_before_named_params,
)


def test_collapse_duplicate_child_named_params() -> None:
    source = "ElevatedButton(onPressed: () {}, child: child: child: child: Text('x'))"
    fixed = collapse_duplicate_child_named_params(source)
    assert "child: child:" not in fixed
    assert "child: Text('x')" in fixed


def test_fix_misplaced_child_before_named_params() -> None:
    source = (
        "SocialButton( child: key: const ValueKey('figma-1:3576'), "
        "onPressed: () {}, child: key: const ValueKey('x'))"
    )
    fixed = fix_misplaced_child_before_named_params(source)
    assert "child: key:" not in fixed
    assert "key: const ValueKey('figma-1:3576')" in fixed


def test_apply_llm_dart_syntax_repairs_combined() -> None:
    source = "Foo(child: child: child: key: const ValueKey('a'))"
    fixed = apply_llm_dart_syntax_repairs(source)
    assert fixed == "Foo(key: const ValueKey('a'))"
