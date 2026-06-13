"""Tests for batch manifest, dump, and generate."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from figma_flutter_agent.batch.dump import dump_screen_node
from figma_flutter_agent.batch.manifest import (
    ScreenEntry,
    default_dump_path,
    load_batch_manifest,
)
from figma_flutter_agent.batch.run import run_batch_generate
from figma_flutter_agent.config import Settings
from figma_flutter_agent.pipeline.result import PipelineResult
from figma_flutter_agent.schemas import CleanDesignTreeNode, DesignTokens, NodeType


def test_load_batch_manifest_resolves_paths(tmp_path: Path) -> None:
    project_dir = tmp_path / "flutter"
    project_dir.mkdir()
    manifest_path = tmp_path / "screens.yaml"
    manifest_path.write_text(
        "\n".join(
            [
                "file_key: abc123",
                "project_dir: flutter",
                "screens:",
                "  - feature: sign_in",
                "    node_id: 1-3570",
                "    dump: .debug/raw/sign_in_layout.json",
            ]
        ),
        encoding="utf-8",
    )

    manifest = load_batch_manifest(manifest_path)

    assert manifest.file_key == "abc123"
    assert manifest.project_dir == project_dir.resolve()
    assert len(manifest.screens) == 1
    assert manifest.screens[0].node_id == "1:3570"
    assert manifest.screens[0].dump == project_dir / ".debug" / "raw" / "sign_in_layout.json"


def test_default_dump_path() -> None:
    path = default_dump_path(Path("/proj"), "sign_in")
    assert path == Path("/proj/.debug/sign_in/primary/raw.json")


@pytest.mark.asyncio
async def test_dump_screen_node_writes_json(tmp_path: Path) -> None:
    connector = MagicMock()
    document = {"id": "1:99", "name": "Frame", "type": "FRAME", "children": []}
    entry = MagicMock()
    entry.document = document
    response = MagicMock()
    response.nodes = {"1:99": entry}
    connector.fetch_nodes = AsyncMock(return_value=response)

    screen = ScreenEntry(feature="demo", node_id="1:99")
    path = await dump_screen_node(
        connector,
        file_key="file",
        screen=screen,
        project_dir=tmp_path,
    )

    assert path.is_file()
    assert json.loads(path.read_text(encoding="utf-8")) == document
    connector.fetch_nodes.assert_awaited_once_with("file", ["1:99"])


@pytest.mark.asyncio
async def test_run_batch_generate_skips_missing_dump(tmp_path: Path) -> None:
    from figma_flutter_agent.batch.manifest import BatchManifest

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "pubspec.yaml").write_text("name: demo\n", encoding="utf-8")
    manifest = BatchManifest(
        file_key="abc",
        project_dir=project_dir,
        screens=(ScreenEntry(feature="missing", node_id="1:1"),),
    )
    settings = Settings(FIGMA_ACCESS_TOKEN=SecretStr("figd_test"))

    report = await run_batch_generate(manifest, settings, dry_run=True, require_dump=True)

    assert not report.passed
    assert report.failures[0].error is not None
    assert "Dump missing" in report.failures[0].error


@pytest.mark.asyncio
async def test_run_batch_generate_from_dump_dry_run(tmp_path: Path) -> None:
    from figma_flutter_agent.batch import run as batch_run_module
    from figma_flutter_agent.batch.manifest import BatchManifest

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
    dump_dir = project_dir / ".debug" / "raw"
    dump_dir.mkdir(parents=True)
    dump_path = dump_dir / "sign_in_layout.json"
    dump_path.write_text(
        json.dumps({"id": "1:3570", "name": "SignIn", "type": "FRAME", "children": []}),
        encoding="utf-8",
    )

    manifest = BatchManifest(
        file_key="abc",
        project_dir=project_dir,
        screens=(ScreenEntry(feature="sign_in", node_id="1:3570", dump=dump_path),),
    )
    settings = Settings()
    pipeline_result = PipelineResult(
        clean_tree=CleanDesignTreeNode(id="1:3570", name="SignIn", type=NodeType.CONTAINER),
        tokens=DesignTokens(),
        planned_files=["lib/generated/sign_in_layout.dart"],
        run_id="test",
    )

    with patch.object(
        batch_run_module,
        "run_pipeline",
        new=AsyncMock(return_value=pipeline_result),
    ) as run_mock:
        report = await run_batch_generate(manifest, settings, dry_run=True)

    run_mock.assert_awaited_once()
    call_kwargs = run_mock.await_args.kwargs
    assert call_kwargs["from_dump"] == dump_path
    assert call_kwargs["require_figma_token"] is False
    assert report.passed
