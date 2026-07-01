"""Tests for asset diagnostics."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from figma_flutter_agent.assets.diagnostics import (
    format_wizard_asset_report,
    list_on_disk_asset_files,
)
from figma_flutter_agent.assets.names import expected_svg_export_rel_path
from figma_flutter_agent.config import AssetsConfig
from figma_flutter_agent.dev.wizard.asset_gap import (
    ScreenSvgExportExpectation,
    partition_missing_asset_entries,
)


def test_list_on_disk_asset_files_skips_empty(tmp_path: Path) -> None:
    icons = tmp_path / "assets" / "icons"
    icons.mkdir(parents=True)
    (icons / "ok.svg").write_text("<svg/>", encoding="utf-8")
    (icons / "empty.svg").write_bytes(b"")
    valid, invalid = list_on_disk_asset_files(tmp_path)
    assert "assets/icons/ok.svg" in valid
    assert "assets/icons/empty.svg" in invalid


def test_format_wizard_asset_report_assets_scope(tmp_path: Path) -> None:
    icons = tmp_path / "assets" / "icons"
    icons.mkdir(parents=True)
    (icons / "foo.svg").write_text("<svg/>", encoding="utf-8")
    passed, lines = format_wizard_asset_report(
        tmp_path,
        dump_path=None,
        screen=None,
        scope="assets",
    )
    assert passed
    text = "\n".join(lines)
    assert "assets/icons/" in text
    assert "foo.svg" in text


def test_format_wizard_asset_report_screen_scope_missing_dump(tmp_path: Path) -> None:
    passed, lines = format_wizard_asset_report(
        tmp_path,
        dump_path=tmp_path / "missing.json",
        screen="bank_home",
        scope="screen",
        file_key="abc",
        primary_node_id="1:2",
        assets=AssetsConfig(),
    )
    assert not passed
    assert "No active screen dump" in "\n".join(lines)


def test_expected_svg_export_rel_path_boundary() -> None:
    rel = expected_svg_export_rel_path("Ingridents", "229:342", "boundary_svg")
    assert rel == "assets/illustrations/ingridents_229_342.svg"


def test_format_wizard_asset_report_screen_scope_shows_boundary_gap(tmp_path: Path) -> None:
    dump_path = tmp_path / "raw.json"
    dump_path.write_text("{}", encoding="utf-8")
    icons = tmp_path / "assets" / "icons"
    icons.mkdir(parents=True)
    (icons / "back_103_584.svg").write_text("<svg/>", encoding="utf-8")

    entries = (
        ScreenSvgExportExpectation(
            node_id="103:584",
            layer_name="Back",
            kind="icon",
        ),
        ScreenSvgExportExpectation(
            node_id="229:342",
            layer_name="Ingridents",
            kind="boundary_svg",
        ),
    )

    with patch(
        "figma_flutter_agent.assets.diagnostics.resolve_screen_asset_export_entries",
        return_value=entries,
    ):
        passed, lines = format_wizard_asset_report(
            tmp_path,
            dump_path=dump_path,
            screen="food_details",
            scope="screen",
            file_key="abc",
            primary_node_id="38:1001",
            assets=AssetsConfig(),
        )

    text = "\n".join(lines)
    assert passed
    assert "[green]OK[/green] 103:584 [icon]" in text
    assert "assets/icons/back_103_584.svg" in text
    assert "[yellow]BOUNDARY[/yellow] 229:342 [boundary]" in text
    assert "assets/illustrations/ingridents_229_342.svg" in text
    assert "render-boundary SVG(s) need" in text
    assert "To backfill:" in text
    assert "1/2" in text


def test_partition_missing_asset_entries_splits_blur_boundary_and_downloadable() -> None:
    entries = (
        ScreenSvgExportExpectation(node_id="1:1", layer_name="Ok", kind="icon"),
        ScreenSvgExportExpectation(node_id="2:2", layer_name="Blur", kind="icon"),
        ScreenSvgExportExpectation(node_id="3:3", layer_name="Boundary", kind="boundary_svg"),
        ScreenSvgExportExpectation(node_id="4:4", layer_name="Need", kind="icon"),
    )
    figma_root = {
        "id": "0:0",
        "children": [
            {"id": "2:2", "effects": [{"type": "LAYER_BLUR", "visible": True}]},
        ],
    }
    partition = partition_missing_asset_entries(
        entries,
        covered=frozenset({"1:1"}),
        figma_root=figma_root,
    )
    assert partition.downloadable_missing_ids == frozenset({"4:4"})
    assert partition.api_unexportable_ids == frozenset({"2:2"})
    assert partition.boundary_missing_ids == frozenset({"3:3"})
    assert partition.check_blocking_missing == 1


def test_partition_nested_composite_icon_is_api_skip() -> None:
    entries = (
        ScreenSvgExportExpectation(node_id="1:1", layer_name="Flat", kind="icon"),
        ScreenSvgExportExpectation(node_id="2:2", layer_name="Nested", kind="icon"),
    )
    figma_root = {
        "id": "0:0",
        "type": "FRAME",
        "children": [
            {
                "id": "1:1",
                "type": "GROUP",
                "name": "Flat",
                "visible": True,
                "absoluteBoundingBox": {"width": 40, "height": 40},
                "children": [
                    {"id": "1:2", "type": "ELLIPSE", "visible": True},
                    {"id": "1:3", "type": "VECTOR", "visible": True},
                ],
            },
            {
                "id": "2:2",
                "type": "GROUP",
                "name": "Nested",
                "visible": True,
                "absoluteBoundingBox": {"width": 40, "height": 40},
                "children": [
                    {"id": "2:3", "type": "ELLIPSE", "visible": True},
                    {
                        "id": "2:4",
                        "type": "GROUP",
                        "visible": True,
                        "children": [
                            {"id": "2:5", "type": "VECTOR", "visible": True},
                        ],
                    },
                ],
            },
        ],
    }
    partition = partition_missing_asset_entries(
        entries,
        covered=frozenset(),
        figma_root=figma_root,
    )
    assert partition.downloadable_missing_ids == frozenset({"1:1"})
    assert partition.api_unexportable_ids == frozenset({"2:2"})
    assert partition.check_blocking_missing == 1
