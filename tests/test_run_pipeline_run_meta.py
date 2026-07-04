"""Integration and regression tests for run.meta in run_pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from figma_flutter_agent.config import Settings
from figma_flutter_agent.debug.run_meta import read_run_meta, run_meta_path
from figma_flutter_agent.errors import PipelineError
from figma_flutter_agent.pipeline.llm import LlmPipelineOutcome
from tests.helpers import pipeline_test_dependencies


def _write_minimal_flutter_project(project_dir: Path) -> Path:
    project_dir.mkdir(parents=True, exist_ok=True)
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
    dump_path = project_dir / ".debug" / "raw" / "sign_in_layout.json"
    dump_path.parent.mkdir(parents=True, exist_ok=True)
    dump_path.write_text(
        json.dumps(
            {
                "id": "1:3570",
                "name": "SignIn",
                "type": "FRAME",
                "visible": True,
                "children": [],
            }
        ),
        encoding="utf-8",
    )
    return dump_path


def _write_manifest_checkout_project(project_dir: Path) -> Path:
    project_dir.mkdir(parents=True, exist_ok=True)
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
    (project_dir / "screens.yaml").write_text(
        "\n".join(
            [
                "file_key: abc",
                "screens:",
                "  - feature: checkout",
                "    node_id: 1:3570",
                "    dump: .debug/raw/checkout_layout.json",
            ]
        ),
        encoding="utf-8",
    )
    dump_path = project_dir / ".debug" / "raw" / "checkout_layout.json"
    dump_path.parent.mkdir(parents=True, exist_ok=True)
    dump_path.write_text(
        json.dumps(
            {
                "id": "1:3570",
                "name": "Payment Screen",
                "type": "FRAME",
                "visible": True,
                "children": [],
            }
        ),
        encoding="utf-8",
    )
    return dump_path


@pytest.mark.asyncio
async def test_run_pipeline_reaches_parsed_run_meta_before_llm(tmp_path: Path) -> None:
    """Regression: _complete_run must not shadow outer log (UnboundLocalError)."""
    import figma_flutter_agent.pipeline.run.core as pipeline_module

    project_dir = tmp_path / "project"
    dump_path = _write_minimal_flutter_project(project_dir)
    settings = Settings()
    deps = pipeline_test_dependencies()

    async def stop_after_parsed_check(*args: object, **kwargs: object) -> tuple[object, dict[str, str]]:
        record = read_run_meta(project_dir, "sign_in")
        assert record is not None
        assert record.status == "parsed"
        raise PipelineError("stop_after_parsed_check")

    with (
        patch.object(
            pipeline_module,
            "parse_figma_url",
            return_value=MagicMock(file_key="abc", node_id="1:3570"),
        ),
        patch.object(pipeline_module, "run_llm_and_plan_phase", new=stop_after_parsed_check),
    ):
        with pytest.raises(PipelineError, match="stop_after_parsed_check"):
            await pipeline_module.run_pipeline(
                settings,
                figma_url="https://www.figma.com/design/abc/x?node-id=1-3570",
                project_dir=project_dir,
                feature_name="sign_in",
                dry_run=False,
                sync_enabled=False,
                from_dump=dump_path,
                from_ir=True,
                deps=deps,
            )


@pytest.mark.asyncio
async def test_run_pipeline_from_dump_does_not_raise_unbound_local_on_log(tmp_path: Path) -> None:
    import figma_flutter_agent.pipeline.run.core as pipeline_module

    project_dir = tmp_path / "project"
    dump_path = _write_minimal_flutter_project(project_dir)
    settings = Settings()
    deps = pipeline_test_dependencies()
    llm_outcome = LlmPipelineOutcome(
        plan_settings=settings,
        llm_result=MagicMock(generation=MagicMock(), warnings=(), destination_generations={}),
    )

    with (
        patch.object(
            pipeline_module,
            "parse_figma_url",
            return_value=MagicMock(file_key="abc", node_id="1:3570"),
        ),
        patch.object(
            pipeline_module,
            "run_llm_and_plan_phase",
            new=AsyncMock(return_value=(llm_outcome, {})),
        ),
        patch.object(
            pipeline_module,
            "run_validate_repair_refine_phase",
            new=AsyncMock(return_value=({}, None)),
        ),
    ):
        result = await pipeline_module.run_pipeline(
            settings,
            figma_url="https://www.figma.com/design/abc/x?node-id=1-3570",
            project_dir=project_dir,
            feature_name="sign_in",
            dry_run=True,
            sync_enabled=False,
            from_dump=dump_path,
            deps=deps,
        )

    assert result.clean_tree.name == "SignIn"


@pytest.mark.asyncio
async def test_run_pipeline_single_run_meta_when_manifest_and_frame_differ(tmp_path: Path) -> None:
    import figma_flutter_agent.pipeline.run.core as pipeline_module

    project_dir = tmp_path / "project"
    dump_path = _write_manifest_checkout_project(project_dir)
    settings = Settings()
    deps = pipeline_test_dependencies()

    async def stop_after_parsed(*args: object, **kwargs: object) -> tuple[object, dict[str, str]]:
        assert not run_meta_path(project_dir, "checkout").is_file()
        record = read_run_meta(project_dir, "payment_screen")
        assert record is not None
        assert record.status == "parsed"
        raise PipelineError("stop_after_parsed")

    with (
        patch(
            "figma_flutter_agent.debug.migrate.ensure_project_debug_layout",
            return_value=None,
        ),
        patch.object(
            pipeline_module,
            "parse_figma_url",
            return_value=MagicMock(file_key="abc", node_id="1:3570"),
        ),
        patch.object(pipeline_module, "run_llm_and_plan_phase", new=stop_after_parsed),
    ):
        with pytest.raises(PipelineError, match="stop_after_parsed"):
            await pipeline_module.run_pipeline(
                settings,
                figma_url="https://www.figma.com/design/abc/x?node-id=1-3570",
                project_dir=project_dir,
                feature_name="auto",
                dry_run=False,
                sync_enabled=False,
                from_dump=dump_path,
                from_ir=True,
                deps=deps,
            )

    assert not run_meta_path(project_dir, "checkout").is_file()
    assert run_meta_path(project_dir, "payment_screen").is_file()
