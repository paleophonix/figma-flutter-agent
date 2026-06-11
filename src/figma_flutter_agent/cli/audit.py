"""CLI commands for systemic pipeline audit artifacts."""

from __future__ import annotations

from pathlib import Path

import typer

from figma_flutter_agent.audit.baseline import capture_baseline_report, write_baseline_markdown
from figma_flutter_agent.audit.diff_triada import run_diff_triada
from figma_flutter_agent.audit.docs import write_all_audit_docs
from figma_flutter_agent.audit.fixtures import write_synthetic_layout_fixtures
from figma_flutter_agent.audit.predicate_matrix import (
    build_predicate_matrix,
    render_matrix_markdown,
)
from figma_flutter_agent.audit.systemic_rules import render_systemic_rules_markdown
from figma_flutter_agent.cli.helpers import console

audit_app = typer.Typer(help="Systemic pipeline audit tooling", no_args_is_help=True)


def _docs_audit_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "audit"


@audit_app.command("baseline")
def audit_baseline_command(
    run_pytest: bool = typer.Option(False, "--run-pytest", help="Run pytest before capture"),
) -> None:
    """Write docs/audit/baseline.md from current repo state."""
    report = capture_baseline_report(run_pytest=run_pytest)
    path = _docs_audit_dir() / "baseline.md"
    write_baseline_markdown(report, path)
    console.print(f"Wrote {path}")


@audit_app.command("diff-triada")
def audit_diff_triada_command() -> None:
    """Run diff-triada on audit corpus; write docs/audit/artifacts/diff_triada.json."""
    out = _docs_audit_dir() / "artifacts"
    records = run_diff_triada(output_dir=out)
    console.print(f"Diff-triada: {len(records)} layouts → {out / 'diff_triada.json'}")


@audit_app.command("predicate-matrix")
def audit_predicate_matrix_command() -> None:
    """Generate predicate overlap matrix markdown."""
    cells = build_predicate_matrix()
    markdown = render_matrix_markdown(cells)
    path = _docs_audit_dir() / "artifacts" / "predicate-overlap-matrix.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    console.print(f"Wrote {path}")


@audit_app.command("rules-coverage")
def audit_rules_coverage_command() -> None:
    """Write SYSTEMIC_BUG_RULES sanitizer coverage doc."""
    path = _docs_audit_dir() / "ir-llm-coverage.md"
    path.write_text(render_systemic_rules_markdown(), encoding="utf-8")
    console.print(f"Wrote {path}")


@audit_app.command("fixtures")
def audit_fixtures_command() -> None:
    """Write synthetic layout JSON fixtures into tests/fixtures/layouts/."""
    paths = write_synthetic_layout_fixtures()
    for path in paths:
        console.print(f"Wrote {path}")


@audit_app.command("docs")
def audit_docs_command() -> None:
    """Generate phase markdown docs under docs/audit/."""
    paths = write_all_audit_docs(_docs_audit_dir())
    for path in paths:
        console.print(f"Wrote {path}")


@audit_app.command("all")
def audit_all_command(
    run_pytest: bool = typer.Option(False, "--run-pytest"),
) -> None:
    """Regenerate all audit artifacts under docs/audit/."""
    audit_fixtures_command()
    audit_baseline_command(run_pytest=run_pytest)
    audit_predicate_matrix_command()
    audit_rules_coverage_command()
    audit_docs_command()
    console.print("Audit artifacts refreshed.")
