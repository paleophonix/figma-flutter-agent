"""Wizard code generation action handlers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console

if TYPE_CHECKING:
    pass

console = Console()


def _wizard_generate(ctx: typer.Context) -> None:
    import asyncio

    from figma_flutter_agent.batch.manifest import load_batch_manifest
    from figma_flutter_agent.batch.run import _figma_url_for_screen, _resolve_dump
    from figma_flutter_agent.config import load_settings
    from figma_flutter_agent.dev.project import (
        ensure_project_config,
        resolve_manifest_path,
    )
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
    config_path = ensure_project_config(root)
    use_dump = prompt_confirm("Use cached .figma_debug dump (offline)?", default=True)
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
    settings = load_settings(config_path)
    ensure_llm_generation_ready(settings)
    force_llm_regen = True
    console.print("[dim]Codegen:[/dim] LLM screen IR + emitter")
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
    console.print("[green]Generation complete.[/green]")


def _wizard_batch_generate(ctx: typer.Context) -> None:
    import asyncio

    from figma_flutter_agent.batch.manifest import load_batch_manifest
    from figma_flutter_agent.batch.run import run_batch_generate
    from figma_flutter_agent.config import load_settings
    from figma_flutter_agent.dev.project import ensure_project_config
    from figma_flutter_agent.wizard.prompts import (
        ensure_llm_generation_ready,
        prompt_manifest_path,
    )
    from figma_flutter_agent.wizard.state import _wizard_project_dir

    root = _wizard_project_dir(ctx)
    config_path = ensure_project_config(root)
    manifest_path = prompt_manifest_path(ctx, root)
    manifest = load_batch_manifest(manifest_path)
    settings = load_settings(config_path)
    ensure_llm_generation_ready(settings)
    force_llm_regen = True
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


def _wizard_generate_menu(ctx: typer.Context) -> None:
    """Run batch or single-screen codegen based on submenu selection."""
    from figma_flutter_agent.wizard.menus import _generate_menu_options
    from figma_flutter_agent.wizard.prompts import _menu_command, prompt_choice

    mode_label = prompt_choice(
        "Generate mode",
        _generate_menu_options(),
        default=_generate_menu_options()[0],
    )
    if _menu_command(mode_label) == "batch":
        _wizard_batch_generate(ctx)
    else:
        _wizard_generate(ctx)
