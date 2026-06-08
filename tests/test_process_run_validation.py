"""Subprocess timeout coverage for Dart validation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.dart import project_validation
from figma_flutter_agent.tools.process_run import FLUTTER_PUB_GET_TIMEOUT_SEC


def test_run_flutter_pub_get_returns_timeout_result(tmp_path: Path) -> None:
    project_dir = tmp_path / "app"
    project_dir.mkdir()
    (project_dir / "pubspec.yaml").write_text(
        "name: demo\nenvironment:\n  sdk: '^3.12.0'\n",
        encoding="utf-8",
    )
    with patch(
        "figma_flutter_agent.generator.codegen.run_pub_get",
        side_effect=GenerationError("flutter pub get timed out"),
    ):
        outcome = project_validation._run_flutter_pub_get(project_dir, "/flutter/bin/flutter")
    assert outcome is not None
    assert outcome.passed is False
    assert "timed out" in outcome.detail
    assert str(int(FLUTTER_PUB_GET_TIMEOUT_SEC)) in outcome.detail
