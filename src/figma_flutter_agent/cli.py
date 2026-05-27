"""Typer CLI entrypoint."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from loguru import logger
from pydantic import ValidationError
from rich.console import Console

from figma_flutter_agent.batch.dump_mode import (
    BatchDumpMode,
    DumpWritePolicy,
    assets_attempted,
    plan_for_mode,
)
from figma_flutter_agent.cli_interactive import (
    CliSession,
    is_interactive,
    prompt_figma_file_key,
    prompt_figma_frame_url,
    prompt_manifest_path,
    prompt_project_dir,
    prompt_screen_name,
    run_main_wizard,
    should_prompt,
    tty_interactive_default,
)
from figma_flutter_agent.config import (
    Settings,
    apply_production_profile,
    apply_signoff_profile,
    apply_visual_qa_profile,
    load_settings,
)
from figma_flutter_agent.errors import (
    FigmaFlutterError,
    FlutterProjectError,
    PipelineError,
    format_error_for_log,
)
from figma_flutter_agent.generation.mode import GenerationLayoutMode
from figma_flutter_agent.logging_setup import LOG_FILE, configure_logging
from figma_flutter_agent.pipeline import format_dry_run_output, run_pipeline
from figma_flutter_agent.validation.spec23 import (
    Spec23Report,
    evaluate_spec23_llm_path,
)
from figma_flutter_agent.validation.spec23 import (
    evaluate_spec23 as run_spec23_evaluation,
)

app = typer.Typer(add_completion=False, no_args_is_help=False, invoke_without_command=True)
console = Console()


@app.callback()
def main(
    ctx: typer.Context,
    interactive: bool = typer.Option(
        False,
        "-i",
        "--interactive",
        help="Prompt for missing options (also auto-enabled in a TTY)",
    ),
    no_interactive: bool = typer.Option(
        False,
        "--no-interactive",
        help="Never prompt (for CI/scripts); missing args show errors or help",
    ),
) -> None:
    """Figma to Flutter codegen CLI."""
    configure_logging(verbose=False)
    session = CliSession(
        interactive=interactive or (tty_interactive_default() and not no_interactive),
        force_non_interactive=no_interactive,
    )
    ctx.ensure_object(dict)
    ctx.obj["session"] = session
    if ctx.invoked_subcommand is None:
        if session.interactive:
            try:
                run_main_wizard(ctx)
            except FigmaFlutterError as exc:
                _exit_domain_error(exc)
            except FileNotFoundError as exc:
                console.print(f"[red]Error:[/red] {exc}")
                raise typer.Exit(code=1) from exc
            raise typer.Exit(code=0)
        console.print(ctx.get_help())
        raise typer.Exit(code=0)


def _resolve_flutter_project(
    ctx: typer.Context,
    project_dir: Path,
    *,
    strict: bool = True,
) -> Path:
    """Resolve ``project_dir`` to a Flutter root, prompting in interactive mode."""
    from figma_flutter_agent.dev.project import (
        env_configured_project_dir,
        is_implicit_project_dir,
        resolve_implicit_project_dir,
        resolve_project_dir,
    )

    env_dir = env_configured_project_dir()

    try:
        if is_implicit_project_dir(project_dir):
            return resolve_implicit_project_dir(env_project_dir=env_dir)
        return resolve_project_dir(project_dir)
    except FlutterProjectError:
        if is_interactive(ctx):
            return prompt_project_dir(ctx, project_dir, env_project_dir=env_dir)
        if strict:
            raise
        return project_dir.expanduser().resolve()


def _resolve_generate_target(
    ctx: typer.Context,
    *,
    project_dir: Path,
    figma_url: str | None,
    from_dump: Path | None,
    feature_name: str | None,
) -> tuple[Path, str, Path | None, str | None]:
    """Fill missing generate inputs via prompts when interactive."""
    root = _resolve_flutter_project(ctx, project_dir, strict=is_interactive(ctx))
    resolved_url = figma_url
    resolved_dump = from_dump.resolve() if from_dump is not None else None
    resolved_feature = feature_name

    if should_prompt(ctx, resolved_url) and resolved_dump is None:
        from figma_flutter_agent.batch.manifest import load_batch_manifest
        from figma_flutter_agent.batch.run import _figma_url_for_screen, _resolve_dump
        from figma_flutter_agent.dev.project import resolve_manifest_path

        manifest_path = root / "screens.yaml"
        if manifest_path.is_file() and is_interactive(ctx):
            from figma_flutter_agent.cli_interactive import prompt_confirm

            if prompt_confirm("Generate from screens.yaml dump (offline)?", default=True):
                manifest = load_batch_manifest(resolve_manifest_path(root))
                picked = prompt_screen_name(ctx, manifest)
                entry = next(item for item in manifest.screens if item.feature == picked)
                resolved_dump = _resolve_dump(entry, manifest.project_dir)
                resolved_url = _figma_url_for_screen(manifest, entry)
                resolved_feature = resolved_feature or picked
        if resolved_url is None:
            resolved_url = prompt_figma_frame_url(ctx=ctx, project_dir=root)
    elif resolved_url is not None and resolved_dump is None:
        from figma_flutter_agent.errors import FigmaUrlError
        from figma_flutter_agent.figma.url import FigmaUrlKind, build_figma_url, parse_figma_input

        try:
            parsed = parse_figma_input(resolved_url)
        except FigmaUrlError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(code=1) from exc
        if parsed.kind == FigmaUrlKind.FILE:
            console.print(
                "[red]Error:[/red] File URL or file key cannot be used with generate. "
                "Use wizard **fetch from Figma**, `batch dump-file`, or pass a frame URL with node-id."
            )
            raise typer.Exit(code=1)
        if parsed.node_id is not None:
            resolved_url = build_figma_url(parsed.file_key, parsed.node_id)
    if resolved_url is None:
        console.print("[red]--figma-url is required (or use --from-dump / interactive mode)[/red]")
        raise typer.Exit(code=1)
    return root, resolved_url, resolved_dump, resolved_feature


def _exit_domain_error(exc: FigmaFlutterError) -> None:
    """Print a domain error and exit with code 1."""
    console.print(f"[red]Error:[/red] {format_error_for_log(exc)}")
    raise typer.Exit(code=1) from exc


def _exit_unexpected(exc: BaseException, *, verbose: bool, command: str) -> None:
    """Log full traceback to file and exit with code 2."""
    logger.exception("Unexpected CLI failure during {}", command)
    console.print(f"[red]Unexpected failure:[/red] {exc}")
    console.print(f"[dim]Full traceback: {LOG_FILE}[/dim]")
    if verbose:
        console.print_exception(show_locals=False)
    raise typer.Exit(code=2) from exc


def _apply_generation_mode_for_command(
    ctx: typer.Context,
    settings: Settings,
    generation_mode: GenerationLayoutMode | None,
) -> Settings:
    """Apply explicit or interactive deterministic vs LLM generation mode."""
    from figma_flutter_agent.generation.mode import apply_generation_layout_mode

    if generation_mode is not None:
        return apply_generation_layout_mode(settings, generation_mode)
    if is_interactive(ctx):
        from figma_flutter_agent.cli_interactive import prompt_generation_layout_mode

        return apply_generation_layout_mode(settings, prompt_generation_layout_mode(settings))
    return settings


_CLI_BOUNDARY_ERRORS: tuple[type[BaseException], ...] = (
    OSError,
    RuntimeError,
    ValueError,
    TypeError,
    KeyError,
    json.JSONDecodeError,
    ValidationError,
)


def _handle_cli_exception(exc: BaseException, *, command: str, verbose: bool) -> None:
    """Map pipeline/CLI failures to domain (1) or unexpected (2) exits.

    Args:
        exc: Raised exception from a command handler.
        command: CLI command name for logging.
        verbose: When True, print traceback to the console.

    Raises:
        typer.Exit: Always (codes 1 or 2), or re-raises interrupt exits.
    """
    if isinstance(exc, (KeyboardInterrupt, SystemExit)):
        raise exc
    if isinstance(exc, asyncio.CancelledError):
        raise exc
    if isinstance(exc, PipelineError):
        _exit_unexpected(exc, verbose=verbose, command=command)
    if isinstance(exc, FigmaFlutterError):
        _exit_domain_error(exc)
    if isinstance(exc, _CLI_BOUNDARY_ERRORS):
        _exit_unexpected(exc, verbose=verbose, command=command)
    _exit_unexpected(exc, verbose=verbose, command=command)


@app.command("version")
def version() -> None:
    """Print package version."""
    from figma_flutter_agent import __version__

    console.print(__version__)


@app.command("run")
def run_screen_command(
    ctx: typer.Context,
    screen: str | None = typer.Argument(
        None,
        help="Screen feature name from screens.yaml (e.g. sign_in, home)",
    ),
    project_dir: Path = typer.Option(
        Path("."),
        "--project-dir",
        help="Flutter project root (must contain screens.yaml)",
    ),
    skip_generate: bool = typer.Option(
        False,
        "--skip-generate",
        help="Skip codegen and launch the app as-is (main.dart unchanged)",
    ),
    list_screens: bool = typer.Option(
        False,
        "--list",
        help="List available screen names and exit",
    ),
    allow_dev_profile: bool = typer.Option(
        True,
        "--allow-dev-profile/--strict",
        help="Use dev codegen gates (default). --strict applies production profile.",
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging"),
) -> None:
    """Generate one screen from cached dump and launch ``flutter run``."""
    from figma_flutter_agent.batch.manifest import format_screen_list, load_batch_manifest
    from figma_flutter_agent.dev.project import (
        ensure_project_config,
        resolve_manifest_path,
    )
    from figma_flutter_agent.dev.run import run_screen_blocking

    configure_logging(verbose=verbose)

    try:
        root = _resolve_flutter_project(ctx, project_dir)
    except FlutterProjectError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if list_screens:
        try:
            from figma_flutter_agent.dev.run import detect_wired_screen_feature

            manifest = load_batch_manifest(resolve_manifest_path(root))
        except FlutterProjectError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(code=1) from exc
        active = detect_wired_screen_feature(root)
        console.print("[bold]Available screens[/bold]:")
        console.print(format_screen_list(manifest, active=active))
        raise typer.Exit(code=0)

    if screen is None:
        if is_interactive(ctx):
            try:
                manifest = load_batch_manifest(resolve_manifest_path(root))
            except FlutterProjectError as exc:
                console.print(f"[red]Error:[/red] {exc}")
                raise typer.Exit(code=1) from exc
            screen = prompt_screen_name(ctx, manifest)
        else:
            console.print("[red]Screen name required.[/red] Example: figma-flutter run sign_in")
            raise typer.Exit(code=1)

    try:
        ensure_project_config(root)
        plan, launched = run_screen_blocking(
            project_dir=root,
            screen_name=screen,
            skip_generate=skip_generate,
            allow_dev_profile=allow_dev_profile,
            verbose=verbose,
        )
    except FileNotFoundError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    except ValueError as exc:
        console.print(f"[red]Unknown screen:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    except BaseException as exc:
        _handle_cli_exception(exc, command="run", verbose=verbose)

    if launched is False:
        console.print(f"[yellow]Flutter run stopped[/yellow] — {plan.screen.feature}")
    else:
        console.print(f"[green]Launched[/green] {plan.screen.feature}")


@app.command("generate")
def generate(
    ctx: typer.Context,
    figma_url: str | None = typer.Option(
        None,
        "--figma-url",
        help="Figma frame URL with node-id",
    ),
    project_dir: Path = typer.Option(
        Path("."), "--project-dir", help="Target Flutter project root"
    ),
    feature_name: str | None = typer.Option(
        None, "--feature-name", help="Override feature folder name"
    ),
    config: Path | None = typer.Option(
        None, "--config", help="Path to agent .ai-figma-flutter.yml (default: repo root)"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Parse and plan without writing files"),
    dump_design: bool = typer.Option(
        False,
        "--dump-design",
        help="Include full cleanTree/tokens in dry-run output (may contain proprietary design data)",
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging"),
    no_sync: bool = typer.Option(
        False, "--no-sync", help="Disable incremental sync and force full rewrite"
    ),
    regenerate_templates: bool = typer.Option(
        False,
        "--regenerate-templates",
        help="Force rewrite of all planned files during incremental sync",
    ),
    force_llm_regen: bool = typer.Option(
        False,
        "--force-llm-regen",
        help="Force LLM regeneration even if the design tree hash has not changed",
    ),
    allow_stubs: bool = typer.Option(
        False,
        "--allow-stubs",
        help="Allow placeholder destination screens when LLM generation fails",
    ),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Apply production profile (default for non-dry-run; redundant if already default)",
    ),
    allow_dev_profile: bool = typer.Option(
        False,
        "--allow-dev-profile",
        help="Skip production gates (dart analyze, spec9, strict preservation, fail-fast LLM)",
    ),
    from_dump: Path | None = typer.Option(
        None,
        "--from-dump",
        help="Load cached .figma_debug/raw/<feature>_layout.json instead of live Figma API",
    ),
    generation_mode: GenerationLayoutMode | None = typer.Option(
        None,
        "--generation-mode",
        help="Screen codegen: deterministic or llm (interactive prompt when omitted)",
        case_sensitive=False,
    ),
) -> None:
    """Generate Flutter screen, theme, and assets from a Figma frame."""
    configure_logging(verbose=verbose)

    try:
        root, figma_url, from_dump, feature_name = _resolve_generate_target(
            ctx,
            project_dir=project_dir,
            figma_url=figma_url,
            from_dump=from_dump,
            feature_name=feature_name,
        )
    except FlutterProjectError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if config is None:
        from figma_flutter_agent.dev.project import ensure_project_config

        config = ensure_project_config(root)

    settings = load_settings(config)
    use_production_profile = (strict or not dry_run) and not allow_dev_profile
    if use_production_profile:
        settings = apply_production_profile(settings)
    elif not dry_run and allow_dev_profile:
        console.print(
            "[yellow]Dev profile:[/yellow] production gates disabled "
            "(--allow-dev-profile). Not suitable for release sign-off."
        )
        from figma_flutter_agent.llm.capabilities import provider_capabilities

        caps = provider_capabilities(settings.resolved_llm_provider())
        if not settings.llm_require_strict_json_schema and not caps.supports_strict_json_schema:
            console.print(
                f"[yellow]LLM provider {settings.llm_provider!r} does not guarantee strict JSON schema; "
                "output may rely on prompt-only JSON parsing. Use anthropic/openai for production."
            )
    if allow_stubs:
        settings = settings.model_copy(
            update={
                "agent": settings.agent.model_copy(
                    update={
                        "generation": settings.agent.generation.model_copy(
                            update={"allow_destination_stubs": True}
                        )
                    }
                )
            }
        )
    settings = _apply_generation_mode_for_command(ctx, settings, generation_mode)
    if not force_llm_regen and not settings.agent.generation.use_deterministic_screen:
        force_llm_regen = True
    try:
        result = asyncio.run(
            run_pipeline(
                settings,
                figma_url=figma_url,
                project_dir=root,
                feature_name=feature_name,
                dry_run=dry_run,
                verbose=verbose,
                sync_enabled=False if no_sync else None,
                regenerate_templates=regenerate_templates,
                force_llm_regen=force_llm_regen,
                from_dump=from_dump,
                require_figma_token=from_dump is None,
            )
        )
    except BaseException as exc:
        _handle_cli_exception(exc, command="generate", verbose=verbose)

    for warning in result.warnings:
        console.print(f"[yellow]Warning:[/yellow] {warning}")

    if dry_run:
        if not dump_design:
            console.print(
                "[yellow]Dry-run output omits full design payload by default.[/yellow] "
                "Use --dump-design to include cleanTree/tokens."
            )
        console.print(f"[dim]run_id={result.run_id}[/dim]")
        console.print(format_dry_run_output(result, include_design=dump_design))
        raise typer.Exit(code=0)

    console.print(f"[green]Generation complete.[/green] run_id={result.run_id}")
    if result.dart_errors_log:
        console.print(f"[yellow]Dart analyzer errors:[/yellow] {result.dart_errors_log}")
    files = result.written_files or result.planned_files
    for path in files:
        console.print(f"  - {path}")


@app.command("validate-spec23")
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


_DEMO_SIGNOFF_FIXTURES: tuple[str, ...] = (
    "figma_node_sample.json",
    "figma_carousel_sample.json",
    "figma_tabs_sample.json",
    "figma_bottom_nav_sample.json",
    "figma_grid_sample.json",
)


@app.command("demo-signoff")
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


@app.command("live-check")
def live_check_command(
    figma_url: str | None = typer.Option(
        None,
        "--figma-url",
        help="Figma frame URL (overrides FIGMA_SMOKE_* for this run; prints .env hint)",
    ),
    project_dir: Path = typer.Option(
        Path("."),
        "--project-dir",
        help="Flutter project root for optional .figma_debug dumps",
    ),
    dump: bool = typer.Option(
        False,
        "--dump",
        help="Write raw Figma node JSON to .figma_debug/ (same as generate --verbose)",
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

    from figma_flutter_agent.figma.connector import FigmaConnector
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
            from figma_flutter_agent.generator.layout_common import to_snake_case
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


visual_qa_app = typer.Typer(help="Visual QA: pixel diff and typography specimens.")
app.add_typer(visual_qa_app, name="visual-qa")

batch_app = typer.Typer(help="Batch dump and offline generate for many screens.")
app.add_typer(batch_app, name="batch")


@batch_app.command("dump")
def batch_dump_command(
    ctx: typer.Context,
    manifest: Path | None = typer.Option(
        None,
        "--manifest",
        help="Path to screens.yaml batch manifest",
    ),
    skip_existing: bool = typer.Option(
        True,
        "--skip-existing/--no-skip-existing",
        help="Skip screens that already have a dump file",
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging"),
) -> None:
    """Fetch one Figma node per screen and write raw layout dumps (1 Tier-1 call each)."""
    from figma_flutter_agent.batch.dump import dump_manifest_screens
    from figma_flutter_agent.batch.manifest import load_batch_manifest
    from figma_flutter_agent.figma.connector import FigmaConnector

    configure_logging(verbose=verbose)
    settings = load_settings()
    token = settings.figma_token().strip()
    if not token:
        console.print("[red]FIGMA_ACCESS_TOKEN is not set[/red]")
        raise typer.Exit(code=1)

    if manifest is None:
        if is_interactive(ctx):
            root = _resolve_flutter_project(ctx, Path("."))
            manifest = prompt_manifest_path(ctx, root)
        else:
            console.print("[red]--manifest is required[/red]")
            raise typer.Exit(code=1)

    try:
        batch_manifest = load_batch_manifest(manifest.resolve())
    except ValueError as exc:
        console.print(f"[red]Invalid manifest:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    async def _run() -> None:
        async with FigmaConnector(token, settings.figma_api_base_url) as connector:
            written = await dump_manifest_screens(
                connector,
                batch_manifest,
                skip_existing=skip_existing,
            )
        console.print(f"[green]Batch dump complete[/green] ({len(written)} screens)")
        for screen, path in written:
            console.print(f"  - {screen.feature}: {path.as_posix()}")

    try:
        asyncio.run(_run())
    except BaseException as exc:
        _handle_cli_exception(exc, command="batch dump", verbose=verbose)


@batch_app.command("dump-file")
def batch_dump_file_command(
    ctx: typer.Context,
    project_dir: Path = typer.Option(
        Path("."),
        "--project-dir",
        help="Target Flutter project root",
    ),
    figma_url: str | None = typer.Option(
        None,
        "--figma-url",
        help="Figma file URL (with or without node-id)",
    ),
    file_key: str | None = typer.Option(
        None, "--file-key", help="Figma file key (alternative to URL)"
    ),
    manifest: Path | None = typer.Option(
        None,
        "--manifest",
        help="Write screens.yaml here (default: <project-dir>/screens.yaml)",
    ),
    skip_existing_screens: bool | None = typer.Option(
        None,
        "--skip-existing-screens/--rewrite-screens",
        help="Keep existing .figma_debug/raw/*_layout.json; default follows --write-policy",
    ),
    write_policy: DumpWritePolicy | None = typer.Option(
        None,
        "--write-policy",
        help="rewrite or skip-existing — skip uses local files, no extra Figma API",
        case_sensitive=False,
    ),
    mode: BatchDumpMode | None = typer.Option(
        None,
        "--mode",
        help="Dump scope: all, json, media, vector, raster (media modes use cached JSON)",
        case_sensitive=False,
    ),
    with_assets: bool | None = typer.Option(
        None,
        "--with-assets/--json-only",
        help="Legacy shorthand: --json-only equals --mode json; default is --mode all",
    ),
    no_write_manifest: bool = typer.Option(
        False,
        "--no-write-manifest",
        help="Do not write or overwrite screens.yaml",
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging"),
) -> None:
    """Fetch entire Figma file: JSON tree, screen dumps, manifest, and all SVG/PNG assets."""
    from figma_flutter_agent.batch.dump_mode import default_write_policy, resolve_batch_dump_mode
    from figma_flutter_agent.batch.file_dump import dump_full_figma_file
    from figma_flutter_agent.batch.screen_report import (
        print_screen_download_report,
        screen_download_all_ok,
    )
    from figma_flutter_agent.errors import FigmaUrlError
    from figma_flutter_agent.figma.connector import FigmaConnector
    from figma_flutter_agent.figma.url import parse_figma_file_key

    configure_logging(verbose=verbose)
    settings = load_settings()
    token = settings.figma_token().strip()
    if not token:
        console.print("[red]FIGMA_ACCESS_TOKEN is not set[/red]")
        raise typer.Exit(code=1)

    resolved_key = file_key.strip() if file_key else None
    if figma_url and figma_url.strip():
        try:
            resolved_key = parse_figma_file_key(figma_url.strip())
        except FigmaUrlError as exc:
            console.print(f"[red]Invalid --figma-url:[/red] {exc}")
            raise typer.Exit(code=1) from exc
    if not resolved_key:
        if is_interactive(ctx):
            resolved_key = prompt_figma_file_key()
        else:
            console.print("[red]Provide --figma-url or --file-key[/red]")
            raise typer.Exit(code=1)

    try:
        project_root = _resolve_flutter_project(ctx, project_dir)
    except FlutterProjectError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    manifest_path = manifest.resolve() if manifest is not None else None
    resolved_mode = resolve_batch_dump_mode(mode=mode, with_assets=with_assets)
    resolved_write_policy = write_policy or default_write_policy(resolved_mode)

    async def _run() -> None:
        async with FigmaConnector(token, settings.figma_api_base_url) as connector:
            return await dump_full_figma_file(
                connector,
                file_key=resolved_key,
                project_dir=project_root,
                manifest_path=manifest_path,
                write_manifest=not no_write_manifest,
                mode=resolved_mode,
                write_policy=resolved_write_policy,
                skip_existing_screens=skip_existing_screens,
                assets=settings.agent.assets,
            )

    try:
        result = asyncio.run(_run())
    except BaseException as exc:
        _handle_cli_exception(exc, command="batch dump-file", verbose=verbose)

    title = result.file_name or result.file_key
    dump_plan = plan_for_mode(result.mode)
    assets_exported = assets_attempted(dump_plan)
    all_ok = screen_download_all_ok(result.screen_reports, with_assets=assets_exported)
    headline = (
        "[green]Full file dump OK[/green]" if all_ok else "[yellow]Full file dump partial[/yellow]"
    )
    console.print(
        f"{headline} {title!r} — mode={result.mode.value}, "
        f"write={resolved_write_policy.value}, {len(result.screens)} screen(s)"
    )
    console.print(f"  full: {result.full_file_path.as_posix()}")
    if assets_exported:
        asset_bits: list[str] = []
        if dump_plan.export_svg:
            asset_bits.append("SVG")
        if dump_plan.export_raster or dump_plan.export_blur_png:
            asset_bits.append("raster")
        console.print(
            f"  assets ({'+'.join(asset_bits)}): "
            f"{result.icon_count} SVG icon(s), {result.raster_count} raster file(s)"
        )
    else:
        console.print("  assets: skipped (json-only mode)")
    if result.manifest_path is not None:
        console.print(f"  manifest: {result.manifest_path.as_posix()}")
    print_screen_download_report(
        console,
        result.screen_reports,
        with_assets=assets_exported,
        orphan_exportables=result.orphan_exportables,
        rate_limited=result.rate_limited,
    )
    if not all_ok:
        raise typer.Exit(code=1)


@batch_app.command("generate")
def batch_generate_command(
    ctx: typer.Context,
    manifest: Path | None = typer.Option(
        None,
        "--manifest",
        help="Path to screens.yaml batch manifest",
    ),
    config: Path | None = typer.Option(
        None, "--config", help="Path to agent .ai-figma-flutter.yml (default: repo root)"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Plan without writing files"),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging"),
    regenerate_templates: bool = typer.Option(
        False,
        "--regenerate-templates",
        help="Force rewrite of all planned files during incremental sync",
    ),
    allow_dev_profile: bool = typer.Option(
        False,
        "--allow-dev-profile",
        help="Skip production gates (not suitable for release sign-off)",
    ),
    require_dump: bool = typer.Option(
        True,
        "--require-dump/--allow-live",
        help="Require cached dumps (default) or call live Figma API per screen",
    ),
    generation_mode: GenerationLayoutMode | None = typer.Option(
        None,
        "--generation-mode",
        help="Screen codegen: deterministic or llm (interactive prompt when omitted)",
        case_sensitive=False,
    ),
) -> None:
    """Generate Flutter outputs for every screen in the manifest (offline when dumps exist)."""
    from figma_flutter_agent.batch.manifest import load_batch_manifest
    from figma_flutter_agent.batch.run import run_batch_generate

    configure_logging(verbose=verbose)
    if manifest is None:
        if is_interactive(ctx):
            root = _resolve_flutter_project(ctx, Path("."))
            manifest = prompt_manifest_path(ctx, root)
        else:
            console.print("[red]--manifest is required[/red]")
            raise typer.Exit(code=1)

    try:
        batch_manifest = load_batch_manifest(manifest.resolve())
    except ValueError as exc:
        console.print(f"[red]Invalid manifest:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if config is None:
        from figma_flutter_agent.dev.project import ensure_project_config

        config = ensure_project_config(batch_manifest.project_dir)
    settings = load_settings(config)
    if not dry_run and not allow_dev_profile:
        settings = apply_production_profile(settings)
    elif not dry_run and allow_dev_profile:
        console.print(
            "[yellow]Dev profile:[/yellow] production gates disabled (--allow-dev-profile)."
        )

    settings = _apply_generation_mode_for_command(ctx, settings, generation_mode)
    batch_force_llm_regen = not settings.agent.generation.use_deterministic_screen

    try:
        report = asyncio.run(
            run_batch_generate(
                batch_manifest,
                settings,
                dry_run=dry_run,
                verbose=verbose,
                allow_dev_profile=allow_dev_profile,
                regenerate_templates=regenerate_templates,
                require_dump=require_dump,
                force_llm_regen=batch_force_llm_regen,
            )
        )
    except BaseException as exc:
        _handle_cli_exception(exc, command="batch generate", verbose=verbose)

    for item in report.results:
        if item.success:
            files = (
                item.pipeline.written_files or item.pipeline.planned_files if item.pipeline else []
            )
            console.print(f"[green]OK[/green] {item.feature} ({len(files)} files)")
        else:
            console.print(f"[red]FAIL[/red] {item.feature}: {item.error}")

    if report.passed:
        console.print(f"[green]Batch generate complete[/green] ({len(report.results)} screens)")
        raise typer.Exit(code=0)

    console.print(
        f"[red]Batch generate failed[/red] ({len(report.failures)} of {len(report.results)})"
    )
    raise typer.Exit(code=1)


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


if __name__ == "__main__":
    app()
