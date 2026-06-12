"""Corpus oracle gate commands (EPIC 6 W0)."""

from __future__ import annotations

import os
from pathlib import Path

import typer

from figma_flutter_agent.config import load_settings
from figma_flutter_agent.validation.oracle import (
    compare_profile_soft_invariants,
    run_corpus_oracle,
    write_all_oracle_reports,
)

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
    compare_profiles: bool = typer.Option(
        False,
        "--compare-profiles",
        help="Fail when production profile increases soft invariant counts vs dev",
    ),
) -> None:
    """Run corpus oracle gates on tests/fixtures/screens.yaml."""
    settings = load_settings()
    report = run_corpus_oracle(
        screen_ids=screen or None,
        settings=settings,
        golden_runtime=None if golden_runtime == "auto" else golden_runtime,
    )
    profile_report = (
        compare_profile_soft_invariants(screen_ids=screen or None, settings=settings)
        if compare_profiles
        else None
    )

    if write_report_dir is not None:
        write_all_oracle_reports(
            report,
            write_report_dir,
            profile_comparison=profile_report,
        )

    blocking_items = report.blocking_results()
    for oracle_item in report.results:
        if oracle_item.skipped:
            console.print(
                f"[yellow]SKIP[/yellow] {oracle_item.screen_id}: {oracle_item.skip_reason}"
            )
            continue
        status = "[green]OK[/green]" if oracle_item.blocking_pass else "[red]FAIL[/red]"
        tier = oracle_item.corpus_tier
        metrics = oracle_item.metrics
        console.print(
            f"{status} {oracle_item.screen_id} ({tier}) "
            f"non_text={metrics.non_text_pixel_diff} "
            f"text_region={metrics.text_region_pixel_diff} "
            f"geom={metrics.geometry_iou}",
        )
        for failure in oracle_item.failures:
            console.print(f"  [red]{failure}[/red]")
    if profile_report is not None:
        for profile_item in profile_report.results:
            if profile_item.passed:
                console.print(f"[green]OK[/green] {profile_item.screen_id} (profile diff)")
                continue
            console.print(f"[red]FAIL[/red] {profile_item.screen_id} (profile diff)")
            for code, values in profile_item.regressions.items():
                console.print(
                    f"  [red]{code}: dev={values['dev']} production={values['production']}[/red]"
                )
            for failure in profile_item.hard_failures:
                console.print(f"  [red]{failure}[/red]")

    if blocking:
        if not report.blocking_passed:
            if blocking_items and all(item.skipped for item in blocking_items):
                allow_skip = os.environ.get(
                    "FIGMA_CORPUS_ORACLE_ALLOW_SKIP", ""
                ).strip().lower() in (
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
        if profile_report is not None and not profile_report.passed:
            console.print("[red]Corpus oracle profile comparison FAIL[/red]")
            raise typer.Exit(code=1)
        raise typer.Exit(code=0)

    if profile_report is not None and not profile_report.passed:
        console.print("[red]Corpus oracle profile comparison FAIL[/red]")
        raise typer.Exit(code=1)
    if not report.full_corpus_passed:
        console.print("[yellow]Corpus oracle advisory report has failures[/yellow]")
    else:
        console.print("[green]Corpus oracle gate OK[/green]")
    raise typer.Exit(code=0)
