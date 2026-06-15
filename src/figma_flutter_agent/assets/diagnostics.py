"""Asset diagnostics for interactive wizard check."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from figma_flutter_agent.config import AssetsConfig
from figma_flutter_agent.dev.wizard.asset_gap import (
    ScreenSvgExportExpectation,
    resolve_screen_asset_export_entries,
)
from figma_flutter_agent.parser.boundaries.assets import discover_asset_path_for_node

_ASSET_SUBDIRS = ("icons", "images", "illustrations")
_ASSET_FILE_SUFFIXES = {".svg", ".png", ".webp", ".jpg", ".jpeg"}


def list_on_disk_asset_files(project_dir: Path) -> tuple[list[str], list[str]]:
    """Return valid and invalid relative paths under ``assets/{icons,images,illustrations}``."""
    valid: list[str] = []
    invalid: list[str] = []
    for folder in _ASSET_SUBDIRS:
        asset_dir = project_dir / "assets" / folder
        if not asset_dir.is_dir():
            continue
        for path in sorted(asset_dir.iterdir()):
            if not path.is_file():
                continue
            rel = f"assets/{folder}/{path.name}"
            if path.suffix.lower() in _ASSET_FILE_SUFFIXES and path.stat().st_size > 0:
                valid.append(rel)
            else:
                invalid.append(rel)
    return valid, invalid


def format_wizard_asset_report(
    project_dir: Path,
    *,
    dump_path: Path | None,
    screen: str | None,
    scope: Literal["assets", "screen", "full"] = "full",
    file_key: str | None = None,
    primary_node_id: str | None = None,
    assets: AssetsConfig | None = None,
) -> tuple[bool, list[str]]:
    """Build human-readable asset audit lines for the interactive wizard.

    Args:
        project_dir: Flutter project root.
        dump_path: Cached Figma frame JSON for screen export comparison.
        screen: Active screen slug for report headers.
        scope: ``assets`` lists on-disk files only; ``screen`` compares the dump
            to ``assets/`` exports; ``full`` includes both.
        file_key: Figma file key for screen-scope gap detection.
        primary_node_id: Screen frame node id for screen-scope gap detection.
        assets: Agent asset settings (illustrations toggle).

    Returns:
        Tuple of pass flag and Rich-marked lines.
    """
    lines: list[str] = []
    valid_files, invalid_files = list_on_disk_asset_files(project_dir)

    if scope == "assets":
        lines.extend(_format_disk_inventory(project_dir, valid_files, invalid_files))
        return len(invalid_files) == 0, lines

    if scope == "screen":
        if dump_path is None or not dump_path.is_file():
            lines.append("[red]No active screen dump available for asset audit.[/red]")
            return False, lines
        if not file_key or not primary_node_id or assets is None:
            lines.append("[red]Screen manifest metadata missing for asset audit.[/red]")
            return False, lines
        return _format_screen_asset_gap(
            project_dir,
            dump_path=dump_path,
            screen=screen,
            file_key=file_key,
            primary_node_id=primary_node_id,
            assets=assets,
            invalid_files=invalid_files,
        )

    lines.extend(_format_disk_inventory(project_dir, valid_files, invalid_files))
    if dump_path is not None and dump_path.is_file() and file_key and primary_node_id and assets:
        lines.append("")
        passed, screen_lines = _format_screen_asset_gap(
            project_dir,
            dump_path=dump_path,
            screen=screen,
            file_key=file_key,
            primary_node_id=primary_node_id,
            assets=assets,
            invalid_files=invalid_files,
        )
        lines.extend(screen_lines)
        return passed and len(invalid_files) == 0, lines
    return len(invalid_files) == 0, lines


def _format_disk_inventory(
    project_dir: Path,
    valid_files: list[str],
    invalid_files: list[str],
) -> list[str]:
    lines: list[str] = ["[bold]Project assets[/bold] (icons / images / illustrations)"]
    any_dir = False
    for folder in _ASSET_SUBDIRS:
        asset_dir = project_dir / "assets" / folder
        folder_files = [path for path in valid_files if path.startswith(f"assets/{folder}/")]
        lines.append(f"[bold]assets/{folder}/[/bold]")
        if not asset_dir.is_dir():
            lines.append("[dim]directory missing (created on fetch/generate)[/dim]")
            continue
        any_dir = True
        if folder_files:
            lines.append(f"{len(folder_files)} file(s):")
            for rel in folder_files:
                lines.append(f"  • {rel.removeprefix(f'assets/{folder}/')}")
        else:
            lines.append("[dim](empty)[/dim]")
    if not any_dir:
        lines.append("[dim]no asset directories yet[/dim]")
    if invalid_files:
        lines.append(f"[red]Invalid/empty:[/red] {', '.join(invalid_files)}")
    return lines


def _export_kind_label(kind: str) -> str:
    if kind == "boundary_svg":
        return "boundary"
    return kind


def _missing_export_hint(missing: tuple[ScreenSvgExportExpectation, ...]) -> str | None:
    if not missing:
        return None
    missing_boundaries = [entry for entry in missing if entry.kind == "boundary_svg"]
    missing_icons = [entry for entry in missing if entry.kind == "icon"]
    hints: list[str] = []
    if missing_boundaries:
        hints.append(
            "render-boundary SVG(s) need live generate or wizard run → full "
            "(launch/offline and dump-only asset export skip the boundary plan)"
        )
    if missing_icons:
        hints.append(
            "missing icon(s) need live sync with FIGMA_ACCESS_TOKEN "
            "(launch/offline does not call Figma Images API)"
        )
    return "[dim]" + "; ".join(hints) + "[/dim]"


def _format_screen_asset_gap(
    project_dir: Path,
    *,
    dump_path: Path,
    screen: str | None,
    file_key: str,
    primary_node_id: str,
    assets: AssetsConfig,
    invalid_files: list[str],
) -> tuple[bool, list[str]]:
    entries = resolve_screen_asset_export_entries(
        dump_path=dump_path,
        file_key=file_key,
        primary_node_id=primary_node_id,
        assets=assets,
    )
    expected = frozenset(entry.node_id for entry in entries)
    covered = frozenset(
        entry.node_id
        for entry in entries
        if discover_asset_path_for_node(project_dir, entry.node_id) is not None
    )
    missing_entries = tuple(
        entry for entry in entries if entry.node_id not in covered
    )
    lines: list[str] = []
    header = f"Required exports ({len(expected)} icon/boundary asset(s))"
    if screen:
        header = f"{header} — screen [bold]{screen}[/bold]"
    lines.append(header)
    if not entries:
        lines.append("[dim]no exportable icons in dump[/dim]")
        return len(invalid_files) == 0, lines

    for entry in sorted(entries, key=lambda item: item.node_id):
        rel = discover_asset_path_for_node(project_dir, entry.node_id)
        kind_label = _export_kind_label(entry.kind)
        if rel is not None:
            lines.append(
                f"  [green]OK[/green] {entry.node_id} [{kind_label}]  {rel}"
            )
        else:
            lines.append(
                f"  [red]MISSING[/red] {entry.node_id} [{kind_label}]"
                f"  → {entry.expected_rel_path}"
            )

    lines.append(
        f"[bold]{len(covered)}/{len(expected)}[/bold] on disk"
        + (
            f", [red]{len(missing_entries)} missing[/red]"
            if missing_entries
            else " [green](complete)[/green]"
        )
    )
    hint = _missing_export_hint(missing_entries)
    if hint is not None:
        lines.append(hint)
    passed = not missing_entries and not invalid_files
    return passed, lines
