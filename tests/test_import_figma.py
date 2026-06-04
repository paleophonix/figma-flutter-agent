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
from figma_flutter_agent.batch.asset_export import FileAssetExportResult
from figma_flutter_agent.dev.import_figma import (
    import_figma_frame,
    resolve_import_feature_name,
    upsert_screen_in_manifest,
)
from figma_flutter_agent.schemas import AssetManifest
from figma_flutter_agent.figma.models import FigmaNodesResponse
from figma_flutter_agent.figma.url import FigmaUrlKind, ParsedFigmaInput


def test_resolve_import_feature_name_uses_figma_when_user_empty() -> None:
    manifest = BatchManifest(file_key="k", project_dir=Path("/tmp"), screens=())
    assert (
        resolve_import_feature_name(None, "Background", manifest, "362:319")
        == "background"
    )


def test_resolve_import_feature_name_uses_custom_slug() -> None:
    manifest = BatchManifest(file_key="k", project_dir=Path("/tmp"), screens=())
    assert (
        resolve_import_feature_name("My Screen", "Background", manifest, "362:319")
        == "my_screen"
    )


def test_resolve_import_feature_name_adds_numeric_suffix_on_collision() -> None:
    manifest = BatchManifest(
        file_key="k",
        project_dir=Path("/tmp"),
        screens=(ScreenEntry(feature="background", node_id="1:1"),),
    )
    assert (
        resolve_import_feature_name(None, "Background", manifest, "362:319")
        == "background_2"
    )


def test_resolve_import_feature_name_preserves_slug_for_same_node_id() -> None:
    manifest = BatchManifest(
        file_key="k",
        project_dir=Path("/tmp"),
        screens=(ScreenEntry(feature="legacy_slug", node_id="362:319"),),
    )
    assert (
        resolve_import_feature_name(None, "Background", manifest, "362:319")
        == "legacy_slug"
    )


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
    dump_mock = AsyncMock(
        side_effect=lambda _connector, *, file_key, screen, project_dir: _write_frame_dump(
            project_dir, screen
        )
    )
    monkeypatch.setattr("figma_flutter_agent.dev.import_figma.dump_screen_node", dump_mock)
    export_mock = AsyncMock(
        return_value=FileAssetExportResult(
            manifest=AssetManifest(),
            icon_count=2,
            raster_count=1,
            exported_node_ids=frozenset(),
            failed_node_ids=frozenset(),
            rate_limited=False,
        )
    )
    monkeypatch.setattr(
        "figma_flutter_agent.dev.import_figma.export_assets_for_document",
        export_mock,
    )
    monkeypatch.setattr(
        "figma_flutter_agent.dev.import_figma.sync_fonts_from_figma_document",
        lambda *_args, **_kwargs: None,
    )

    feature, _dump_path, assets = await import_figma_frame(
        connector,
        parsed,
        project_dir=project_dir,
        manifest_path=manifest_path,
        merge=False,
    )

    assert feature == "music_v2"
    assert assets is not None and assets.icon_count == 2
    export_mock.assert_awaited_once()
    manifest = load_batch_manifest(manifest_path)
    assert len(manifest.screens) == 1
    assert manifest.screens[0].feature == "music_v2"


def _write_frame_dump(project_dir: Path, screen: ScreenEntry) -> Path:
    from figma_flutter_agent.batch.manifest import default_dump_path

    dump_path = screen.dump or default_dump_path(project_dir, screen.feature)
    dump_path.parent.mkdir(parents=True, exist_ok=True)
    dump_path.write_text(
        '{"id":"1:3978","name":"Music V2","type":"FRAME","children":[]}',
        encoding="utf-8",
    )
    return dump_path


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

    dump_mock = AsyncMock(
        side_effect=lambda _connector, *, file_key, screen, project_dir: _write_frame_dump(
            project_dir, screen
        )
    )
    monkeypatch.setattr("figma_flutter_agent.dev.import_figma.dump_screen_node", dump_mock)
    export_mock = AsyncMock(
        return_value=FileAssetExportResult(
            manifest=AssetManifest(),
            icon_count=0,
            raster_count=0,
            exported_node_ids=frozenset(),
            failed_node_ids=frozenset(),
            rate_limited=False,
        )
    )
    monkeypatch.setattr(
        "figma_flutter_agent.dev.import_figma.export_assets_for_document",
        export_mock,
    )
    monkeypatch.setattr(
        "figma_flutter_agent.dev.import_figma.sync_fonts_from_figma_document",
        lambda *_args, **_kwargs: None,
    )

    feature, dump_path, _assets = await import_figma_frame(
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
