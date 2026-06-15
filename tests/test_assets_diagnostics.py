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
from figma_flutter_agent.dev.wizard.asset_gap import ScreenSvgExportExpectation


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
    assert not passed
    assert "[green]OK[/green] 103:584 [icon]" in text
    assert "assets/icons/back_103_584.svg" in text
    assert "[red]MISSING[/red] 229:342 [boundary]" in text
    assert "assets/illustrations/ingridents_229_342.svg" in text
    assert "render-boundary SVG(s) need live generate" in text
    assert "1/2" in text
