"""Wizard view combat renders helpers."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from figma_flutter_agent.config import Settings
from figma_flutter_agent.dev.view_render_plan import (
    load_clean_tree_from_debug,
    refresh_planned_layout_from_clean_tree,
)
from figma_flutter_agent.dev.view_renders import (
    _capture_settings_for_planned,
    run_view_combat_renders,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType
from figma_flutter_agent.tools.ast_sidecar import AST_SIDECAR_MAX_SOURCE_BYTES
from figma_flutter_agent.validation.golden_capture import GoldenCaptureResult


def _minimal_tree() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="1:2",
        name="Frame",
        type=NodeType.STACK,
        children=[],
    )


def test_load_clean_tree_from_debug_reads_processed_dump(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    processed = project / ".debug" / "processed"
    processed.mkdir(parents=True)
    tree = _minimal_tree()
    (processed / "background_layout.json").write_text(
        json.dumps({"cleanTree": tree.model_dump()}),
        encoding="utf-8",
    )
    loaded = load_clean_tree_from_debug(project, "background")
    assert loaded is not None
    assert loaded.id == "1:2"


def test_refresh_planned_layout_drops_stale_wide_reflow_on_phone_artboard() -> None:
    dump = Path(r"e:/@dev/flutter-demo-project/ataev/.debug/raw/profile_edit_layout.json")
    if not dump.is_file():
        dump = Path("tests/fixtures/layouts/profile_edit_layout.json")
    if not dump.is_file():
        pytest.skip("profile_edit dump not available")
    raw = json.loads(dump.read_text(encoding="utf-8"))
    from figma_flutter_agent.parser.tree import build_clean_tree

    tree, _, _, _ = build_clean_tree(raw)
    stale = {
        "lib/generated/profile_edit_layout.dart": (
            "final width = constraints.maxWidth.clamp(0.0, 390.0);"
            "if (AppBreakpoints.isWideLayout(width)) {}"
        )
    }
    refreshed = refresh_planned_layout_from_clean_tree(
        stale,
        feature_name="profile_edit",
        clean_tree=tree,
        settings=Settings(),
        package_name="demo_app",
        project_dir=dump.parent.parent.parent,
    )
    layout = refreshed["lib/generated/profile_edit_layout.dart"]
    assert "clamp(0.0, 390.0)" not in layout
    assert "isWideLayout" not in layout


def test_capture_settings_extends_timeout_for_warm_sandbox_compile() -> None:
    settings = Settings()
    base = settings.agent.generation.golden_capture_timeout_sec
    updated = _capture_settings_for_planned(
        settings,
        {"lib/generated/background_layout.dart": "Column(children: [])"},
    )
    assert updated.agent.generation.golden_capture_timeout_sec >= 1200.0
    assert updated.agent.generation.golden_capture_timeout_sec >= base


def test_capture_settings_extends_timeout_for_large_layout() -> None:
    settings = Settings()
    base = settings.agent.generation.golden_capture_timeout_sec
    huge = "x" * (AST_SIDECAR_MAX_SOURCE_BYTES + 1)
    updated = _capture_settings_for_planned(
        settings,
        {"lib/generated/background_layout.dart": huge},
    )
    assert updated.agent.generation.golden_capture_timeout_sec >= 1200.0
    assert updated.agent.generation.golden_capture_timeout_sec >= base


@pytest.mark.asyncio
async def test_run_view_combat_renders_writes_session_artifacts(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    (project / "pubspec.yaml").write_text(
        "\n".join(
            [
                "name: demo_app",
                "dependencies:",
                "  flutter:",
                "    sdk: flutter",
                "flutter:",
                "  uses-material-design: true",
            ]
        ),
        encoding="utf-8",
    )
    bundle = project / ".debug" / "dart" / "background_screen.dart"
    bundle.parent.mkdir(parents=True)
    bundle.write_text(
        "\n".join(
            [
                "// --- begin lib/features/background/background_screen.dart ---",
                "class BackgroundScreen extends StatelessWidget {",
                "  const BackgroundScreen({super.key});",
                "  @override",
                "  Widget build(BuildContext context) => const SizedBox();",
                "}",
                "// --- end lib/features/background/background_screen.dart ---",
            ]
        ),
        encoding="utf-8",
    )
    figma_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    flutter_png = b"\x89PNG\r\n\x1a\n" + b"\x01" * 32

    with (
        patch(
            "figma_flutter_agent.dev.view_renders._resolve_figma_reference_png",
            new=AsyncMock(return_value=figma_png),
        ),
        patch(
            "figma_flutter_agent.dev.view_renders.capture_planned_in_warm_sandbox",
            return_value=GoldenCaptureResult(png=flutter_png),
        ),
        patch(
            "figma_flutter_agent.dev.view_renders.render_visual_diff_heatmap_png",
            return_value=b"\x89PNG\r\n\x1a\n" + b"\x02" * 32,
        ),
        patch(
            "figma_flutter_agent.dev.view_renders.compare_png_bytes",
        ) as compare_mock,
    ):
        compare_mock.return_value = type(
            "Diff",
            (),
            {"changed_ratio": 0.01, "passed": True},
        )()
        settings = Settings()
        result = await run_view_combat_renders(
            project,
            feature_name="background",
            bundle_path=bundle,
            settings=settings,
        )

    assert result.flutter_capture_ok
    assert result.diff_ok
    assert result.render_dir.is_dir()
    assert (result.render_dir / "figma_reference.png").is_file()
    assert (result.render_dir / "flutter_render.png").is_file()
    assert (result.render_dir / "diff_heatmap.png").is_file()
