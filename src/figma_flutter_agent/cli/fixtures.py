"""Fixture, dev, and debug commands."""

from __future__ import annotations

from pathlib import Path

import typer

from figma_flutter_agent.config import apply_refine_ready_profile, load_settings
from figma_flutter_agent.errors import FigmaFlutterError
from figma_flutter_agent.validation.spec23.evaluate import (
    evaluate_spec23 as run_spec23_evaluation,
)
from figma_flutter_agent.validation.spec23.models import Spec23Report

from .helpers import _handle_cli_exception, console


def fixture_ir_validate_command(
    screen: list[str] = typer.Option(
        None,
        "--screen",
        help="Manifest screen id (repeatable; default all)",
    ),
    no_guards: bool = typer.Option(
        False,
        "--no-guards",
        help="Validate structure only (skip apply_ir_guards mutations)",
    ),
) -> None:
    """Run IR guardrails on tests/fixtures/screens.yaml layout JSON."""
    from figma_flutter_agent.fixtures.bulk_ir_validate import validate_all_fixture_screens

    results = validate_all_fixture_screens(
        screen_ids=screen or None,
        apply_guards=not no_guards,
        validate=True,
    )
    failures = [item for item in results if not item.ok]
    for item in results:
        if item.ok:
            console.print(f"[green]OK[/green]  {item.screen_id}")
        else:
            console.print(f"[red]FAIL[/red] {item.screen_id}: {item.error}")
    if failures:
        raise typer.Exit(code=1)
    console.print(f"[green]Fixture IR validate OK[/green] ({len(results)} screen(s))")
    raise typer.Exit(code=0)


def fixture_golden_check_command(
    screen: list[str] = typer.Option(
        None,
        "--screen",
        help="Manifest screen id (repeatable; default all)",
    ),
    threshold: float = typer.Option(
        0.05,
        "--threshold",
        help="Maximum allowed pixel changed ratio vs baseline",
    ),
    golden_runtime: str = typer.Option(
        "auto",
        "--golden-runtime",
        help="Golden capture runtime: auto, docker, or host",
    ),
) -> None:
    """Compare fresh captures to committed tests/fixtures/golden/png/docker baselines."""
    from figma_flutter_agent.fixtures.golden_compare import compare_all_fixture_goldens

    settings = load_settings()
    results = compare_all_fixture_goldens(
        screen_ids=screen or None,
        settings=settings,
        pixel_threshold=threshold,
        golden_runtime=None if golden_runtime == "auto" else golden_runtime,
    )
    hard_failures = [item for item in results if not item.ok and not item.skipped]
    skipped = [item for item in results if item.skipped]
    for item in results:
        if item.skipped:
            console.print(f"[yellow]SKIP[/yellow] {item.screen_id}: {item.reason}")
        elif item.ok:
            ratio = f" ({item.changed_ratio:.2%} changed)" if item.changed_ratio is not None else ""
            console.print(f"[green]OK[/green]  {item.screen_id}{ratio}")
        else:
            console.print(f"[red]FAIL[/red] {item.screen_id}: {item.reason}")
    if hard_failures:
        raise typer.Exit(code=1)
    if skipped and not any(item.ok for item in results):
        console.print("[yellow]All screens skipped (Flutter SDK or baselines missing)[/yellow]")
        raise typer.Exit(code=1)
    console.print(
        f"[green]Fixture golden check OK[/green] "
        f"({sum(1 for item in results if item.ok)} passed, {len(skipped)} skipped)"
    )
    raise typer.Exit(code=0)


def fixture_geometry_check_command(
    screen: list[str] = typer.Option(
        None,
        "--screen",
        help="Manifest screen id (repeatable; default all)",
    ),
    min_iou: float | None = typer.Option(
        None,
        "--min-iou",
        help="Minimum IoU per widget (default: agent.generation.runtime_geometry_min_iou)",
    ),
    golden_runtime: str = typer.Option(
        "auto",
        "--golden-runtime",
        help="Golden capture runtime: auto, docker, or host",
    ),
) -> None:
    """Capture fixture screens and verify runtime figma_keys bounds vs layout placements."""
    from figma_flutter_agent.fixtures.geometry_check import check_all_fixture_geometry

    settings = load_settings()
    results = check_all_fixture_geometry(
        screen_ids=screen or None,
        settings=settings,
        min_iou=min_iou,
        golden_runtime=None if golden_runtime == "auto" else golden_runtime,
    )
    hard_failures = [item for item in results if not item.ok and not item.skipped]
    for item in results:
        if item.skipped:
            console.print(f"[yellow]SKIP[/yellow] {item.screen_id}: {item.reason}")
        elif item.ok:
            console.print(f"[green]OK[/green]  {item.screen_id} (geometry)")
        else:
            console.print(f"[red]FAIL[/red] {item.screen_id}: {item.reason}")
            if item.feedback:
                console.print(item.feedback)
    if hard_failures:
        raise typer.Exit(code=1)
    if not any(item.ok for item in results):
        console.print("[yellow]All screens skipped (Flutter SDK unavailable?)[/yellow]")
        raise typer.Exit(code=1)
    console.print(
        f"[green]Fixture geometry OK[/green] "
        f"({sum(1 for item in results if item.ok)} passed)"
    )
    raise typer.Exit(code=0)


def profile_refine_ready_command(
    config: Path | None = typer.Option(
        None,
        "--config",
        help="Path to agent .ai-figma-flutter.yml (default: repo root)",
    ),
) -> None:
    """Print generation flags to enable after baseline geometry gate is green."""
    settings = load_settings(config)
    updated = apply_refine_ready_profile(settings)
    generation = updated.agent.generation
    console.print("[bold]agent.generation[/bold] (refine-ready profile):")
    console.print(f"  llm_visual_refine: {generation.llm_visual_refine}")
    console.print(f"  llm_visual_refine_capture_golden: {generation.llm_visual_refine_capture_golden}")
    console.print(f"  llm_visual_refine_threshold: {generation.llm_visual_refine_threshold}")
    console.print(f"  runtime_geometry_gate: {generation.runtime_geometry_gate}")
    console.print(
        f"  runtime_geometry_use_tier_thresholds: {generation.runtime_geometry_use_tier_thresholds}"
    )
    console.print(
        "\n[yellow]Prerequisite:[/yellow] fixture-geometry-check green on demo screens, "
        "then merge into .ai-figma-flutter.yml"
    )
    raise typer.Exit(code=0)


def validate_spec23_command(
    fixture: Path = typer.Option(
        Path("tests/fixtures/figma_node_sample.json"),
        "--fixture",
        help="Path to a Figma frame JSON fixture",
    ),
    llm_fixture: Path | None = typer.Option(
        None,
        "--llm-fixture",
        help="Optional LLM response JSON; evaluates the LLM codegen path",
    ),
    strict: bool = typer.Option(True, "--strict/--no-strict", help="Apply substantive §23 gates"),
    config: Path | None = typer.Option(
        None, "--config", help="Path to agent .ai-figma-flutter.yml (default: repo root)"
    ),
) -> None:
    """Run spec section-23 acceptance checks against local fixtures."""
    import json

    from figma_flutter_agent.validation.spec23.evaluate import evaluate_spec23_llm_path

    settings = load_settings(config)
    root = json.loads(fixture.read_text(encoding="utf-8"))
    try:
        if llm_fixture is not None:
            from figma_flutter_agent.schemas import FlutterGenerationResponse

            generation = FlutterGenerationResponse.model_validate(
                json.loads(llm_fixture.read_text(encoding="utf-8"))
            )
            report: Spec23Report = evaluate_spec23_llm_path(
                root,
                settings,
                generation,
                node_id=str(root.get("id")),
                strict=strict,
            )
        else:
            report = run_spec23_evaluation(
                root, settings, node_id=str(root.get("id")), strict=strict
            )
    except BaseException as exc:
        if isinstance(exc, FigmaFlutterError):
            console.print(f"[red]Validation failed:[/red] {exc}")
        _handle_cli_exception(exc, command="validate-spec23", verbose=False)

    for item in report.criteria:
        status = "[green]PASS[/green]" if item.passed else "[red]FAIL[/red]"
        detail = f" ({item.detail})" if item.detail else ""
        console.print(f"{status} {item.name}{detail}")

    if report.passed:
        console.print(f"[green]Spec §23 OK[/green] mode={report.generation_mode}")
        raise typer.Exit(code=0)

    console.print("[red]Spec §23 FAILED[/red]")
    raise typer.Exit(code=1)
