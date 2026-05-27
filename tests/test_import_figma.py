"""Tests for Figma file/frame import helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from figma_flutter_agent.batch.manifest import (
    BatchManifest,
    ScreenEntry,
    load_batch_manifest,
    write_batch_manifest,
)
from figma_flutter_agent.dev.import_figma import import_figma_frame, upsert_screen_in_manifest
from figma_flutter_agent.figma.models import FigmaNodesResponse
from figma_flutter_agent.figma.url import FigmaUrlKind, ParsedFigmaInput


def test_upsert_screen_in_manifest_creates_new(tmp_path: Path) -> None:
    manifest_path = tmp_path / "screens.yaml"
    project_dir = tmp_path / "demo"
    project_dir.mkdir()
    screen = ScreenEntry(feature="sign_in", node_id="1:100")

    manifest = upsert_screen_in_manifest(
        manifest_path,
        project_dir=project_dir,
        file_key="abc123",
        screen=screen,
    )

    assert manifest.file_key == "abc123"
    assert len(manifest.screens) == 1
    assert manifest.screens[0].feature == "sign_in"
    assert load_batch_manifest(manifest_path).screens[0].node_id == "1:100"


def test_upsert_screen_in_manifest_replaces_same_node_id(tmp_path: Path) -> None:
    manifest_path = tmp_path / "screens.yaml"
    project_dir = tmp_path / "demo"
    project_dir.mkdir()
    upsert_screen_in_manifest(
        manifest_path,
        project_dir=project_dir,
        file_key="abc123",
        screen=ScreenEntry(feature="old_name", node_id="1:100"),
    )
    upsert_screen_in_manifest(
        manifest_path,
        project_dir=project_dir,
        file_key="abc123",
        screen=ScreenEntry(feature="sign_in", node_id="1:100"),
    )

    manifest = load_batch_manifest(manifest_path)
    assert len(manifest.screens) == 1
    assert manifest.screens[0].feature == "sign_in"


@pytest.mark.asyncio
async def test_import_figma_frame_overwrite_replaces_manifest(tmp_path: Path, monkeypatch) -> None:
    project_dir = tmp_path / "demo"
    project_dir.mkdir()
    manifest_path = project_dir / "screens.yaml"
    write_batch_manifest(
        manifest_path,
        BatchManifest(
            file_key="abc123",
            project_dir=project_dir,
            screens=(ScreenEntry(feature="home", node_id="1:200"),),
        ),
    )
    parsed = ParsedFigmaInput(
        kind=FigmaUrlKind.FRAME,
        file_key="abc123",
        node_id="1:3978",
        source="https://www.figma.com/design/abc123/Test?node-id=1-3978",
    )

    connector = MagicMock()
    connector.fetch_nodes = AsyncMock(
        return_value=FigmaNodesResponse.model_validate(
            {
                "name": "Test",
                "nodes": {
                    "1:3978": {
                        "document": {
                            "id": "1:3978",
                            "name": "Music V2",
                            "type": "FRAME",
                            "children": [],
                        }
                    }
                },
            }
        )
    )
    dump_mock = AsyncMock(side_effect=lambda _connector, *, file_key, screen, project_dir: screen)
    monkeypatch.setattr("figma_flutter_agent.dev.import_figma.dump_screen_node", dump_mock)

    feature, _dump_path = await import_figma_frame(
        connector,
        parsed,
        project_dir=project_dir,
        manifest_path=manifest_path,
        merge=False,
    )

    assert feature == "music_v2"
    manifest = load_batch_manifest(manifest_path)
    assert len(manifest.screens) == 1
    assert manifest.screens[0].feature == "music_v2"


@pytest.mark.asyncio
async def test_import_figma_frame_writes_dump_and_manifest(tmp_path: Path, monkeypatch) -> None:
    project_dir = tmp_path / "demo"
    project_dir.mkdir()
    manifest_path = project_dir / "screens.yaml"
    parsed = ParsedFigmaInput(
        kind=FigmaUrlKind.FRAME,
        file_key="abc123",
        node_id="1:3978",
        source="https://www.figma.com/design/abc123/Test?node-id=1-3978",
    )

    connector = MagicMock()
    connector.fetch_nodes = AsyncMock(
        return_value=FigmaNodesResponse.model_validate(
            {
                "name": "Test",
                "nodes": {
                    "1:3978": {
                        "document": {
                            "id": "1:3978",
                            "name": "Music V2",
                            "type": "FRAME",
                            "children": [],
                        }
                    }
                },
            }
        )
    )

    dump_mock = AsyncMock(side_effect=lambda _connector, *, file_key, screen, project_dir: screen)
    monkeypatch.setattr("figma_flutter_agent.dev.import_figma.dump_screen_node", dump_mock)

    feature, dump_path = await import_figma_frame(
        connector,
        parsed,
        project_dir=project_dir,
        manifest_path=manifest_path,
    )

    assert feature == "music_v2"
    assert dump_path.name == "music_v2_layout.json"
    dump_mock.assert_awaited_once()
    manifest = load_batch_manifest(manifest_path)
    assert manifest.screens[0].feature == "music_v2"
    assert manifest.screens[0].node_id == "1:3978"
