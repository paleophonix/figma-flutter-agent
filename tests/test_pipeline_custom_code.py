from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from figma_flutter_agent.config import AgentYamlConfig, GenerationConfig, Settings
from figma_flutter_agent.parser.dedup import DedupResult
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    DesignTokens,
    NodeType,
)
from figma_flutter_agent.stages.fetch import FigmaFetchResult
from figma_flutter_agent.stages.parse import FigmaParseResult
from tests.helpers import pipeline_test_dependencies


def _mock_fetch_result() -> FigmaFetchResult:
    root = {
        "id": "1:1",
        "name": "Screen",
        "type": "FRAME",
        "visible": True,
        "children": [],
    }
    return FigmaFetchResult(
        file_key="abc",
        node_id="1:1",
        root=root,
        variables_payload=None,
        published_styles={},
        components={},
    )


def _mock_parse_result() -> FigmaParseResult:
    return FigmaParseResult(
        tokens=DesignTokens(),
        clean_tree=CleanDesignTreeNode(id="1:1", name="Screen", type=NodeType.CONTAINER),
        absolute_ratio=0.0,
        dedup_result=DedupResult(),
        cluster_summary={},
    )


async def _fake_fetch_figma_frame(*args: Any, **kwargs: Any) -> FigmaFetchResult:
    return _mock_fetch_result()


def _fake_parse_figma_frame(*args: Any, **kwargs: Any) -> FigmaParseResult:
    return _mock_parse_result()


@pytest.mark.asyncio
async def test_full_pipeline_custom_code_preservation(tmp_path: Path) -> None:
    """Run full run_pipeline, insert custom code, run again, and verify preservation."""
    from figma_flutter_agent import pipeline as pipeline_module

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "pubspec.yaml").write_text(
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

    settings = Settings(
        FIGMA_ACCESS_TOKEN=SecretStr("figd_test"),
    )
    settings.agent = AgentYamlConfig(generation=GenerationConfig(use_deterministic_screen=True))

    with (
        patch.object(
            pipeline_module,
            "parse_figma_url",
            return_value=MagicMock(file_key="abc", node_id="1:1"),
        ),
        patch.object(pipeline_module, "fetch_figma_frame", side_effect=_fake_fetch_figma_frame),
        patch.object(pipeline_module, "parse_figma_frame", side_effect=_fake_parse_figma_frame),
        patch("figma_flutter_agent.stages.write.validate_dart_project"),
    ):
        await pipeline_module.run_pipeline(
            settings,
            figma_url="https://www.figma.com/design/abc/x?node-id=1-1",
            project_dir=project_dir,
            dry_run=False,
            sync_enabled=False,
            deps=pipeline_test_dependencies(),
        )

    screen_path = project_dir / "lib" / "features" / "screen" / "screen_screen.dart"
    assert screen_path.exists()
    original = screen_path.read_text(encoding="utf-8")
    assert "// <custom-code>" in original

    custom_snippet = "\n    // PRESERVED_MARKER_12345\n"
    updated = original.replace(
        "// <custom-code>",
        f"// <custom-code>{custom_snippet}",
        1,
    )
    screen_path.write_text(updated, encoding="utf-8")

    with (
        patch.object(
            pipeline_module,
            "parse_figma_url",
            return_value=MagicMock(file_key="abc", node_id="1:1"),
        ),
        patch.object(pipeline_module, "fetch_figma_frame", side_effect=_fake_fetch_figma_frame),
        patch.object(pipeline_module, "parse_figma_frame", side_effect=_fake_parse_figma_frame),
        patch("figma_flutter_agent.stages.write.validate_dart_project"),
    ):
        await pipeline_module.run_pipeline(
            settings,
            figma_url="https://www.figma.com/design/abc/x?node-id=1-1",
            project_dir=project_dir,
            dry_run=False,
            sync_enabled=False,
            deps=pipeline_test_dependencies(),
        )

    regen = screen_path.read_text(encoding="utf-8")
    assert "PRESERVED_MARKER_12345" in regen
