"""Semantics corpus gate commands (EPIC 5.W1)."""

from __future__ import annotations

from pathlib import Path

import typer

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.parser.semantics.metrics import (
    DEFAULT_GATES,
    evaluate_w1_corpus,
    load_w1_manifest,
    write_gate_report,
)

from .helpers import _handle_cli_exception, console

semantics_app = typer.Typer(add_completion=False, no_args_is_help=True)


@semantics_app.command("corpus-gate")
def semantics_corpus_gate_command(
    manifest_path: Path | None = typer.Option(
        None,
        "--manifest",
        help="Path to semantics manifest.yaml (defaults to tests fixture manifest).",
    ),
    write_report: Path | None = typer.Option(
        None,
        "--write-report",
        help="Write JSON gate report to this path.",
    ),
    overall_precision_min: float = typer.Option(
        DEFAULT_GATES["overall_precision_min"],
        "--overall-precision-min",
    ),
    per_kind_precision_min: float = typer.Option(
        DEFAULT_GATES["per_kind_precision_min"],
        "--per-kind-precision-min",
    ),
    recall_min: float = typer.Option(DEFAULT_GATES["recall_min"], "--recall-min"),
) -> None:
    """Evaluate W1 semantics corpus precision/recall gates."""
    try:
        manifest = load_w1_manifest(manifest_path) if manifest_path else load_w1_manifest()
        report = evaluate_w1_corpus(
            manifest,
            gates={
                "overall_precision_min": overall_precision_min,
                "per_kind_precision_min": per_kind_precision_min,
                "recall_min": recall_min,
                "blocker_negative_false_positives_max": 0,
            },
        )
    except (GenerationError, OSError, KeyError, ValueError) as exc:
        _handle_cli_exception(exc)
        raise typer.Exit(code=1) from exc

    if write_report is not None:
        write_gate_report(report, write_report)

    status = "[green]PASS[/green]" if report.passed else "[red]FAIL[/red]"
    console.print(
        f"{status} W1 corpus gate — precision={report.overall_precision:.3f} "
        f"recall={report.overall_recall:.3f} blocker_fp={report.blocker_negative_false_positives}",
    )
    if not report.passed:
        for case in report.failed_cases[:12]:
            console.print(f"  [red]case[/red] {case['path']}: {case['message']}")
        raise typer.Exit(code=1)
    raise typer.Exit(code=0)
