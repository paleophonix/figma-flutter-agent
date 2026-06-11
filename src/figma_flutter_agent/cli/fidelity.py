"""Fidelity manifest promotion and validation commands (EPIC 4.5)."""

from __future__ import annotations

from pathlib import Path

import typer

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.ir.fidelity.promote import (
    PromotionRequest,
    promote_manifest_entry,
    validate_manifest_entries,
)
from figma_flutter_agent.schemas import FidelityTier, WidgetIrKind

from .helpers import _handle_cli_exception, console

fidelity_app = typer.Typer(add_completion=False, no_args_is_help=True)


@fidelity_app.command("promote")
def fidelity_promote_command(
    kind: str = typer.Option(..., "--kind", help="Semantic WidgetIrKind value"),
    tier: str = typer.Option(..., "--tier", help="FidelityTier value"),
    fixture_id: str = typer.Option(..., "--fixture-id", help="Corpus fixture/golden id"),
    feature_profile: str = typer.Option("material", "--feature-profile"),
    template_version: str = typer.Option("1", "--template-version"),
    epsilon: float | None = typer.Option(0.02, "--epsilon"),
    manifest_path: Path | None = typer.Option(None, "--manifest-path"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate only; do not write YAML"),
) -> None:
    """Promote a manifest entry from offline golden/signoff evidence."""
    try:
        result = promote_manifest_entry(
            PromotionRequest(
                kind=WidgetIrKind(kind),
                tier=FidelityTier(tier),
                fixture_id=fixture_id,
                feature_profile=feature_profile,
                template_version=template_version,
                epsilon=epsilon,
                manifest_path=manifest_path,
            ),
            dry_run=dry_run,
        )
    except (GenerationError, ValueError) as exc:
        _handle_cli_exception(exc)
        raise typer.Exit(code=1) from exc

    action = "Would promote" if result.dry_run else "Promoted"
    console.print(
        f"[green]{action}[/green] {result.entry.kind.value} -> {result.entry.default_tier.value} "
        f"({result.manifest_path})",
    )
    raise typer.Exit(code=0)


@fidelity_app.command("validate")
def fidelity_validate_command(
    manifest_path: Path | None = typer.Option(None, "--manifest-path"),
) -> None:
    """Validate package fidelity manifest schema and fixture evidence."""
    errors = validate_manifest_entries(manifest_path)
    if errors:
        for item in errors:
            console.print(f"[red]FAIL[/red] {item}")
        raise typer.Exit(code=1)
    console.print("[green]Fidelity manifest validate OK[/green]")
    raise typer.Exit(code=0)
