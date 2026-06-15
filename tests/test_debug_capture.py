"""Tests for dev.debug_capture project-local render snapshots."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from figma_flutter_agent.config import Settings
from figma_flutter_agent.debug.capture import run_project_debug_capture
from figma_flutter_agent.debug.paths import (
    debug_capture_artifact_path,
    figma_reference_png_path,
    screen_capture_dir,
)
from figma_flutter_agent.preview_capture import CaptureMode
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType
from figma_flutter_agent.validation.golden_capture.result import GoldenCaptureResult


@pytest.mark.asyncio
async def test_debug_capture_writes_flat_artifacts_without_figma_duplicate(
    tmp_path: Path,
) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    (project / "pubspec.yaml").write_text("name: demo\n", encoding="utf-8")
    figma_ref = figma_reference_png_path(project, "login")
    figma_ref.parent.mkdir(parents=True)
    figma_ref.write_bytes(b"figma")

    base = Settings()
    settings = base.model_copy(
        update={
            "agent": base.agent.model_copy(
                update={
                    "dev": base.agent.dev.model_copy(update={"debug_capture": True}),
                    "runtime": base.agent.runtime.model_copy(
                        update={"default_capture_mode": CaptureMode.ORACLE.value},
                    ),
                },
            ),
        },
    )

    planned = {
        "lib/features/login/login_screen.dart": (
            "import 'package:flutter/material.dart';\n"
            "class LoginScreen extends StatelessWidget {\n"
            "  const LoginScreen({super.key});\n"
            "  @override Widget build(BuildContext c) => const Text('x');\n"
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

    capture_result = GoldenCaptureResult(png=b"flutter")

    with (
        patch(
            "figma_flutter_agent.debug.capture.capture_planned_in_warm_sandbox",
            return_value=capture_result,
        ),
        patch(
            "figma_flutter_agent.debug.capture.compare_png_bytes",
            return_value=type("R", (), {"changed_ratio": 0.1})(),
        ),
        patch(
            "figma_flutter_agent.debug.capture.render_visual_diff_heatmap_png",
            return_value=b"heatmap",
        ),
    ):
        outcome = await run_project_debug_capture(
            project_dir=project,
            feature_name="login",
            settings=settings,
            planned_files=planned,
            clean_tree=None,
        )

    assert outcome is not None
    capture_root = screen_capture_dir(project, "login")
    assert outcome.capture_dir == capture_root
    assert figma_ref.read_bytes() == b"figma"
    assert not list(capture_root.glob("*_figma.png"))
    assert (
        debug_capture_artifact_path(project, "login", "flutter_render").read_bytes() == b"flutter"
    )
    assert debug_capture_artifact_path(project, "login", "diff_heatmap").is_file()
    manifest_path = debug_capture_artifact_path(project, "login", "manifest")
    assert manifest_path.is_file()
    assert "figma.png" in manifest_path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_debug_capture_persists_in_memory_figma_to_reference_only(
    tmp_path: Path,
) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    (project / "pubspec.yaml").write_text("name: demo\n", encoding="utf-8")

    base = Settings()
    settings = base.model_copy(
        update={
            "agent": base.agent.model_copy(
                update={
                    "dev": base.agent.dev.model_copy(update={"debug_capture": True}),
                    "runtime": base.agent.runtime.model_copy(
                        update={"default_capture_mode": CaptureMode.ORACLE.value},
                    ),
                },
            ),
        },
    )

    with (
        patch(
            "figma_flutter_agent.debug.capture.capture_planned_in_warm_sandbox",
            return_value=GoldenCaptureResult(png=b"flutter"),
        ),
        patch(
            "figma_flutter_agent.debug.capture.compare_png_bytes",
            return_value=type("R", (), {"changed_ratio": 0.0})(),
        ),
        patch(
            "figma_flutter_agent.debug.capture.render_visual_diff_heatmap_png",
            return_value=b"heatmap",
        ),
    ):
        await run_project_debug_capture(
            project_dir=project,
            feature_name="login",
            settings=settings,
            planned_files={"lib/generated/login_layout.dart": "class LoginLayout {}"},
            figma_reference_png=b"from-pipeline",
        )

    assert figma_reference_png_path(project, "login").read_bytes() == b"from-pipeline"
    assert not (screen_capture_dir(project, "login") / "login_figma_reference.png").exists()


@pytest.mark.asyncio
async def test_debug_capture_preview_mode_uses_flutter_warm_sandbox(
    tmp_path: Path,
) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    (project / "pubspec.yaml").write_text("name: demo\n", encoding="utf-8")
    processed = project / ".debug" / "processed"
    processed.mkdir(parents=True)
    (processed / "login_layout.json").write_text(
        '{"id":"root","name":"Root","type":"STACK","children":[]}',
        encoding="utf-8",
    )

    base = Settings()
    settings = base.model_copy(
        update={
            "agent": base.agent.model_copy(
                update={
                    "dev": base.agent.dev.model_copy(update={"debug_capture": True}),
                    "runtime": base.agent.runtime.model_copy(
                        update={"default_capture_mode": CaptureMode.PREVIEW.value},
                    ),
                },
            ),
        },
    )

    with patch(
        "figma_flutter_agent.debug.capture.capture_planned_in_warm_sandbox",
        return_value=GoldenCaptureResult(png=b"flutter-preview"),
    ):
        outcome = await run_project_debug_capture(
            project_dir=project,
            feature_name="login",
            settings=settings,
            planned_files={"lib/generated/login_layout.dart": "class LoginLayout {}"},
            clean_tree=CleanDesignTreeNode(id="root", name="Root", type=NodeType.STACK),
        )

    assert outcome is not None
    assert outcome.flutter_capture_ok is True
    assert outcome.diff_ok is False
    assert (
        debug_capture_artifact_path(project, "login", "preview_capture").read_bytes()
        == b"flutter-preview"
    )
    assert not debug_capture_artifact_path(project, "login", "flutter_render").exists()


@pytest.mark.asyncio
async def test_debug_capture_noop_when_disabled(tmp_path: Path) -> None:
    settings = Settings()
    outcome = await run_project_debug_capture(
        project_dir=tmp_path,
        feature_name="login",
        settings=settings,
        planned_files={},
        clean_tree=None,
    )
    assert outcome is None
