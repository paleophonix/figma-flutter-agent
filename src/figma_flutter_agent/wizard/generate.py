"""Wizard code generation action handlers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console

from figma_flutter_agent.wizard.capture_prompt import prompt_wizard_capture_settings

if TYPE_CHECKING:
    from figma_flutter_agent.config import Settings

console = Console()


def _wizard_generate(ctx: typer.Context, *, settings: Settings) -> None:
    import asyncio

    from figma_flutter_agent.batch.manifest import load_batch_manifest
    from figma_flutter_agent.batch.run import _figma_url_for_screen, _resolve_dump
    from figma_flutter_agent.dev.project import resolve_manifest_path
    from figma_flutter_agent.figma.url import FigmaUrlKind
    from figma_flutter_agent.pipeline.run import run_pipeline
    from figma_flutter_agent.wizard.prompts import (
        ensure_llm_generation_ready,
        print_pipeline_warnings,
        prompt_confirm,
        prompt_figma_input,
        prompt_screen_name,
        prompt_text,
    )
    from figma_flutter_agent.wizard.state import _wizard_project_dir

    root = _wizard_project_dir(ctx)
    use_dump = prompt_confirm("Use cached .debug dump (offline)?", default=True)
    from_dump: Path | None = None
    figma_url: str
    feature_name: str | None = None
    if use_dump:
        manifest = load_batch_manifest(resolve_manifest_path(root))
        screen = prompt_screen_name(ctx, manifest)
        entry = next(item for item in manifest.screens if item.feature == screen)
        from_dump = _resolve_dump(entry, manifest.project_dir)
        figma_url = _figma_url_for_screen(manifest, entry)
        feature_name = screen
    else:
        parsed = prompt_figma_input(
            expect_kind=FigmaUrlKind.FRAME,
            ctx=ctx,
            project_dir=root,
        )
        if parsed is None:
            msg = "Frame URL prompt returned no input"
            raise RuntimeError(msg)
        from figma_flutter_agent.figma.url import build_figma_url

        figma_url = build_figma_url(parsed.file_key, parsed.node_id or "")
        raw_feature = prompt_text("Feature folder name (Enter = auto)", default="")
        feature_name = raw_feature or None
    ensure_llm_generation_ready(settings)
    force_llm_regen = True
    capture_note = "on" if settings.agent.dev.debug_capture else "off"
    console.print(f"[dim]Codegen:[/dim] LLM screen IR + emitter (capture {capture_note})")
    result = asyncio.run(
        run_pipeline(
            settings,
            figma_url=figma_url,
            project_dir=root,
            feature_name=feature_name,
            from_dump=from_dump,
            require_figma_token=from_dump is None,
            force_llm_regen=force_llm_regen,
        )
    )
    print_pipeline_warnings(result.warnings)
    if result.flutter_capture_ok is False:
        console.print(
            "[yellow]Generation committed, but Flutter capture is blocked. "
            "Run wizard debug (forensic board) to repair capture blockers.[/yellow]"
        )
    else:
        console.print("[green]Generation complete.[/green]")


def _wizard_batch_generate(ctx: typer.Context, *, settings: Settings) -> None:
    import asyncio

    from figma_flutter_agent.batch.manifest import load_batch_manifest
    from figma_flutter_agent.batch.run import run_batch_generate
    from figma_flutter_agent.wizard.prompts import (
        ensure_llm_generation_ready,
        prompt_manifest_path,
    )
    from figma_flutter_agent.wizard.state import _wizard_project_dir

    root = _wizard_project_dir(ctx)
    manifest_path = prompt_manifest_path(ctx, root)
    manifest = load_batch_manifest(manifest_path)
    ensure_llm_generation_ready(settings)
    force_llm_regen = True
    capture_note = "on" if settings.agent.dev.debug_capture else "off"
    console.print(f"[dim]Batch codegen[/dim] (capture {capture_note})")
    report = asyncio.run(
        run_batch_generate(
            manifest,
            settings,
            allow_dev_profile=True,
            force_llm_regen=force_llm_regen,
        )
    )
    if report.passed:
        console.print(f"[green]Batch OK[/green] ({len(report.results)} screens)")
    else:
        console.print(f"[red]Batch failed[/red] ({len(report.failures)} failures)")
        raise typer.Exit(code=1)


def _wizard_compare_generate(ctx: typer.Context, *, settings: Settings) -> None:
    import asyncio

    from figma_flutter_agent.batch.manifest import load_batch_manifest
    from figma_flutter_agent.batch.run import _figma_url_for_screen, _resolve_dump
    from figma_flutter_agent.dev.project import resolve_manifest_path
    from figma_flutter_agent.figma.url import FigmaUrlKind
    from figma_flutter_agent.pipeline.run import run_pipeline
    from figma_flutter_agent.wizard.prompts import (
        ensure_llm_generation_ready,
        print_pipeline_warnings,
        prompt_confirm,
        prompt_figma_input,
        prompt_screen_name,
        prompt_text,
    )
    from figma_flutter_agent.wizard.state import _wizard_project_dir

    root = _wizard_project_dir(ctx)
    models = settings.resolved_llm_compare_models()
    use_dump = prompt_confirm("Use cached .debug dump (offline)?", default=True)
    from_dump: Path | None = None
    figma_url: str
    feature_name: str | None = None
    if use_dump:
        manifest = load_batch_manifest(resolve_manifest_path(root))
        screen = prompt_screen_name(ctx, manifest)
        entry = next(item for item in manifest.screens if item.feature == screen)
        from_dump = _resolve_dump(entry, manifest.project_dir)
        figma_url = _figma_url_for_screen(manifest, entry)
        feature_name = screen
    else:
        parsed = prompt_figma_input(
            expect_kind=FigmaUrlKind.FRAME,
            ctx=ctx,
            project_dir=root,
        )
        if parsed is None:
            msg = "Frame URL prompt returned no input"
            raise RuntimeError(msg)
        from figma_flutter_agent.figma.url import build_figma_url

        figma_url = build_figma_url(parsed.file_key, parsed.node_id or "")
        raw_feature = prompt_text("Feature folder name (Enter = auto)", default="")
        feature_name = raw_feature or None
    ensure_llm_generation_ready(settings)
    console.print("[dim]Compare:[/dim] LLM screen IR only (no Dart write)")
    for index, model in enumerate(models, start=1):
        console.print(f"  ir_{index}.json ← {model}")
    result = asyncio.run(
        run_pipeline(
            settings,
            figma_url=figma_url,
            project_dir=root,
            feature_name=feature_name,
            from_dump=from_dump,
            require_figma_token=from_dump is None,
            force_llm_regen=True,
            llm_compare=True,
        )
    )
    print_pipeline_warnings(result.warnings)
    console.print(
        "[green]Compare complete — see ir_1.json, ir_2.json, ir_3.json under .debug/screen/[/green]"
    )


def _wizard_generate_menu(ctx: typer.Context) -> None:
    """Run batch or single-screen codegen based on submenu selection."""
    from figma_flutter_agent.dev.project import ensure_project_config
    from figma_flutter_agent.wizard.menus import _generate_menu_options, _is_menu_return
    from figma_flutter_agent.wizard.prompts import _menu_command, prompt_choice
    from figma_flutter_agent.wizard.state import _wizard_project_dir

    mode_label = prompt_choice(
        "Generate mode",
        _generate_menu_options(),
        default=_generate_menu_options()[0],
    )
    if _is_menu_return(mode_label):
        return
    root = _wizard_project_dir(ctx)
    config_path = ensure_project_config(root)
    settings = prompt_wizard_capture_settings(config_path)
    if _menu_command(mode_label) == "batch":
        _wizard_batch_generate(ctx, settings=settings)
    elif _menu_command(mode_label) == "compare":
        _wizard_compare_generate(ctx, settings=settings)
    else:
        _wizard_generate(ctx, settings=settings)
