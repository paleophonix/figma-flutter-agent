"""Planned Dart graph freeze and write projection invariants."""

from __future__ import annotations

import pytest

from figma_flutter_agent.errors import PlannedDartGraphError
from figma_flutter_agent.generator.planned.graph import (
    assert_planned_graph_unchanged,
    build_planned_dart_graph,
    finalize_planned_dart_graph,
    planned_graph_content_hash,
    project_write_payload,
    validate_planned_dart_graph,
)


def test_validate_raises_on_stale_widget_import() -> None:
    planned = {
        "lib/features/login/login_screen.dart": (
            "import 'package:demo_app/widgets/missing_widget.dart';\n"
            "class LoginScreen {}\n"
        ),
    }
    graph = build_planned_dart_graph(planned)
    with pytest.raises(PlannedDartGraphError, match="import graph inconsistent"):
        validate_planned_dart_graph(graph, package_name="demo_app")


def test_validate_raises_on_missing_widget_class_body() -> None:
    planned = {
        "lib/features/login/login_screen.dart": (
            "import 'package:flutter/material.dart';\n"
            "class LoginScreen extends StatelessWidget {\n"
            "  @override Widget build(BuildContext c) => MissingWidget();\n"
            "}\n"
        ),
    }
    graph = build_planned_dart_graph(planned)
    with pytest.raises(PlannedDartGraphError, match="without lib/widgets bodies"):
        validate_planned_dart_graph(graph, package_name="demo_app")


def test_finalize_and_project_write_payload_preserves_hash() -> None:
    planned = {
        "lib/features/login/login_screen.dart": (
            "import 'package:flutter/material.dart';\n"
            "class LoginScreen extends StatelessWidget {\n"
            "  const LoginScreen({super.key});\n"
            "  @override Widget build(BuildContext c) => const SizedBox();\n"
            "}\n"
        ),
        "lib/generated/login_layout.dart": (
            "import 'package:flutter/material.dart';\n"
            "class LoginLayout extends StatelessWidget {\n"
            "  const LoginLayout({super.key});\n"
            "  @override Widget build(BuildContext c) => const SizedBox();\n"
            "}\n"
        ),
    }
    frozen = finalize_planned_dart_graph(planned, package_name="demo_app")
    subset = {
        "lib/features/login/login_screen.dart": frozen.files[
            "lib/features/login/login_screen.dart"
        ],
    }
    payload = project_write_payload(frozen, subset)
    assert planned_graph_content_hash(payload) == planned_graph_content_hash(
        {k: payload[k] for k in subset},
    )
    assert_planned_graph_unchanged(frozen, frozen.files, context="test")


def test_assert_planned_graph_unchanged_detects_mutation() -> None:
    planned = {"lib/a.dart": "class A {}"}
    frozen = build_planned_dart_graph(planned)
    with pytest.raises(PlannedDartGraphError, match="mutated after freeze"):
        assert_planned_graph_unchanged(
            frozen,
            {"lib/a.dart": "class A { int x = 1; }"},
            context="unit",
        )
