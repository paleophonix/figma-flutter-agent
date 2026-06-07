"""Emit parse gate (dart format on planned files in temp tree)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from figma_flutter_agent.config import AgentYamlConfig
from figma_flutter_agent.dev.flutter_sdk import resolve_dart_executable
from figma_flutter_agent.generator import validation as validation_module
from figma_flutter_agent.generator.dart.project_validation import (
    _validate_package_imports,
    align_skeleton_pubspec_package_name,
    gate_planned_dart_syntax,
)


def test_require_screen_ir_enables_emit_parse_gate() -> None:
    agent = AgentYamlConfig.model_validate(
        {
            "generation": {
                "use_deterministic_screen": False,
                "use_screen_ir": True,
                "require_screen_ir": True,
                "llm_fallback_to_deterministic": True,
            },
            "validation": {"emit_parse_gate": False},
        }
    )
    assert agent.generation.require_screen_ir is True
    assert agent.generation.use_screen_ir is True
    assert agent.generation.use_deterministic_screen is False
    assert agent.validation.emit_parse_gate is True
    assert agent.generation.llm_fallback_to_deterministic is False


def test_validate_package_imports_accepts_target_app_prefix() -> None:
    planned = {
        "lib/widgets/vuesax_widget.dart": (
            "import 'package:demo_app2/widgets/other_widget.dart';\n"
            "import 'package:flutter/material.dart';\n"
        ),
    }
    assert _validate_package_imports(planned, "demo_app2") is None


def test_validate_package_imports_rejects_wrong_prefix() -> None:
    planned = {
        "lib/widgets/foo_widget.dart": "import 'package:demo_app2/theme/app_colors.dart';\n",
    }
    error = _validate_package_imports(planned, "demo_app")
    assert error is not None
    assert "demo_app2" in error


def test_align_skeleton_pubspec_package_name(tmp_path: Path) -> None:
    pubspec = tmp_path / "pubspec.yaml"
    pubspec.write_text("name: demo_app\n", encoding="utf-8")
    align_skeleton_pubspec_package_name(tmp_path, "demo_app2")
    assert "name: demo_app2" in pubspec.read_text(encoding="utf-8")


def test_gate_rejects_unparseable_widget_dart() -> None:
    if resolve_dart_executable() is None:
        pytest.skip("dart SDK not available")
    planned = {
        "lib/widgets/foo_widget.dart": (
            "import 'package:flutter/material.dart';\n\n"
            "class FooWidget extends StatelessWidget {\n"
            "  @override\n"
            "  Widget build(BuildContext context) => Stack(children: [Text('x'\n"
            ");\n"
            "}\n"
        ),
    }
    outcome = gate_planned_dart_syntax(
        planned,
        package_name="demo_app",
        require_dart_sdk=True,
    )
    assert not outcome.skipped
    assert not outcome.passed
    assert "delimiter" in outcome.detail.lower() or outcome.errors


def test_dart_format_targets_uses_single_batch_for_multiple_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[list[str]] = []
    lib = tmp_path / "lib"
    lib.mkdir()
    a = lib / "a.dart"
    b = lib / "b.dart"
    a.write_text("void main() {}\n", encoding="utf-8")
    b.write_text("void main() {}\n", encoding="utf-8")

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(list(command))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(validation_module, "run_subprocess", fake_run)
    outcome = validation_module._run_dart_format_targets(
        tmp_path,
        dart="dart",
        format_target=[str(a), str(b)],
    )
    assert outcome is None
    assert len(calls) == 1
    assert calls[0][0:2] == ["dart", "format"]
    assert str(a) in calls[0]
    assert str(b) in calls[0]


def test_gate_falls_back_unclosed_paren_screen() -> None:
    if resolve_dart_executable() is None:
        pytest.skip("dart SDK not available")
    planned = {
        "lib/features/sign_up/sign_up_screen.dart": (
            "import 'package:flutter/material.dart';\n\n"
            "class SignUpScreen extends StatelessWidget {\n"
            "  const SignUpScreen({super.key});\n\n"
            "  @override\n"
            "  Widget build(BuildContext context) {\n"
            "    return Stack(children: [Text('x'\n"
            "  }\n"
            "}\n"
        ),
    }
    outcome = gate_planned_dart_syntax(
        planned,
        package_name="demo_app",
        require_dart_sdk=True,
    )
    assert outcome.passed, outcome.errors
    screen = planned["lib/features/sign_up/sign_up_screen.dart"]
    assert "SignUpLayout" in screen
    assert "GeneratedScreenShell" in screen


def test_gate_accepts_minimal_valid_screen() -> None:
    if resolve_dart_executable() is None:
        pytest.skip("dart SDK not available")
    planned = {
        "lib/features/foo/foo_screen.dart": (
            "import 'package:flutter/material.dart';\n\n"
            "class FooScreen extends StatelessWidget {\n"
            "  const FooScreen({super.key});\n\n"
            "  @override\n"
            "  Widget build(BuildContext context) {\n"
            "    return const Scaffold(body: Center(child: Text('ok')));\n"
            "  }\n"
            "}\n"
        ),
    }
    outcome = gate_planned_dart_syntax(
        planned,
        package_name="demo_app",
        require_dart_sdk=True,
    )
    assert outcome.passed
