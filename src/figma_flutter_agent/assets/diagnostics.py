"""Asset diagnostics for interactive wizard check."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from figma_flutter_agent.assets.names import asset_filename
from figma_flutter_agent.config import AssetsConfig
from figma_flutter_agent.dev.wizard.asset_gap import (
    ScreenAssetGapPartition,
    ScreenSvgExportExpectation,
    partition_missing_asset_entries,
    resolve_asset_export_entries_from_fetch,
    resolve_screen_asset_export_entries,
)
from figma_flutter_agent.parser.boundaries.assets import (
    build_asset_node_index,
    lookup_asset_path_for_node,
)
from figma_flutter_agent.pipeline.dump_prefetch import ScreenDumpPrefetch

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
    dump_prefetch: ScreenDumpPrefetch | None = None,
    has_figma_token: bool = False,
    gap_partition: ScreenAssetGapPartition | None = None,
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
        dump_prefetch: Optional preflight parse snapshot to avoid re-parsing the dump.
        has_figma_token: When true, backfill hints reference the download prompt.
        gap_partition: Optional precomputed missing-export partition from preflight.

    Returns:
        Tuple of pass flag and Rich-marked lines.
    """
    lines: list[str] = []

    if scope == "assets":
        valid_files, invalid_files = list_on_disk_asset_files(project_dir)
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
            invalid_files=[],
            dump_prefetch=dump_prefetch,
            has_figma_token=has_figma_token,
            gap_partition=gap_partition,
        )

    valid_files, invalid_files = list_on_disk_asset_files(project_dir)
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
            dump_prefetch=dump_prefetch,
            has_figma_token=has_figma_token,
            gap_partition=gap_partition,
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


def _missing_export_hint(
    partition: ScreenAssetGapPartition, *, has_figma_token: bool
) -> str | None:
    if partition.check_blocking_missing == 0 and not partition.boundary_missing_ids:
        if not partition.api_unexportable_ids:
            return None
    hints: list[str] = []
    if partition.downloadable_missing_ids:
        if has_figma_token:
            hints.append("confirm the download prompt below, or use [bold]list → assets[/bold]")
        else:
            hints.append(
                "set FIGMA_ACCESS_TOKEN, then [bold]list → assets[/bold] or [bold]run → full[/bold]"
            )
    if partition.api_unexportable_ids:
        hints.append(
            f"{len(partition.api_unexportable_ids)} icon(s) need raster fallback PNG "
            "(confirm download below or use [bold]run → full[/bold])"
        )
    if partition.boundary_missing_ids:
        hints.append(
            f"{len(partition.boundary_missing_ids)} render-boundary SVG(s) need "
            "[bold]run → full[/bold] or live generate"
        )
    return "[yellow]To backfill:[/yellow] " + "; ".join(hints)


def _resolve_screen_export_entries(
    *,
    dump_path: Path,
    file_key: str,
    primary_node_id: str,
    assets: AssetsConfig,
    dump_prefetch: ScreenDumpPrefetch | None,
) -> tuple[ScreenSvgExportExpectation, ...]:
    if dump_prefetch is not None and dump_prefetch.matches_dump(dump_path):
        return resolve_asset_export_entries_from_fetch(
            dump_prefetch.fetch_result,
            primary_node_id=primary_node_id,
            assets=assets,
            parse_result=dump_prefetch.parse_result,
        )
    return resolve_screen_asset_export_entries(
        dump_path=dump_path,
        file_key=file_key,
        primary_node_id=primary_node_id,
        assets=assets,
    )


def _format_screen_asset_gap(
    project_dir: Path,
    *,
    dump_path: Path,
    screen: str | None,
    file_key: str,
    primary_node_id: str,
    assets: AssetsConfig,
    invalid_files: list[str],
    dump_prefetch: ScreenDumpPrefetch | None = None,
    has_figma_token: bool = False,
    gap_partition: ScreenAssetGapPartition | None = None,
) -> tuple[bool, list[str]]:
    asset_index = build_asset_node_index(project_dir)
    entries = _resolve_screen_export_entries(
        dump_path=dump_path,
        file_key=file_key,
        primary_node_id=primary_node_id,
        assets=assets,
        dump_prefetch=dump_prefetch,
    )
    expected = frozenset(entry.node_id for entry in entries)
    covered = frozenset(
        entry.node_id
        for entry in entries
        if lookup_asset_path_for_node(asset_index, entry.node_id) is not None
    )
    if gap_partition is None:
        figma_root: dict = {}
        if dump_prefetch is not None and dump_prefetch.matches_dump(dump_path):
            figma_root = dump_prefetch.fetch_result.root
        else:
            from figma_flutter_agent.pipeline.dump import load_fetch_result_from_dump

            fetch = load_fetch_result_from_dump(
                dump_path,
                file_key=file_key,
                node_id=primary_node_id,
            )
            figma_root = fetch.root
        gap_partition = partition_missing_asset_entries(entries, covered, figma_root)
    lines: list[str] = []
    header = f"Required exports ({len(expected)} icon/boundary asset(s))"
    if screen:
        header = f"{header} — screen [bold]{screen}[/bold]"
    lines.append(header)
    if not entries:
        lines.append("[dim]no exportable icons in dump[/dim]")
        return len(invalid_files) == 0, lines

    for entry in sorted(entries, key=lambda item: item.node_id):
        rel = lookup_asset_path_for_node(asset_index, entry.node_id)
        kind_label = _export_kind_label(entry.kind)
        if rel is not None:
            lines.append(f"  [green]OK[/green] {entry.node_id} [{kind_label}]  {rel}")
        elif entry.node_id in gap_partition.api_unexportable_ids:
            png_name = asset_filename(entry.layer_name, entry.node_id, "png")
            lines.append(
                f"  [yellow]RASTER[/yellow] {entry.node_id} [{kind_label}]  "
                f"→ assets/images/{png_name} [dim](SVG API skip — PNG fallback)[/dim]"
            )
        elif entry.kind == "boundary_svg":
            lines.append(
                f"  [yellow]BOUNDARY[/yellow] {entry.node_id} [{kind_label}]  "
                f"→ {entry.expected_rel_path}"
            )
        else:
            lines.append(
                f"  [red]MISSING[/red] {entry.node_id} [{kind_label}]  → {entry.expected_rel_path}"
            )

    summary_parts = [f"[bold]{len(covered)}/{len(expected)}[/bold] on disk"]
    if gap_partition.downloadable_missing_ids:
        summary_parts.append(
            f"[red]{len(gap_partition.downloadable_missing_ids)} downloadable missing[/red]"
        )
    if gap_partition.api_unexportable_ids:
        summary_parts.append(
            f"[yellow]{len(gap_partition.api_unexportable_ids)} raster fallback[/yellow]"
        )
    if gap_partition.boundary_missing_ids:
        summary_parts.append(f"[yellow]{len(gap_partition.boundary_missing_ids)} boundary[/yellow]")
    if gap_partition.total_missing == 0:
        summary_parts.append("[green](complete)[/green]")
    lines.append(", ".join(summary_parts))
    hint = _missing_export_hint(gap_partition, has_figma_token=has_figma_token)
    if hint is not None:
        lines.append(hint)
    passed = gap_partition.check_blocking_missing == 0 and not invalid_files
    return passed, lines
