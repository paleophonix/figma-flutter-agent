"""Shared CLI helper utilities."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from loguru import logger
from pydantic import ValidationError
from rich.console import Console

from figma_flutter_agent.errors import (
    FigmaFlutterError,
    FlutterProjectError,
    PipelineError,
    format_error_for_log,
)
from figma_flutter_agent.logging_setup import LOG_FILE
from figma_flutter_agent.wizard import (
    is_interactive,
    prompt_figma_frame_url,
    prompt_project_dir,
    prompt_screen_name,
    should_prompt,
)

console = Console()

_CLI_BOUNDARY_ERRORS: tuple[type[BaseException], ...] = (
    OSError,
    RuntimeError,
    ValueError,
    TypeError,
    KeyError,
    json.JSONDecodeError,
    ValidationError,
)


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
) -> tuple[Path, str | None, Path | None, str | None]:
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
            from figma_flutter_agent.wizard import prompt_confirm

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
        if resolved_dump is None:
            from figma_flutter_agent.pipeline.helpers import resolve_manifest_cached_dump

            auto_dump = resolve_manifest_cached_dump(
                root,
                feature_name=resolved_feature,
                node_id=parsed.node_id,
                file_key=parsed.file_key,
            )
            if auto_dump is not None:
                resolved_dump = auto_dump
    if resolved_url is None and resolved_dump is None:
        console.print("[red]Provide --figma-url, --from-dump, or use interactive mode (-i)[/red]")
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
