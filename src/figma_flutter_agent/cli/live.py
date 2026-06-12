"""Live check, demo sign-off, visual QA, doctor, and version commands."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer

from figma_flutter_agent.config import (
    Settings,
    apply_signoff_profile,
    apply_visual_qa_profile,
    load_settings,
)
from figma_flutter_agent.errors import FigmaFlutterError
from figma_flutter_agent.logging_setup import configure_logging
from figma_flutter_agent.validation.spec23.evaluate import (
    evaluate_spec23 as run_spec23_evaluation,
)

from .helpers import _handle_cli_exception, console

visual_qa_app = typer.Typer(help="Visual QA: pixel diff and typography specimens.")

_DEMO_SIGNOFF_FIXTURES: tuple[str, ...] = (
    "figma_node_sample.json",
    "figma_carousel_sample.json",
    "figma_tabs_sample.json",
    "figma_bottom_nav_sample.json",
    "figma_grid_sample.json",
)


def doctor_command(
    config: Path | None = typer.Option(
        None, "--config", help="Path to agent .ai-figma-flutter.yml"
    ),
    project_dir: Path = typer.Option(
        Path("."), "--project-dir", help="Flutter project root for project-specific checks"
    ),
    build_ast: bool = typer.Option(
        False,
        "--build-ast",
        help="Compile tools/bin/ast_compiler* when the prebuilt for this OS is missing",
    ),
    build_golden: bool = typer.Option(
        False,
        "--build-golden",
        help="Build docker image figma-flutter-golden-capture:local when Docker is available",
    ),
) -> None:
    """Check Poetry, Flutter, AST sidecar, and Docker golden runtime."""
    from figma_flutter_agent.dev.ast_sidecar_build import ensure_ast_sidecar_binary
    from figma_flutter_agent.dev.doctor import run_doctor
    from figma_flutter_agent.dev.golden_capture_build import ensure_golden_capture_image

    settings = load_settings(config) if config is not None else Settings()

    def _doctor_build_print(message: str) -> None:
        if message.startswith("Built "):
            console.print(f"[green]{message}[/green]")
        elif "failed" in message.lower() or message.startswith("Cannot"):
            console.print(f"[red]{message}[/red]")
        else:
            console.print(f"[yellow]{message}[/yellow]")

    if build_ast:
        ensure_ast_sidecar_binary(
            settings,
            build_if_missing=True,
            print_hint=False,
            console_print=_doctor_build_print,
        )
    if build_golden:
        ensure_golden_capture_image(
            settings,
            build_if_missing=True,
            print_hint=False,
            console_print=_doctor_build_print,
        )
    for row in run_doctor(settings=settings, project_dir=project_dir):
        mark = "[green]OK[/green]" if row.ok else "[yellow]WARN[/yellow]"
        console.print(f"{mark} {row.name}: {row.detail}")


def version() -> None:
    """Print package version."""
    from figma_flutter_agent import __version__

    console.print(__version__)


def live_check_command(
    figma_url: str | None = typer.Option(
        None,
        "--figma-url",
        help="Figma frame URL (overrides FIGMA_SMOKE_* for this run; prints .env hint)",
    ),
    project_dir: Path = typer.Option(
        Path("."),
        "--project-dir",
        help="Flutter project root for optional .debug dumps",
    ),
    dump: bool = typer.Option(
        False,
        "--dump",
        help="Write raw Figma node JSON to .debug/ (same as generate --verbose)",
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging"),
) -> None:
    """Verify Figma credentials and optionally smoke-test fetch on FIGMA_SMOKE_* frame."""
    from figma_flutter_agent.errors import FigmaUrlError
    from figma_flutter_agent.figma.url import resolve_smoke_frame

    configure_logging(verbose=verbose)
    settings = load_settings()
    token = settings.figma_token().strip()

    try:
        file_key, node_id = resolve_smoke_frame(
            figma_url=figma_url,
            file_key=settings.figma_smoke_file_key,
            node_id=settings.figma_smoke_node_id,
        )
    except FigmaUrlError as exc:
        console.print(f"[red]Invalid --figma-url:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if not token:
        console.print("[red]FIGMA_ACCESS_TOKEN is not set[/red]")
        raise typer.Exit(code=1)
    console.print("[green]FIGMA_ACCESS_TOKEN[/green] present")

    if not file_key or not node_id:
        console.print(
            "[yellow]No smoke frame configured — skipping live frame fetch.[/yellow]\n"
            "  Set FIGMA_SMOKE_FILE_KEY and FIGMA_SMOKE_NODE_ID in .env, or pass:\n"
            "  figma-flutter live-check --figma-url "
            '"https://www.figma.com/design/FILE_KEY/Name?node-id=1-2"'
        )
        raise typer.Exit(code=0)

    if figma_url and figma_url.strip():
        console.print(f"[dim]Using frame from URL: file_key={file_key} node_id={node_id}[/dim]")
        console.print(
            "[dim]Persist for pytest -m live_figma:[/dim]\n"
            f"  FIGMA_SMOKE_FILE_KEY={file_key}\n"
            f"  FIGMA_SMOKE_NODE_ID={node_id}"
        )

    from figma_flutter_agent.figma.client import FigmaConnector
    from figma_flutter_agent.stages.fetch import fetch_figma_frame

    async def _run_fetch() -> None:
        async with FigmaConnector(token, settings.figma_api_base_url) as connector:
            result = await fetch_figma_frame(
                connector,
                file_key=file_key,
                node_id=node_id,
                project_dir=project_dir.resolve(),
                verbose=dump,
            )
        console.print(
            f"[green]Live fetch OK[/green] frame={result.root.get('name')!r} "
            f"links={len(result.prototype_links)} components={len(result.components)}"
        )
        if dump:
            from figma_flutter_agent.debug.dumps import write_raw_dump
            from figma_flutter_agent.generator.layout.common import to_snake_case
            from figma_flutter_agent.pipeline.helpers import resolve_feature_name

            feature = resolve_feature_name(str(result.root.get("name") or ""), to_snake_case(node_id))
            debug_path = write_raw_dump(project_dir.resolve(), feature, result.root)
            console.print(f"  dump: {debug_path}")

    try:
        asyncio.run(_run_fetch())
    except BaseException as exc:
        if isinstance(exc, FigmaFlutterError):
            console.print(f"[red]Live fetch failed:[/red] {exc}")
        _handle_cli_exception(exc, command="live-check", verbose=verbose)

    raise typer.Exit(code=0)


def demo_signoff_command(
    fixtures_dir: Path = typer.Option(
        Path("tests/fixtures"),
        "--fixtures-dir",
        help="Directory containing Figma frame JSON fixtures",
    ),
    strict: bool = typer.Option(True, "--strict/--no-strict", help="Apply substantive §23 gates"),
    signoff_gates: bool = typer.Option(
        False,
        "--signoff-gates",
        help="Enable CI quality/validation gates (spec §9/§23 analyze, preservation)",
    ),
    visual_qa: bool = typer.Option(
        False,
        "--visual-qa",
        help="Enable visual QA settings (reference PNG, golden tests, dark theme)",
    ),
    config: Path | None = typer.Option(
        None,
        "--config",
        help="Path to agent .ai-figma-flutter.yml (default: repo root)",
    ),
) -> None:
    """Run automated fixture-based demo sign-off (offline substitute for manual QA)."""
    import json

    settings = load_settings(config)
    if visual_qa:
        settings = apply_visual_qa_profile(settings)
    if signoff_gates:
        settings = apply_signoff_profile(settings)
    failures: list[str] = []

    for fixture_name in _DEMO_SIGNOFF_FIXTURES:
        fixture_path = fixtures_dir / fixture_name
        if not fixture_path.is_file():
            failures.append(f"{fixture_name}: missing")
            console.print(f"[red]FAIL[/red] {fixture_name} (file not found)")
            continue
        root = json.loads(fixture_path.read_text(encoding="utf-8"))
        try:
            report = run_spec23_evaluation(
                root,
                settings,
                node_id=str(root.get("id")),
                strict=strict,
            )
        except FigmaFlutterError as exc:
            failures.append(f"{fixture_name}: {exc}")
            console.print(f"[red]FAIL[/red] {fixture_name} ({exc})")
            continue
        if report.passed:
            console.print(f"[green]PASS[/green] {fixture_name}")
        else:
            failed_names = ", ".join(item.name for item in report.criteria if not item.passed)
            failures.append(f"{fixture_name}: {failed_names}")
            console.print(f"[red]FAIL[/red] {fixture_name} ({failed_names})")

    if failures:
        console.print("[red]Demo sign-off FAILED[/red]")
        raise typer.Exit(code=1)

    console.print(
        "[green]Demo sign-off OK[/green] "
        f"({len(_DEMO_SIGNOFF_FIXTURES)} fixtures, strict={strict}). "
        "Run `poetry run pytest tests/test_demo_signoff.py` for dart analyze + custom-code checks."
    )
    raise typer.Exit(code=0)


@visual_qa_app.command("compare")
def visual_qa_compare_command(
    project_dir: Path = typer.Option(..., "--project-dir", help="Flutter project root"),
    feature: str = typer.Option("sign_in", "--feature", help="Generated feature slug"),
    threshold: float | None = typer.Option(
        None,
        "--threshold",
        help="Changed-pixel ratio threshold (default from config or 0.05)",
    ),
    skip_specimens: bool = typer.Option(
        False,
        "--skip-specimens",
        help="Compare only the full-screen Figma reference vs golden",
    ),
    config: Path | None = typer.Option(
        None, "--config", help="Path to agent .ai-figma-flutter.yml (default: repo root)"
    ),
    fail_on_missing: bool = typer.Option(
        False,
        "--fail-on-missing",
        help="Exit 1 when reference or golden PNGs are missing",
    ),
) -> None:
    """Compare Figma reference PNGs against Flutter golden files (pixel differential)."""
    from figma_flutter_agent.validation.compare import run_visual_qa

    settings = load_settings(config)
    effective_threshold = (
        threshold if threshold is not None else settings.agent.validation.pixel_diff_threshold
    )
    report = run_visual_qa(
        project_dir.resolve(),
        feature,
        threshold=effective_threshold,
        include_specimens=not skip_specimens,
    )

    if not report.comparisons:
        console.print("[yellow]No comparisons run[/yellow] (missing reference or golden PNGs).")
        if fail_on_missing:
            raise typer.Exit(code=1)
        raise typer.Exit(code=0)

    for item in report.comparisons:
        if item.skipped:
            console.print(f"[dim]SKIP[/dim] {item.name}: {item.skip_reason}")
            continue
        status = "[green]PASS[/green]" if item.result.passed else "[red]FAIL[/red]"
        console.print(
            f"{status} {item.name}: {item.result.changed_ratio:.2%} changed "
            f"(threshold {item.result.threshold:.2%})"
        )

    if report.passed:
        console.print("[green]Visual QA compare OK[/green]")
        raise typer.Exit(code=0)

    console.print(f"[red]Visual QA compare FAILED[/red] ({len(report.failures)} comparisons)")
    raise typer.Exit(code=1)
