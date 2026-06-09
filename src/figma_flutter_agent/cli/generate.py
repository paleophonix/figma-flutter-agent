"""Generation commands: generate, run, import-tokens."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer

from figma_flutter_agent.config import (
    apply_production_profile,
    load_settings,
)
from figma_flutter_agent.errors import FlutterProjectError
from figma_flutter_agent.logging_setup import configure_logging
from figma_flutter_agent.wizard import is_interactive, prompt_screen_name

from .helpers import (
    _exit_domain_error,
    _handle_cli_exception,
    _resolve_flutter_project,
    _resolve_generate_target,
    console,
)


def import_tokens_command(
    path: Path = typer.Argument(..., help="Path to W3C / Figma Tokens plugin JSON export"),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write normalized DesignTokens JSON (stdout when omitted)",
    ),
) -> None:
    """Import design tokens from plugin JSON (no Node.js Style Dictionary required)."""
    from figma_flutter_agent.parser.tokens.import_json import import_design_tokens_json

    tokens = import_design_tokens_json(path)
    payload = tokens.model_dump_json(indent=2)
    if output is None:
        console.print(payload)
        return
    output.write_text(payload + "\n", encoding="utf-8")
    console.print(f"Wrote {output.as_posix()}")


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
    """Generate one screen from cached dump + screen IR and launch ``flutter run``."""
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


def generate(
    ctx: typer.Context,
    figma_url: str | None = typer.Option(
        None,
        "--figma-url",
        help="Figma frame URL with node-id (optional when --from-dump and screens.yaml exist)",
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
    from_ir: bool = typer.Option(
        False,
        "--from-ir",
        help="Skip LLM screen IR; load .figma_debug/ir/<feature>_pre_emit.json (or llm_validated/llm_parsed)",
    ),
    from_ir_path: Path | None = typer.Option(
        None,
        "--from-ir-path",
        help="Explicit screen IR JSON file or directory (implies --from-ir)",
    ),
    golden_runtime: str | None = typer.Option(
        None,
        "--golden-runtime",
        help="Golden capture runtime: auto | docker | host (visual refine)",
    ),
    no_docker: bool = typer.Option(
        False,
        "--no-docker",
        help="Force host golden capture (FIGMA_GOLDEN_RUNTIME=host)",
    ),
) -> None:
    """Generate Flutter screen, theme, and assets from a Figma frame."""
    from figma_flutter_agent.pipeline.dry_run import format_dry_run_output
    from figma_flutter_agent.pipeline.run import run_pipeline

    configure_logging(verbose=verbose)

    import os

    if no_docker:
        os.environ["FIGMA_GOLDEN_RUNTIME"] = "host"
    elif golden_runtime is not None:
        os.environ["FIGMA_GOLDEN_RUNTIME"] = golden_runtime.strip().lower()

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
    settings = settings
    use_cached_ir = from_ir or from_ir_path is not None
    if (
        not force_llm_regen
        and settings.agent.generation.use_screen_ir
        and not use_cached_ir
    ):
        force_llm_regen = True

    from figma_flutter_agent.dev.ast_sidecar_build import ensure_ast_sidecar_binary

    def _generate_ast_print(message: str) -> None:
        if message.startswith("Built AST"):
            console.print(f"[green]{message}[/green]")
        elif "failed" in message.lower() or message.startswith("Cannot"):
            console.print(f"[yellow]{message}[/yellow]")
        else:
            console.print(f"[dim]{message}[/dim]")

    ensure_ast_sidecar_binary(
        settings,
        interactive=is_interactive(ctx),
        build_if_missing=True,
        console_print=_generate_ast_print,
    )

    from figma_flutter_agent.dev.golden_capture_build import ensure_golden_capture_image
    from figma_flutter_agent.validation.golden_runtime import resolve_golden_runtime

    if resolve_golden_runtime(settings=settings).runtime == "docker":
        ensure_golden_capture_image(
            settings,
            interactive=is_interactive(ctx),
            build_if_missing=True,
            console_print=_generate_ast_print,
        )

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
                from_ir=from_ir,
                from_ir_path=from_ir_path,
                require_figma_token=from_dump is None and not use_cached_ir,
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
    if result.render_log_dir:
        console.print(f"[dim]Combat renders:[/dim] {result.render_log_dir}")
    if result.dart_errors_log:
        console.print(f"[yellow]Dart analyzer errors:[/yellow] {result.dart_errors_log}")
    files = result.written_files or result.planned_files
    for path in files:
        console.print(f"  - {path}")
