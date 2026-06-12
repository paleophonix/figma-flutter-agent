"""Corpus oracle gate commands (EPIC 6 W0)."""

from __future__ import annotations

import os
from pathlib import Path

import typer

from figma_flutter_agent.config import load_settings
from figma_flutter_agent.validation.oracle import run_corpus_oracle, write_all_oracle_reports

from .helpers import console

corpus_oracle_app = typer.Typer(add_completion=False, no_args_is_help=True)


@corpus_oracle_app.command("gate")
def corpus_oracle_gate_command(
    blocking: bool = typer.Option(
        False,
        "--blocking",
        help="Exit non-zero when strict_pixel_blocking subset fails",
    ),
    screen: list[str] = typer.Option(
        None,
        "--screen",
        help="Manifest screen id (repeatable; default all)",
    ),
    write_report_dir: Path | None = typer.Option(
        None,
        "--write-report-dir",
        help="Directory for blocking_gate.json, advisory_pixel_report.json, candidates",
    ),
    golden_runtime: str = typer.Option(
        "auto",
        "--golden-runtime",
        help="Golden capture runtime: auto, docker, or host",
    ),
) -> None:
    """Run corpus oracle gates on tests/fixtures/screens.yaml."""
    settings = load_settings()
    report = run_corpus_oracle(
        screen_ids=screen or None,
        settings=settings,
        golden_runtime=None if golden_runtime == "auto" else golden_runtime,
    )

    if write_report_dir is not None:
        write_all_oracle_reports(report, write_report_dir)

    blocking_items = report.blocking_results()
    for item in report.results:
        if item.skipped:
            console.print(f"[yellow]SKIP[/yellow] {item.screen_id}: {item.skip_reason}")
            continue
        status = "[green]OK[/green]" if item.blocking_pass else "[red]FAIL[/red]"
        tier = item.corpus_tier
        metrics = item.metrics
        console.print(
            f"{status} {item.screen_id} ({tier}) "
            f"non_text={metrics.non_text_pixel_diff} "
            f"text_region={metrics.text_region_pixel_diff} "
            f"geom={metrics.geometry_iou}",
        )
        for failure in item.failures:
            console.print(f"  [red]{failure}[/red]")

    if blocking:
        if not report.blocking_passed:
            if blocking_items and all(item.skipped for item in blocking_items):
                allow_skip = os.environ.get("FIGMA_CORPUS_ORACLE_ALLOW_SKIP", "").strip().lower() in (
                    "1",
                    "true",
                    "yes",
                )
                if allow_skip:
                    console.print(
                        "[yellow]All blocking screens skipped (Flutter capture unavailable); "
                        "FIGMA_CORPUS_ORACLE_ALLOW_SKIP=1[/yellow]",
                    )
                    raise typer.Exit(code=0)
                console.print(
                    "[red]All strict_pixel_blocking screens skipped; "
                    "blocking gate FAIL (set FIGMA_CORPUS_ORACLE_ALLOW_SKIP=1 for local only)[/red]",
                )
                raise typer.Exit(code=1)
            console.print(
                f"[red]Corpus oracle blocking gate FAIL[/red] "
                f"({len(blocking_items)} strict_pixel_blocking screen(s))",
            )
            raise typer.Exit(code=1)
        console.print(
            f"[green]Corpus oracle blocking gate OK[/green] ({len(blocking_items)} screen(s))",
        )
        raise typer.Exit(code=0)

    if not report.full_corpus_passed:
        console.print("[yellow]Corpus oracle advisory report has failures[/yellow]")
    else:
        console.print("[green]Corpus oracle gate OK[/green]")
    raise typer.Exit(code=0)
