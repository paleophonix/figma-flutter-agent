import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from figma_flutter_agent.config import AgentYamlConfig, GenerationConfig, Settings
from figma_flutter_agent.errors import LlmError
from figma_flutter_agent.generator.dart.project_validation import ProjectAnalyzeResult
from figma_flutter_agent.parser.dedup import DedupResult
from figma_flutter_agent.schemas import (
    AssetManifest,
    CleanDesignTreeNode,
    DesignTokens,
    FlutterGenerationResponse,
    NodeType,
)
from figma_flutter_agent.stages.fetch import FigmaFetchResult
from figma_flutter_agent.stages.llm_repair import LlmRepairStageResult
from figma_flutter_agent.stages.parse import FigmaParseResult
from tests.helpers import (
    mock_fetch_components,
    mock_fetch_styles,
    mock_fetch_variables,
    pipeline_test_dependencies,
    write_minimal_batch_manifest,
)


def _mock_fetch_result() -> FigmaFetchResult:
    root = {"id": "1:1", "name": "Screen", "type": "FRAME", "visible": True, "children": []}
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
async def test_pipeline_runs_llm_in_thread_pool(tmp_path: Path) -> None:
    import figma_flutter_agent.pipeline.run as pipeline_module

    async_started = asyncio.Event()
    async_finished = asyncio.Event()

    async def fake_fetch_nodes(*args: Any, **kwargs: Any) -> MagicMock:
        await async_started.wait()
        entry = MagicMock()
        entry.document = {"id": "1:1", "name": "Screen", "type": "FRAME", "children": []}
        response = MagicMock()
        response.nodes = {"1:1": entry}
        return response

    async def fake_side_task() -> None:
        async_started.set()
        await asyncio.sleep(0.05)
        async_finished.set()

    async def slow_generate_async(*args: Any, **kwargs: Any) -> FlutterGenerationResponse:
        await asyncio.sleep(0.2)
        return FlutterGenerationResponse(
            screen_code="""
class ScreenScreen extends StatelessWidget {
  const ScreenScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final textScaler = MediaQuery.textScalerOf(context);
    return GeneratedScreenShell(child: const Text('Screen'));
  }
}
"""
        )

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
    write_minimal_batch_manifest(project_dir)

    settings = Settings(
        FIGMA_ACCESS_TOKEN=SecretStr("figd_test"),
        ANTHROPIC_API_KEY=SecretStr("sk-ant-test"),
        LLM_PROVIDER="anthropic",
    )
    settings.agent = AgentYamlConfig(
        generation=GenerationConfig(use_deterministic_screen=False),
    )

    connector = MagicMock()
    connector.fetch_nodes = fake_fetch_nodes
    connector.fetch_variables = mock_fetch_variables
    connector.fetch_styles = mock_fetch_styles
    connector.fetch_components = mock_fetch_components

    llm = MagicMock()
    llm.generate_async = slow_generate_async
    llm_factory = MagicMock(return_value=llm)
    deps = pipeline_test_dependencies(connector=connector, create_llm_client=llm_factory)

    async def _skip_repair(request: Any) -> LlmRepairStageResult:
        return LlmRepairStageResult(
            planned_files=request.planned_files,
            llm_result=request.llm_result,
        )

    with (
        patch.object(
            pipeline_module,
            "parse_figma_url",
            return_value=MagicMock(file_key="abc", node_id="1:1"),
        ),
        patch.object(pipeline_module, "fetch_figma_frame", side_effect=_fake_fetch_figma_frame),
        patch.object(pipeline_module, "parse_figma_frame", side_effect=_fake_parse_figma_frame),
        patch(
            "figma_flutter_agent.stages.write.validate_dart_project",
            return_value=ProjectAnalyzeResult(passed=True, detail="stubbed analyze"),
        ),
        patch.object(pipeline_module, "run_analyze_repair_loop", side_effect=_skip_repair),
    ):
        side_task = asyncio.create_task(fake_side_task())
        await pipeline_module.run_pipeline(
            settings,
            figma_url="https://www.figma.com/design/abc/x?node-id=1-1",
            project_dir=project_dir,
            dry_run=False,
            sync_enabled=False,
            deps=deps,
        )
        await side_task

    assert async_finished.is_set()
    assert llm_factory.call_count >= 1


@pytest.mark.asyncio
async def test_dry_run_plans_deterministic_screen_without_llm(tmp_path: Path) -> None:
    import figma_flutter_agent.pipeline.run as pipeline_module

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
    write_minimal_batch_manifest(project_dir)

    settings = Settings(
        FIGMA_ACCESS_TOKEN=SecretStr("figd_test"),
    )

    llm_factory = MagicMock()
    deps = pipeline_test_dependencies(create_llm_client=llm_factory)

    with (
        patch.object(
            pipeline_module,
            "parse_figma_url",
            return_value=MagicMock(file_key="abc", node_id="1:1"),
        ),
        patch.object(pipeline_module, "fetch_figma_frame", side_effect=_fake_fetch_figma_frame),
        patch.object(pipeline_module, "parse_figma_frame", side_effect=_fake_parse_figma_frame),
    ):
        result = await pipeline_module.run_pipeline(
            settings,
            figma_url="https://www.figma.com/design/abc/x?node-id=1-1",
            project_dir=project_dir,
            dry_run=True,
            sync_enabled=False,
            deps=deps,
        )

    llm_factory.assert_not_called()
    assert "lib/generated/screen_layout.dart" in result.planned_files
    assert "lib/features/screen/screen_screen.dart" in result.planned_files


@pytest.mark.asyncio
async def test_dry_run_skips_llm_client(tmp_path: Path) -> None:
    import figma_flutter_agent.pipeline.run as pipeline_module

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
    write_minimal_batch_manifest(project_dir)

    settings = Settings(
        FIGMA_ACCESS_TOKEN=SecretStr("figd_test"),
        ANTHROPIC_API_KEY=SecretStr("sk-ant-test"),
        LLM_PROVIDER="anthropic",
    )

    llm_factory = MagicMock()
    deps = pipeline_test_dependencies(create_llm_client=llm_factory)

    with (
        patch.object(
            pipeline_module,
            "parse_figma_url",
            return_value=MagicMock(file_key="abc", node_id="1:1"),
        ),
        patch.object(pipeline_module, "fetch_figma_frame", side_effect=_fake_fetch_figma_frame),
        patch.object(pipeline_module, "parse_figma_frame", side_effect=_fake_parse_figma_frame),
    ):
        result = await pipeline_module.run_pipeline(
            settings,
            figma_url="https://www.figma.com/design/abc/x?node-id=1-1",
            project_dir=project_dir,
            dry_run=True,
            sync_enabled=False,
            deps=deps,
        )

    llm_factory.assert_not_called()
    assert result.planned_files


@pytest.mark.asyncio
async def test_format_dry_run_output_omits_design_by_default(tmp_path: Path) -> None:
    import figma_flutter_agent.pipeline.run as pipeline_module
    from figma_flutter_agent.pipeline.dry_run import format_dry_run_output

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
    write_minimal_batch_manifest(project_dir)

    settings = Settings(
        FIGMA_ACCESS_TOKEN=SecretStr("figd_test"),
    )

    llm_factory = MagicMock()
    deps = pipeline_test_dependencies(create_llm_client=llm_factory)

    with (
        patch.object(
            pipeline_module,
            "parse_figma_url",
            return_value=MagicMock(file_key="abc", node_id="1:1"),
        ),
        patch.object(pipeline_module, "fetch_figma_frame", side_effect=_fake_fetch_figma_frame),
        patch.object(pipeline_module, "parse_figma_frame", side_effect=_fake_parse_figma_frame),
    ):
        result = await pipeline_module.run_pipeline(
            settings,
            figma_url="https://www.figma.com/design/abc/x?node-id=1-1",
            project_dir=project_dir,
            dry_run=True,
            sync_enabled=False,
            deps=deps,
        )

    llm_factory.assert_not_called()
    payload = json.loads(format_dry_run_output(result))
    assert "cleanTree" not in payload
    assert "tokens" not in payload
    assert payload["summary"]["plannedFileCount"] >= 1


@pytest.mark.asyncio
async def test_pipeline_falls_back_to_deterministic_when_llm_fails(tmp_path: Path) -> None:
    import figma_flutter_agent.pipeline.run as pipeline_module

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
    write_minimal_batch_manifest(project_dir)

    settings = Settings(
        FIGMA_ACCESS_TOKEN=SecretStr("figd_test"),
        ANTHROPIC_API_KEY=SecretStr("sk-ant-test"),
        LLM_PROVIDER="anthropic",
    )
    settings.agent = AgentYamlConfig(
        generation=GenerationConfig(
            use_deterministic_screen=False,
            llm_fallback_to_deterministic=True,
        ),
    )

    llm = MagicMock()
    llm.generate_async = AsyncMock(side_effect=LlmError("LLM response validation failed"))
    llm_factory = MagicMock(return_value=llm)
    deps = pipeline_test_dependencies(create_llm_client=llm_factory)

    with (
        patch.object(
            pipeline_module,
            "parse_figma_url",
            return_value=MagicMock(file_key="abc", node_id="1:1"),
        ),
        patch.object(pipeline_module, "fetch_figma_frame", side_effect=_fake_fetch_figma_frame),
        patch.object(pipeline_module, "parse_figma_frame", side_effect=_fake_parse_figma_frame),
        patch.object(pipeline_module, "export_figma_assets", return_value=AssetManifest()),
        patch("figma_flutter_agent.stages.write.validate_dart_project"),
    ):
        result = await pipeline_module.run_pipeline(
            settings,
            figma_url="https://www.figma.com/design/abc/x?node-id=1-1",
            project_dir=project_dir,
            dry_run=False,
            sync_enabled=False,
            deps=deps,
        )

    assert any("deterministic layout fallback" in warning for warning in result.warnings)
    assert "lib/generated/screen_layout.dart" in result.planned_files
    assert "lib/features/screen/screen_screen.dart" in result.planned_files


@pytest.mark.asyncio
async def test_pipeline_raises_when_llm_fails_and_fallback_disabled(tmp_path: Path) -> None:
    import figma_flutter_agent.pipeline.run as pipeline_module

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
    write_minimal_batch_manifest(project_dir)

    settings = Settings(
        FIGMA_ACCESS_TOKEN=SecretStr("figd_test"),
        ANTHROPIC_API_KEY=SecretStr("sk-ant-test"),
        LLM_PROVIDER="anthropic",
    )
    settings.agent = AgentYamlConfig(
        generation=GenerationConfig(
            use_deterministic_screen=False,
            llm_fallback_to_deterministic=False,
        ),
    )

    llm = MagicMock()
    llm.generate_async = AsyncMock(side_effect=LlmError("LLM response validation failed"))
    llm_factory = MagicMock(return_value=llm)
    deps = pipeline_test_dependencies(create_llm_client=llm_factory)

    with (
        patch.object(
            pipeline_module,
            "parse_figma_url",
            return_value=MagicMock(file_key="abc", node_id="1:1"),
        ),
        patch.object(pipeline_module, "fetch_figma_frame", side_effect=_fake_fetch_figma_frame),
        patch.object(pipeline_module, "parse_figma_frame", side_effect=_fake_parse_figma_frame),
        patch.object(pipeline_module, "export_figma_assets", return_value=AssetManifest()),
        patch("figma_flutter_agent.stages.write.validate_dart_project"),
        pytest.raises(LlmError, match="LLM response validation failed"),
    ):
        await pipeline_module.run_pipeline(
            settings,
            figma_url="https://www.figma.com/design/abc/x?node-id=1-1",
            project_dir=project_dir,
            dry_run=False,
            sync_enabled=False,
            deps=deps,
        )
