"""Per-screen download status for batch file dumps."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from figma_flutter_agent.assets.collect import collect_exportable_nodes

JsonStatus = Literal["ok", "skipped", "missing"]
AssetStatus = Literal["complete", "partial", "failed", "none", "skipped"]


@dataclass(frozen=True)
class ScreenDownloadReport:
    """Download outcome for one screen frame."""

    feature: str
    node_id: str
    frame_name: str
    dump_path: Path
    json_status: JsonStatus
    asset_status: AssetStatus
    assets_expected: int
    assets_exported: int
    assets_failed: int


def exportable_node_ids_in_subtree(root: dict[str, Any]) -> set[str]:
    """Return exportable Figma node ids contained in ``root`` subtree."""
    return {node_id for node_id, _name, _kind in collect_exportable_nodes(root)}


def build_screen_download_reports(
    screens: list[tuple[str, str, str, Path, bool]],
    *,
    frames_by_id: dict[str, dict[str, Any]],
    exported_node_ids: set[str],
    assets_attempted: bool,
) -> tuple[list[ScreenDownloadReport], set[str]]:
    """Build per-screen JSON and asset status reports.

    Args:
        screens: Tuple of ``(feature, node_id, frame_name, dump_path, json_skipped)``.
        frames_by_id: Raw Figma frame nodes keyed by id.
        exported_node_ids: Node ids with at least one exported asset file.
        assets_attempted: Whether asset export was enabled for this run.

    Returns:
        Screen reports and exportable node ids not owned by any screen frame.
    """
    all_exportable: set[str] = set()
    per_screen_expected: dict[str, set[str]] = {}
    for _feature, node_id, _frame_name, _dump_path, _json_skipped in screens:
        frame = frames_by_id.get(node_id)
        if frame is None:
            per_screen_expected[node_id] = set()
            continue
        expected = exportable_node_ids_in_subtree(frame)
        per_screen_expected[node_id] = expected
        all_exportable |= expected

    assigned = set().union(*per_screen_expected.values()) if per_screen_expected else set()
    orphan_exportables = all_exportable - assigned

    reports: list[ScreenDownloadReport] = []
    for feature, node_id, frame_name, dump_path, json_skipped in screens:
        if json_skipped and dump_path.is_file():
            json_status: JsonStatus = "skipped"
        elif dump_path.is_file():
            json_status = "ok"
        else:
            json_status = "missing"

        expected = per_screen_expected.get(node_id, set())
        exported = expected & exported_node_ids
        failed_count = len(expected) - len(exported)

        if not assets_attempted:
            asset_status: AssetStatus = "skipped"
        elif not expected:
            asset_status = "none"
        elif len(exported) == len(expected):
            asset_status = "complete"
        elif exported:
            asset_status = "partial"
        else:
            asset_status = "failed"

        reports.append(
            ScreenDownloadReport(
                feature=feature,
                node_id=node_id,
                frame_name=frame_name,
                dump_path=dump_path,
                json_status=json_status,
                asset_status=asset_status,
                assets_expected=len(expected),
                assets_exported=len(exported),
                assets_failed=failed_count,
            )
        )

    return reports, orphan_exportables


def screen_download_all_ok(
    reports: list[ScreenDownloadReport],
    *,
    with_assets: bool,
) -> bool:
    """Return True when every screen JSON and asset export succeeded."""
    for report in reports:
        if report.json_status == "missing":
            return False
        if with_assets and report.asset_status in {"partial", "failed"}:
            return False
    return True


def print_screen_download_report(
    console: object,
    reports: list[ScreenDownloadReport],
    *,
    with_assets: bool,
    orphan_exportables: int,
    rate_limited: bool,
) -> None:
    """Print a per-screen JSON and asset status table to the terminal."""
    print_fn = console.print

    print_fn("\n[bold]Screen download report[/bold]")
    if rate_limited:
        print_fn(
            "[yellow]Figma rate limit (429) was hit during asset export. "
            "Partial assets were saved; re-run later for missing files.[/yellow]"
        )

    json_labels = {
        "ok": "[green]JSON ok[/green]",
        "skipped": "[yellow]JSON skipped[/yellow]",
        "missing": "[red]JSON missing[/red]",
    }
    for report in reports:
        json_label = json_labels[report.json_status]
        if not with_assets:
            asset_label = "assets skipped"
            marker = "[green]OK[/green]" if report.json_status != "missing" else "[red]FAIL[/red]"
        elif report.asset_status == "complete":
            asset_label = f"[green]assets {report.assets_exported}/{report.assets_expected}[/green]"
            marker = "[green]OK[/green]"
        elif report.asset_status == "none":
            asset_label = "no exportable assets"
            marker = "[green]OK[/green]" if report.json_status != "missing" else "[red]FAIL[/red]"
        elif report.asset_status == "partial":
            asset_label = (
                f"[yellow]assets {report.assets_exported}/{report.assets_expected} "
                f"({report.assets_failed} failed)[/yellow]"
            )
            marker = "[yellow]PARTIAL[/yellow]"
        else:
            asset_label = (
                f"[red]assets 0/{report.assets_expected} ({report.assets_failed} failed)[/red]"
            )
            marker = "[red]FAIL[/red]"

        print_fn(
            f"  {marker} {report.feature} ({report.node_id}) — {report.frame_name!r}: "
            f"{json_label}; {asset_label}"
        )

    json_ok = sum(1 for report in reports if report.json_status in {"ok", "skipped"})
    assets_ok = sum(
        1
        for report in reports
        if not with_assets or report.asset_status in {"complete", "none", "skipped"}
    )
    print_fn(
        f"\nSummary: JSON {json_ok}/{len(reports)} ready; "
        f"assets complete {assets_ok}/{len(reports)} screen(s)"
    )
    if orphan_exportables:
        print_fn(
            f"[dim]{orphan_exportables} exportable node(s) sit outside page-level frames "
            "(not attributed to a screen).[/dim]"
        )
