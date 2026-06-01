"""Planned dict path normalization for format-gate repairs on Windows."""

from __future__ import annotations

from figma_flutter_agent.generator.planned_dart import (
    canonicalize_planned_path_keys,
    planned_content_for_path,
    repair_planned_format_parse_failures,
)


def test_canonicalize_planned_path_keys() -> None:
    planned = {
        r"lib\features\sign_up\sign_up_screen.dart": "broken",
    }
    canonicalize_planned_path_keys(planned)
    assert r"lib\features\sign_up\sign_up_screen.dart" not in planned
    assert "lib/features/sign_up/sign_up_screen.dart" in planned


def test_repair_format_parse_failures_finds_backslash_key() -> None:
    path = r"lib\features\sign_up\sign_up_screen.dart"
    planned = {
        path: "Widget build(BuildContext c) => Column(children: [Text('a'), Text('b'));"
    }
    errors = (
        "line 1, column 60 of /tmp/sign_up_screen.dart: Expected to find ']'.",
    )
    updated = repair_planned_format_parse_failures(
        planned,
        ("lib/features/sign_up/sign_up_screen.dart",),
        analyze_errors=errors,
    )
    located = planned_content_for_path(updated, path)
    assert located is not None
    _, content = located
    assert "Text('b')" in content
