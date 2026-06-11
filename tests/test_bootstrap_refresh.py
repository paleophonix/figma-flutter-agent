"""Tests for compiler-owned bootstrap refresh at plan and emit gates."""

from __future__ import annotations

from figma_flutter_agent.generator.dart.project_validation import gate_planned_dart_syntax
from figma_flutter_agent.generator.planned.reconcile.bootstrap_refresh import (
    PlannedBootstrapContext,
    bootstrap_main_needs_refresh,
    ensure_compiler_bootstrap_planned_files,
    is_agent_generated_bootstrap,
    render_planned_bootstrap_files,
)


def _bootstrap_context() -> PlannedBootstrapContext:
    return PlannedBootstrapContext(
        feature_name="task_management",
        screen_class="TaskManagementScreen",
        app_title="Task Management",
        routing_type="go_router",
        routing_enabled=False,
        generate_dark_mode=False,
        max_web_width=1200,
        architecture="feature_first",
        package_name="cases",
        use_package_imports=True,
        state_management_type="none",
        theme_variant="material_3",
    )


def test_bootstrap_main_needs_refresh_for_flutter_create_template() -> None:
    foreign_main = """
import 'package:flutter/material.dart';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      theme: ThemeData(colorScheme: .fromSeed(seedColor: Colors.deepPurple)),
      home: const SizedBox(),
    );
  }
}
"""
    assert bootstrap_main_needs_refresh(foreign_main)
    assert not is_agent_generated_bootstrap(foreign_main)


def test_ensure_compiler_bootstrap_drops_backslash_main_alias() -> None:
    bootstrap = render_planned_bootstrap_files(_bootstrap_context())
    foreign_main = "void main() {\n  runApp(MaterialApp(\n"
    planned = {
        "lib/main.dart": bootstrap["lib/main.dart"],
        r"lib\main.dart": foreign_main,
    }
    updated = ensure_compiler_bootstrap_planned_files(
        planned,
        bootstrap_files=bootstrap,
        force=True,
    )
    assert r"lib\main.dart" not in updated
    assert "lib/main.dart" in updated
    assert "FigmaFlutterApp" in updated["lib/main.dart"]


def test_ensure_compiler_bootstrap_replaces_foreign_main() -> None:
    foreign_main = "void main() {\n  runApp(MaterialApp(\n"
    bootstrap = render_planned_bootstrap_files(_bootstrap_context())
    updated = ensure_compiler_bootstrap_planned_files(
        {"lib/main.dart": foreign_main},
        bootstrap_files=bootstrap,
        force=True,
    )
    body = updated["lib/main.dart"]
    assert is_agent_generated_bootstrap(body)
    assert "TaskManagementScreen" in body


def test_bootstrap_escapes_apostrophe_in_app_title() -> None:
    context = PlannedBootstrapContext(
        feature_name="task_management",
        screen_class="TaskManagementScreen",
        app_title="today's tasks",
        routing_type="go_router",
        routing_enabled=False,
        generate_dark_mode=False,
        max_web_width=1200,
        architecture="feature_first",
        package_name="cases",
        use_package_imports=True,
        state_management_type="none",
        theme_variant="material_3",
    )
    from figma_flutter_agent.generator.dart.llm_codegen import validate_dart_delimiters

    body = render_planned_bootstrap_files(context)["lib/main.dart"]
    assert "today\\'s tasks" in body
    assert validate_dart_delimiters(body) is None


def test_gate_refreshes_foreign_main_before_delimiter_check() -> None:
    foreign_main = "void main() {\n  runApp(MaterialApp(\n"
    planned = {
        "lib/main.dart": foreign_main,
        "lib/features/task_management/task_management_screen.dart": """
import 'package:flutter/material.dart';
class TaskManagementScreen extends StatelessWidget {
  const TaskManagementScreen({super.key});
  @override
  Widget build(BuildContext context) => const SizedBox();
}
""",
        "lib/generated/task_management_layout.dart": """
import 'package:flutter/material.dart';
class TaskManagementLayout extends StatelessWidget {
  const TaskManagementLayout({super.key});
  @override
  Widget build(BuildContext context) => const SizedBox();
}
""",
    }
    outcome = gate_planned_dart_syntax(
        planned,
        package_name="cases",
        bootstrap_context=_bootstrap_context(),
    )
    assert outcome.passed or outcome.skipped
    assert is_agent_generated_bootstrap(planned["lib/main.dart"])
