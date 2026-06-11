"""Low-level prompt primitives (no ctx/wizard-state dependency)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console

if TYPE_CHECKING:
    from figma_flutter_agent.batch.manifest import BatchManifest
    from figma_flutter_agent.config import Settings
    from figma_flutter_agent.figma.url import FigmaUrlKind, ParsedFigmaInput

console = Console()


def print_pipeline_warnings(warnings: list[str]) -> None:
    """Print pipeline warnings to the interactive console."""
    for warning in warnings:
        lowered = warning.lower()
        if (
            "font" in lowered
            or "assets/fonts" in lowered
            or "rename" in lowered
            or "fallback" in lowered
            or "substitute" in lowered
            or "skipped" in lowered
            or "refine off" in lowered
            or "delegates" in lowered
        ):
            console.print(f"[yellow]Warning:[/yellow] {warning}")
        else:
            console.print(f"[dim]{warning}[/dim]")


def tty_interactive_default() -> bool:
    """Return True when stdin/stdout are TTYs (safe to prompt)."""
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except (AttributeError, ValueError):
        return False


def get_session(ctx: typer.Context | None) -> object | None:
    """Return the active ``CliSession`` from Typer context, if any."""
    from figma_flutter_agent.wizard.state import CliSession

    if ctx is None or not isinstance(ctx.obj, dict):
        return None
    session = ctx.obj.get("session")
    if isinstance(session, CliSession):
        return session
    return None


def is_interactive(ctx: typer.Context | None) -> bool:
    """Return True when interactive prompts are enabled."""
    session = get_session(ctx)
    if session is None:
        return False
    if session.force_non_interactive:
        return False
    return session.interactive


def should_prompt(ctx: typer.Context | None, value: object | None) -> bool:
    """Return True when ``value`` is missing and prompts are allowed."""
    if value is not None and value != "":
        return False
    return is_interactive(ctx)


def prompt_text(message: str, *, default: str | None = None) -> str:
    """Prompt for a single line of text."""
    return typer.prompt(message, default=default or "").strip()


def prompt_confirm(message: str, *, default: bool = True) -> bool:
    """Prompt for yes/no confirmation."""
    return typer.confirm(message, default=default)


def _colorize_choice_label(option: str) -> str:
    """Return a Rich markup label with a colored command prefix."""
    label, separator, description = option.partition(" — ")
    if not separator:
        style = _choice_label_style(label)
        return f"[{style}]{label}[/{style}]"

    style = _choice_label_style(label)
    return f"[{style}]{label}[/{style}]{separator}{description}"


def _choice_label_style(label: str) -> str:
    """Return the Rich style for interactive menu command prefixes."""
    if label == "launch":
        return "bold red"
    return "bold yellow"


def _menu_command(option: str) -> str:
    """Return the command prefix from a ``command — description`` menu label."""
    return option.partition(" — ")[0]


def _choice_display_index(
    index: int,
    options_len: int,
    *,
    zero_indexed: bool,
    quit_zero_last: bool,
) -> int:
    """Map an option list index to the number shown beside it."""
    if quit_zero_last:
        if index == options_len - 1:
            return 0
        return index + 1
    if zero_indexed:
        return index
    return index + 1


def _choice_index_from_input(
    raw: str,
    options_len: int,
    *,
    zero_indexed: bool,
    quit_zero_last: bool,
) -> int | None:
    """Map user numeric input to an option list index."""
    if not raw.isdigit():
        return None
    num = int(raw)
    if quit_zero_last:
        if num == 0:
            return options_len - 1
        if 1 <= num <= options_len - 1:
            return num - 1
        return None
    picked = num if zero_indexed else num - 1
    if 0 <= picked < options_len:
        return picked
    return None


def prompt_choice(
    title: str,
    options: list[str],
    *,
    default: str | None = None,
    zero_indexed: bool = False,
    quit_zero_last: bool = False,
) -> str:
    """Prompt the user to pick one of ``options`` by number or label."""
    if not options:
        msg = "prompt_choice requires at least one option"
        raise ValueError(msg)
    if quit_zero_last and zero_indexed:
        msg = "prompt_choice cannot combine zero_indexed and quit_zero_last"
        raise ValueError(msg)
    console.print(f"[bold]{title}[/bold]")
    default_index = 0
    if default is not None:
        try:
            default_index = options.index(default)
        except ValueError:
            default_index = 0
    options_len = len(options)
    for index, option in enumerate(options):
        display_index = _choice_display_index(
            index,
            options_len,
            zero_indexed=zero_indexed,
            quit_zero_last=quit_zero_last,
        )
        marker = " [cyan](default)[/cyan]" if index == default_index else ""
        console.print(f"  {display_index}. {_colorize_choice_label(option)}{marker}")
    default_display = _choice_display_index(
        default_index,
        options_len,
        zero_indexed=zero_indexed,
        quit_zero_last=quit_zero_last,
    )
    while True:
        raw = typer.prompt(
            "Choice",
            default=str(default_display),
        ).strip()
        picked = _choice_index_from_input(
            raw,
            options_len,
            zero_indexed=zero_indexed,
            quit_zero_last=quit_zero_last,
        )
        if picked is not None:
            return options[picked]
        for option in options:
            if raw.lower() == option.lower():
                return option
            command = _menu_command(option)
            if command and raw.lower() == command.lower():
                return option
        console.print("[red]Invalid choice — enter a number or feature name.[/red]")


def ensure_llm_generation_ready(settings: Settings) -> None:
    """Warn when LLM-IR generation is selected without an API key."""
    if not settings.llm_api_key():
        console.print(
            "[yellow]Warning:[/yellow] LLM-IR generation requires an API key in .env. "
            f"Set {settings.llm_api_key_env_name()}."
        )


def _prompting_enabled(ctx: typer.Context | None) -> bool:
    """Return True when Typer session or wizard TTY allows prompts."""
    if is_interactive(ctx):
        return True
    return ctx is None and tty_interactive_default()


def prompt_project_dir(
    ctx: typer.Context | None,
    project_dir: Path,
    *,
    env_project_dir: Path | None = None,
) -> Path:
    """Resolve Flutter project root, prompting when needed."""
    from figma_flutter_agent.dev.project import (
        default_flutter_project_candidate,
        is_implicit_project_dir,
    )
    from figma_flutter_agent.errors import FlutterProjectError

    candidate = project_dir.expanduser()
    if not (candidate.resolve() / "pubspec.yaml").is_file() and is_implicit_project_dir(
        project_dir
    ):
        candidate = default_flutter_project_candidate(env_project_dir=env_project_dir)
    if (candidate.resolve() / "pubspec.yaml").is_file():
        return candidate.resolve()
    if _prompting_enabled(ctx):
        while True:
            raw = prompt_text(
                "Flutter project directory (path to pubspec.yaml)",
                default=str(candidate),
            )
            path = Path(raw).expanduser().resolve()
            if (path / "pubspec.yaml").is_file():
                return path
            console.print(f"[red]No pubspec.yaml at {path}[/red]")
    raise FlutterProjectError(f"Flutter project not found at {candidate}")


def prompt_import_feature_name(
    figma_frame_name: str,
    manifest: BatchManifest,
    node_id: str,
) -> str | None:
    """Prompt for a manifest feature slug when importing a Figma frame.

    Args:
        figma_frame_name: Layer name from Figma.
        manifest: Current batch manifest (used to preview the default slug).
        node_id: Figma node id for the frame.

    Returns:
        User-entered slug, or ``None`` when Enter is pressed (use Figma-derived name).
    """
    from figma_flutter_agent.dev.import_figma import resolve_import_feature_name

    default_slug = resolve_import_feature_name(None, figma_frame_name, manifest, node_id)
    raw = prompt_text(
        f'Screen slug in screens.yaml [Figma: "{figma_frame_name}"] '
        f"(Enter = {default_slug})",
        default="",
    )
    return raw if raw else None


def prompt_screen_name(ctx: typer.Context | None, manifest: BatchManifest) -> str:
    """Prompt for a screen feature slug from ``manifest``."""
    options = [screen.feature for screen in manifest.screens]
    return prompt_choice("Which screen?", options, default=options[0] if options else None)


def prompt_figma_file_key(
    *,
    default: str | None = None,
    ctx: typer.Context | None = None,
    project_dir: Path | None = None,
) -> str:
    """Prompt for a Figma file key or design URL."""
    from figma_flutter_agent.figma.url import FigmaUrlKind

    parsed = prompt_figma_input(
        default=default,
        expect_kind=FigmaUrlKind.FILE,
        ctx=ctx,
        project_dir=project_dir,
    )
    return parsed.file_key


def prompt_figma_frame_url(
    *,
    default: str | None = None,
    ctx: typer.Context | None = None,
    project_dir: Path | None = None,
) -> str:
    """Prompt for a Figma frame URL containing ``node-id``."""
    from figma_flutter_agent.figma.url import FigmaUrlKind, build_figma_url

    parsed = prompt_figma_input(
        default=default,
        expect_kind=FigmaUrlKind.FRAME,
        ctx=ctx,
        project_dir=project_dir,
    )
    if parsed.node_id is None:
        msg = "Frame URL must include node-id"
        raise ValueError(msg)
    return build_figma_url(parsed.file_key, parsed.node_id)


def _wizard_default_figma_input(
    ctx: typer.Context | None,
    *,
    project_dir: Path | None,
    prefer_kind: FigmaUrlKind | None,
) -> str:
    """Resolve wizard pre-fill from manifest, then env."""
    from figma_flutter_agent.batch.manifest import load_batch_manifest
    from figma_flutter_agent.config import load_settings
    from figma_flutter_agent.figma.url import resolve_default_figma_input
    from figma_flutter_agent.wizard.state import _wizard_active_screen_label

    settings = load_settings()
    manifest = None
    if project_dir is not None:
        manifest_path = project_dir / "screens.yaml"
        if manifest_path.is_file():
            manifest = load_batch_manifest(manifest_path)
    active_screen = _wizard_active_screen_label(ctx) if ctx is not None else None
    return resolve_default_figma_input(
        prefer_kind=prefer_kind,
        manifest=manifest,
        active_screen=active_screen,
        figma_default_url=settings.figma_default_url,
        figma_smoke_file_key=settings.figma_smoke_file_key,
        figma_smoke_node_id=settings.figma_smoke_node_id,
    )


def prompt_figma_input(
    *,
    default: str | None = None,
    expect_kind: FigmaUrlKind | None = None,
    default_kind: FigmaUrlKind | None = None,
    ctx: typer.Context | None = None,
    project_dir: Path | None = None,
    optional: bool = False,
) -> ParsedFigmaInput | None:
    """Prompt for a Figma URL or file key and auto-detect file vs frame scope.

    Args:
        default: Optional default input string.
        expect_kind: When set, re-prompt until the parsed kind matches.
        default_kind: When set, pre-fill from manifest/env using this scope.
        ctx: Optional wizard context for active screen and project memory.
        project_dir: Flutter project root used to load ``screens.yaml``.
        optional: When True, empty input with no default skips the prompt.

    Returns:
        Parsed Figma input, or ``None`` when ``optional`` and input is skipped.

    Raises:
        FigmaUrlError: When parsing fails after user input.
        ValueError: When ``expect_kind`` is not satisfied.
    """
    from figma_flutter_agent.errors import FigmaUrlError
    from figma_flutter_agent.figma.url import (
        FigmaUrlKind,
        describe_figma_input,
        parse_figma_input,
    )

    resolved_default = default
    if not resolved_default and (ctx is not None or project_dir is not None):
        resolved_default = _wizard_default_figma_input(
            ctx,
            project_dir=project_dir,
            prefer_kind=default_kind if default_kind is not None else expect_kind,
        )

    while True:
        raw = prompt_text(
            "Figma URL or file key (file link or frame link with node-id)",
            default=resolved_default or "",
        )
        if not raw:
            if optional and not resolved_default:
                return None
            console.print("[red]URL or file key is required.[/red]")
            continue
        try:
            parsed = parse_figma_input(raw)
        except FigmaUrlError as exc:
            console.print(f"[red]{exc}[/red]")
            continue
        console.print(f"[cyan]Detected:[/cyan] {describe_figma_input(parsed)}")
        if expect_kind is not None and parsed.kind != expect_kind:
            if expect_kind == FigmaUrlKind.FRAME:
                console.print("[red]Expected a frame URL with node-id=…[/red]")
            else:
                console.print("[red]Expected a file URL or file key (without node-id).[/red]")
            continue
        return parsed


def prompt_manifest_path(ctx: typer.Context | None, project_dir: Path) -> Path:
    """Return ``screens.yaml`` path, prompting when the default is missing."""
    default = project_dir / "screens.yaml"
    if default.is_file():
        if not _prompting_enabled(ctx):
            return default
        use_default = prompt_confirm(
            f"Use batch manifest at {default.as_posix()}?",
            default=True,
        )
        if use_default:
            return default
    if _prompting_enabled(ctx):
        while True:
            raw = prompt_text("Path to screens.yaml", default=str(default))
            path = Path(raw).expanduser().resolve()
            if path.is_file():
                return path
            console.print(f"[red]Manifest not found: {path}[/red]")
    if default.is_file():
        return default
    msg = f"Batch manifest not found at {default.as_posix()}"
    raise FileNotFoundError(msg)
