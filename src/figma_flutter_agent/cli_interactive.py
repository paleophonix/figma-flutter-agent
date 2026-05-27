"""Interactive CLI prompts (Flutter-style dialog when options are missing)."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console

if TYPE_CHECKING:
    from figma_flutter_agent.batch.manifest import BatchManifest
    from figma_flutter_agent.config import Settings
    from figma_flutter_agent.figma.url import FigmaUrlKind, ParsedFigmaInput
    from figma_flutter_agent.generation.mode import GenerationLayoutMode

console = Console()


def print_pipeline_warnings(warnings: list[str]) -> None:
    """Print pipeline warnings to the interactive console."""
    for warning in warnings:
        lowered = warning.lower()
        if (
            "fallback" in lowered
            or "skipped" in lowered
            or "refine off" in lowered
            or "delegates" in lowered
        ):
            console.print(f"[yellow]Warning:[/yellow] {warning}")
        else:
            console.print(f"[dim]{warning}[/dim]")


@dataclass
class CliSession:
    """Interactive CLI session flags stored on ``typer.Context.obj``."""

    interactive: bool
    force_non_interactive: bool = False


def tty_interactive_default() -> bool:
    """Return True when stdin/stdout are TTYs (safe to prompt)."""
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except (AttributeError, ValueError):
        return False


def get_session(ctx: typer.Context | None) -> CliSession | None:
    """Return the active ``CliSession`` from Typer context, if any."""
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
        if label == "quit":
            return f"[bold red]{label}[/bold red]"
        return f"[bold yellow]{label}[/bold yellow]"

    style = _choice_label_style(label)
    return f"[{style}]{label}[/{style}]{separator}{description}"


def _choice_label_style(label: str) -> str:
    """Return the Rich style for interactive menu command prefixes."""
    if label == "quit":
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


def prompt_generation_layout_mode(settings: Settings) -> GenerationLayoutMode:
    """Ask whether to use deterministic or LLM screen codegen."""
    from figma_flutter_agent.generation.mode import (
        GenerationLayoutMode,
        generation_mode_from_menu,
        generation_mode_menu_label,
        generation_mode_menu_options,
        wizard_default_generation_layout_mode,
    )

    options = generation_mode_menu_options()
    default_label = generation_mode_menu_label(wizard_default_generation_layout_mode())
    label = prompt_choice("Code generation mode", options, default=default_label)
    mode = generation_mode_from_menu(label)
    if mode is GenerationLayoutMode.LLM and not settings.llm_api_key():
        console.print(
            "[yellow]Warning:[/yellow] LLM mode selected but no API key found in .env. "
            f"Set {settings.llm_api_key_env_name()} or switch to deterministic."
        )
    return mode


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
    from figma_flutter_agent.dev.project import resolve_manifest_path
    from figma_flutter_agent.figma.url import resolve_default_figma_input

    settings = load_settings()
    manifest = None
    if project_dir is not None:
        manifest_path = resolve_manifest_path(project_dir)
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


@dataclass
class WizardState:
    """Cached wizard selections between menu iterations."""

    project_dir: Path | None = None
    active_screen: str | None = None


def _wizard_active_screen_label(ctx: typer.Context) -> str | None:
    """Return the session or wired active screen slug, if known."""
    from figma_flutter_agent.dev.run import detect_wired_screen_feature

    state = _wizard_state(ctx)
    if state.active_screen:
        return state.active_screen
    if state.project_dir is not None:
        return detect_wired_screen_feature(state.project_dir)
    return None


def _wizard_state(ctx: typer.Context) -> WizardState:
    if not isinstance(ctx.obj, dict):
        ctx.ensure_object(dict)
    state = ctx.obj.get("wizard")
    if not isinstance(state, WizardState):
        state = WizardState()
        ctx.obj["wizard"] = state
    return state


def _load_persisted_active_screen(project_dir: Path) -> str | None:
    """Return the active screen slug from disk prefs, if any."""
    from figma_flutter_agent.dev.wizard_prefs import load_wizard_prefs

    return load_wizard_prefs(project_dir).active_screen


def _persist_active_screen(ctx: typer.Context, screen: str | None) -> None:
    """Remember the active screen in session memory and on disk."""
    from figma_flutter_agent.dev.wizard_prefs import save_wizard_prefs

    state = _wizard_state(ctx)
    state.active_screen = screen
    if state.project_dir is not None:
        save_wizard_prefs(state.project_dir, active_screen=screen)


def _bootstrap_wizard_state(ctx: typer.Context) -> None:
    """Load default project and persisted active screen before the first menu draw."""
    from figma_flutter_agent.dev.project import (
        default_flutter_project_candidate,
        env_configured_project_dir,
    )

    state = _wizard_state(ctx)
    if state.project_dir is None or not (state.project_dir / "pubspec.yaml").is_file():
        candidate = default_flutter_project_candidate(
            env_project_dir=env_configured_project_dir(),
        )
        if (candidate / "pubspec.yaml").is_file():
            state.project_dir = candidate.resolve()
    if state.project_dir is not None and state.active_screen is None:
        state.active_screen = _load_persisted_active_screen(state.project_dir)


def _wizard_menu_options() -> list[str]:
    """Menu items in pipeline order (setup → fetch → select → generate → run → validate)."""
    return [
        "change — pick Flutter project (pubspec.yaml) root",
        "check — doctor and/or live Figma connectivity",
        "fetch — import frame or dump file from Figma (URL auto-detect)",
        "list — view manifest and preflight status",
        "select — pick active screen and wire main.dart",
        "generate — codegen one or all screens",
        "run — generate, sync, and launch Flutter",
        "analyze — run flutter analyze on project",
        "test — offline quality gates (demo-signoff + pytest)",
        "quit",
    ]


def _check_menu_options() -> list[str]:
    """Sub-menu for environment and connectivity checks."""
    return [
        "all — doctor + live Figma check",
        "doctor — Figma token, Flutter SDK, project files",
        "live-check — verify Figma token and API fetch",
    ]


def _generate_menu_options() -> list[str]:
    """Sub-menu for single-screen vs batch codegen."""
    return [
        "batch — codegen all screens from screens.yaml",
        "one — codegen one Figma frame",
    ]


def _run_menu_options() -> list[str]:
    """Sub-menu for generate/assets/sync before Flutter launch."""
    return [
        "full — generate, sync assets, flutter run",
        "offline — generate from cache, flutter run (no live assets)",
    ]


def _resolve_run_prefer_live(
    *,
    prefer_offline: bool,
    has_token: bool,
) -> bool:
    """Map the run submenu choice to live Figma sync vs cached dump.

    ``full`` always prefers live sync when a token is configured; ``offline``
    always uses the cached dump. Extra confirm prompts are skipped because the
    submenu already captured the user's intent.

    Args:
        prefer_offline: True when the user picked the offline run submenu item.
        has_token: Whether ``FIGMA_ACCESS_TOKEN`` is configured.

    Returns:
        True to sync from live Figma; False to use the cached dump.
    """
    if prefer_offline:
        return False
    return has_token


def _print_wizard_header(ctx: typer.Context) -> None:
    state = _wizard_state(ctx)
    console.print("figma-flutter — interactive mode")
    if state.project_dir is not None:
        active = _wizard_active_screen_label(ctx)
        active_label = active if active is not None else "not set"
        console.print(f"Project: {state.project_dir.as_posix()}  Active screen: {active_label}")
    console.print("")


def run_main_wizard(ctx: typer.Context) -> None:
    """Top-level interactive menu when ``figma-flutter`` is invoked without a subcommand."""
    from figma_flutter_agent.errors import FigmaFlutterError, format_error_for_log

    _bootstrap_wizard_state(ctx)
    _print_wizard_header(ctx)
    while True:
        action = prompt_choice(
            "What would you like to do?",
            _wizard_menu_options(),
            default="run — generate, sync, and launch Flutter",
            quit_zero_last=True,
        )
        command = _menu_command(action)
        if command == "quit":
            raise typer.Exit(code=0)
        try:
            if command == "change":
                _wizard_change_project(ctx)
            elif command == "check":
                _wizard_check(ctx)
            elif command == "fetch":
                _wizard_fetch_from_figma(ctx)
            elif command == "list":
                _wizard_list_screens(ctx)
            elif command == "select":
                _wizard_select_active_screen(ctx)
            elif command == "generate":
                _wizard_generate_menu(ctx)
            elif command == "run":
                _wizard_run(ctx)
            elif command == "analyze":
                _wizard_flutter_analyze(ctx)
            elif command == "test":
                _wizard_agent_signoff(ctx)
            else:
                console.print(f"[yellow]Unknown action:[/yellow] {action}")
        except typer.Exit as exc:
            if exc.exit_code:
                console.print("[red]Action failed.[/red]")
            else:
                raise
        except FigmaFlutterError as exc:
            console.print(f"[red]Error:[/red] {format_error_for_log(exc)}")
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            console.print(f"[red]Error:[/red] {format_error_for_log(exc)}")
        console.print("")
        _print_wizard_header(ctx)


def _wizard_pick_flutter_device(*, flutter_sdk: str | None = None) -> str | None:
    """Prompt for a Flutter run target or return None for the default device."""
    from figma_flutter_agent.config import load_settings
    from figma_flutter_agent.dev.wizard import (
        default_flutter_device_option,
        device_id_from_choice,
        list_flutter_devices,
    )

    sdk = flutter_sdk or load_settings().flutter_sdk or None
    devices = list_flutter_devices(flutter_sdk=sdk)
    if not devices:
        console.print("[yellow]No flutter devices listed — Flutter will pick a default.[/yellow]")
        return None
    options = [f"{label} [{device_id}]" for device_id, label in devices]
    options.append("default — let Flutter choose")
    picked = prompt_choice(
        "Flutter device",
        options,
        default=default_flutter_device_option(devices) or options[0],
    )
    if picked.startswith("default"):
        return None
    return device_id_from_choice(picked)


def _wizard_resolve_screen(ctx: typer.Context, manifest: BatchManifest) -> str:
    """Return active screen or prompt to pick one."""
    active = _wizard_active_screen_label(ctx)
    options = {screen.feature for screen in manifest.screens}
    if (
        active is not None
        and active in options
        and prompt_confirm(f"Use active screen '{active}'?", default=True)
    ):
        return active
    return _wizard_pick_screen(ctx, manifest)


def _wizard_check(ctx: typer.Context) -> None:
    """Run doctor, live-check, or both based on submenu selection."""
    mode_label = prompt_choice(
        "Check mode",
        _check_menu_options(),
        default=_check_menu_options()[0],
    )
    mode = _menu_command(mode_label)
    failed = False
    if mode in {"all", "doctor"}:
        try:
            _wizard_doctor(ctx)
        except typer.Exit as exc:
            if exc.exit_code:
                failed = True
            else:
                raise
    if mode in {"all", "live-check"}:
        try:
            _wizard_live_check(ctx)
        except typer.Exit as exc:
            if exc.exit_code:
                failed = True
            else:
                raise
    if failed:
        raise typer.Exit(code=1)


def _wizard_generate_menu(ctx: typer.Context) -> None:
    """Run batch or single-screen codegen based on submenu selection."""
    mode_label = prompt_choice(
        "Generate mode",
        _generate_menu_options(),
        default=_generate_menu_options()[0],
    )
    if _menu_command(mode_label) == "batch":
        _wizard_batch_generate(ctx)
    else:
        _wizard_generate(ctx)


def _wizard_run(ctx: typer.Context) -> None:
    """Launch Flutter after optional generate/asset-sync submenu selection."""
    mode_label = prompt_choice(
        "Run pipeline",
        _run_menu_options(),
        default=_run_menu_options()[0],
    )
    prefer_offline = _menu_command(mode_label) == "offline"
    _wizard_sync_preview(ctx, prefer_offline=prefer_offline)


def _wizard_sync_preview(ctx: typer.Context, *, prefer_offline: bool = False) -> None:
    """Sync one screen from Figma (live when needed) and launch Flutter."""
    import asyncio

    from figma_flutter_agent.batch.manifest import load_batch_manifest
    from figma_flutter_agent.config import load_settings
    from figma_flutter_agent.dev.project import (
        ensure_project_config,
        resolve_manifest_path,
    )
    from figma_flutter_agent.dev.wizard import (
        build_run_plan,
        collect_screen_preflight,
        format_screen_preflight,
        sync_preview_workflow,
    )
    from figma_flutter_agent.generation.mode import (
        apply_generation_layout_mode,
        force_llm_regen_for_mode,
        generation_mode_run_label,
    )

    root = _wizard_project_dir(ctx)
    ensure_project_config(root)
    manifest = load_batch_manifest(resolve_manifest_path(root))
    screen = _wizard_resolve_screen(ctx, manifest)
    _persist_active_screen(ctx, screen)

    plan = build_run_plan(project_dir=root, screen_name=screen)
    preflight = collect_screen_preflight(plan)

    settings = load_settings(plan.config_path)
    has_token = bool(settings.figma_token().strip())
    prefer_live = _resolve_run_prefer_live(
        prefer_offline=prefer_offline,
        has_token=has_token,
    )
    full_selected = not prefer_offline

    if prefer_offline:
        console.print("[dim]Run mode:[/dim] offline — cached dump, no live asset sync")
    elif prefer_live:
        console.print("[dim]Run mode:[/dim] full — sync from live Figma")
    elif preflight.dump_exists:
        console.print("[dim]Run mode:[/dim] no FIGMA token — using cached dump")
    elif preflight.needs_live_sync:
        console.print(
            "[yellow]No FIGMA token and dump/assets missing — live sync unavailable.[/yellow]"
        )

    console.print(
        format_screen_preflight(
            preflight,
            prefer_live=prefer_live,
            prefer_offline=prefer_offline,
            full_selected=full_selected and not prefer_live,
        )
    )

    generation_mode = prompt_generation_layout_mode(settings)
    settings = apply_generation_layout_mode(settings, generation_mode)
    force_llm_regen = force_llm_regen_for_mode(generation_mode)
    console.print(f"[dim]Codegen:[/dim] {generation_mode_run_label(generation_mode)}")

    device_id = _wizard_pick_flutter_device(flutter_sdk=settings.flutter_sdk or None)
    device_label = device_id or "default device"
    console.print(f"[dim]Launching Flutter on {device_label} after sync…[/dim]")
    _, launched, pipeline_result = asyncio.run(
        sync_preview_workflow(
            project_dir=root,
            screen_name=screen,
            prefer_live=prefer_live,
            device_id=device_id,
            settings=settings,
            force_llm_regen=force_llm_regen,
        )
    )
    print_pipeline_warnings(pipeline_result.warnings)
    if launched is False:
        console.print(f"[yellow]Sync complete — Flutter run stopped.[/yellow] — {screen}")
    else:
        console.print(f"[green]Run complete[/green] — {screen}")


def _wizard_doctor(ctx: typer.Context) -> None:
    from figma_flutter_agent.config import load_settings
    from figma_flutter_agent.dev.wizard import (
        collect_doctor_report,
        format_doctor_report,
    )

    root = _wizard_project_dir(ctx)
    settings = load_settings()
    report = collect_doctor_report(project_dir=root, settings=settings)
    console.print(format_doctor_report(report))
    if not report.passed:
        raise typer.Exit(code=1)


def _wizard_flutter_analyze(ctx: typer.Context) -> None:
    from figma_flutter_agent.config import load_settings
    from figma_flutter_agent.dev.wizard import run_flutter_analyze

    root = _wizard_project_dir(ctx)
    settings = load_settings()
    run_flutter_analyze(root, flutter_sdk=settings.flutter_sdk or None)
    console.print("[green]flutter analyze passed[/green]")


def _wizard_agent_signoff(ctx: typer.Context) -> None:
    from figma_flutter_agent.dev.wizard import agent_repo_root, run_agent_signoff

    if not prompt_confirm(
        "Run offline test gates (demo-signoff + pytest)? This may take several minutes.",
        default=False,
    ):
        console.print("[yellow]Skipped.[/yellow]")
        return
    run_agent_signoff(agent_root=agent_repo_root())
    console.print("[green]Test gates passed[/green]")


def _wizard_change_project(ctx: typer.Context) -> None:
    from figma_flutter_agent.dev.project import (
        default_flutter_project_candidate,
        env_configured_project_dir,
    )

    state = _wizard_state(ctx)
    state.project_dir = prompt_project_dir(
        ctx,
        default_flutter_project_candidate(),
        env_project_dir=env_configured_project_dir(),
    )
    state.active_screen = _load_persisted_active_screen(state.project_dir)
    console.print(f"[green]Project set to[/green] {state.project_dir.as_posix()}")


def _wizard_project_dir(ctx: typer.Context) -> Path:
    from figma_flutter_agent.dev.project import (
        default_flutter_project_candidate,
        env_configured_project_dir,
    )

    state = _wizard_state(ctx)
    if state.project_dir is not None and (state.project_dir / "pubspec.yaml").is_file():
        return state.project_dir
    state.project_dir = prompt_project_dir(
        ctx,
        default_flutter_project_candidate(),
        env_project_dir=env_configured_project_dir(),
    )
    if state.active_screen is None:
        state.active_screen = _load_persisted_active_screen(state.project_dir)
    return state.project_dir


def _wizard_pick_screen(ctx: typer.Context, manifest: BatchManifest) -> str:
    """Show a numbered screen list and return the picked feature slug."""
    from figma_flutter_agent.batch.manifest import format_screen_list

    active = _wizard_active_screen_label(ctx)
    options = [screen.feature for screen in manifest.screens]
    if not options:
        msg = "No screens in screens.yaml"
        raise ValueError(msg)
    console.print(format_screen_list(manifest, active=active))
    default = active if active in options else options[0]
    picked = prompt_choice("Select active screen", options, default=default)
    _persist_active_screen(ctx, picked)
    return picked


def _wizard_select_active_screen(ctx: typer.Context) -> None:
    """Pick active screen from menu and wire ``main.dart``."""
    from figma_flutter_agent.batch.manifest import load_batch_manifest
    from figma_flutter_agent.dev.project import (
        ensure_project_config,
        resolve_manifest_path,
    )
    from figma_flutter_agent.dev.run import (
        detect_wired_screen_feature,
        wire_active_screen_blocking,
    )

    root = _wizard_project_dir(ctx)
    ensure_project_config(root)
    manifest = load_batch_manifest(resolve_manifest_path(root))
    screen = _wizard_pick_screen(ctx, manifest)
    regen = prompt_confirm("Regenerate Dart from dump and wire main.dart?", default=True)
    if regen:
        wire_active_screen_blocking(project_dir=root, screen_name=screen, allow_dev_profile=True)
        wired = detect_wired_screen_feature(root)
        if wired != screen:
            console.print("[yellow]Warning:[/yellow] could not verify main.dart wiring")
    else:
        console.print(
            "[yellow]Skipped codegen.[/yellow] Active screen saved to "
            ".figma-flutter/wizard-state.yml (wire main.dart before run if needed)."
        )
    console.print(f"[green]Active screen:[/green] {screen}")


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
    from figma_flutter_agent.generation.mode import (
        apply_generation_layout_mode,
        force_llm_regen_for_mode,
        generation_mode_run_label,
    )
    from figma_flutter_agent.pipeline import run_pipeline

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
    generation_mode = prompt_generation_layout_mode(settings)
    settings = apply_generation_layout_mode(settings, generation_mode)
    force_llm_regen = force_llm_regen_for_mode(generation_mode)
    console.print(f"[dim]Codegen:[/dim] {generation_mode_run_label(generation_mode)}")
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


def _import_manifest_menu_options() -> list[str]:
    """Sub-menu for merging or replacing ``screens.yaml`` during fetch."""
    return [
        "add — merge into existing screens.yaml",
        "overwrite — replace screens.yaml with this import",
    ]


def _list_menu_options() -> list[str]:
    """Sub-menu for manifest listing and screen removal."""
    return [
        "view — show manifest and preflight status",
        "delete — remove screens (comma-separated slugs)",
    ]


def _prompt_import_manifest_mode(manifest_path: Path) -> bool:
    """Return True when the import should merge into an existing manifest."""
    if not manifest_path.is_file():
        return True
    from figma_flutter_agent.batch.manifest import load_batch_manifest

    manifest = load_batch_manifest(manifest_path)
    if not manifest.screens:
        return True
    mode_label = prompt_choice(
        "Import into screens.yaml",
        _import_manifest_menu_options(),
        default=_import_manifest_menu_options()[0],
    )
    return _menu_command(mode_label) == "add"


def _file_fetch_menu_options() -> list[str]:
    """Sub-menu for full-file fetch scope in the interactive wizard."""
    return [
        "quick — JSON + SVG + PNG, rewrite all",
        "advanced — choose scope and write policy",
    ]


def _wizard_fetch_from_figma(ctx: typer.Context, *, parsed: ParsedFigmaInput | None = None) -> None:
    """Import one frame or dump a full Figma file based on pasted URL."""
    from figma_flutter_agent.dev.project import ensure_project_config
    from figma_flutter_agent.figma.url import FigmaUrlKind

    root = _wizard_project_dir(ctx)
    ensure_project_config(root)
    if parsed is None:
        parsed = prompt_figma_input(ctx=ctx, project_dir=root)

    if parsed.kind == FigmaUrlKind.FRAME:
        _wizard_import_figma_frame(ctx, parsed, project_dir=root)
        return

    mode_label = prompt_choice(
        "File download mode",
        _file_fetch_menu_options(),
        default=_file_fetch_menu_options()[0],
    )
    advanced = mode_label.startswith("advanced")
    _wizard_dump_figma_file(ctx, parsed, project_dir=root, advanced=advanced)


def _wizard_import_figma_frame(
    ctx: typer.Context,
    parsed: ParsedFigmaInput,
    *,
    project_dir: Path,
) -> None:
    """Import one frame, update the manifest, and optionally preview it."""
    import asyncio

    from figma_flutter_agent.config import load_settings
    from figma_flutter_agent.dev.import_figma import import_figma_frame
    from figma_flutter_agent.dev.project import resolve_manifest_path
    from figma_flutter_agent.dev.run import wire_active_screen_blocking
    from figma_flutter_agent.dev.wizard import sync_preview_workflow
    from figma_flutter_agent.figma.connector import FigmaConnector

    settings = load_settings()
    token = settings.figma_token().strip()
    if not token:
        console.print("[red]FIGMA_ACCESS_TOKEN is not set[/red]")
        raise typer.Exit(code=1)

    manifest_path = resolve_manifest_path(project_dir)
    merge = _prompt_import_manifest_mode(manifest_path)

    async def _run_import() -> tuple[str, Path]:
        async with FigmaConnector(token, settings.figma_api_base_url) as connector:
            return await import_figma_frame(
                connector,
                parsed,
                project_dir=project_dir,
                manifest_path=manifest_path,
                merge=merge,
            )

    feature, dump_path = asyncio.run(_run_import())
    console.print(
        f"[green]Imported frame[/green] {feature} ({parsed.node_id}) → {dump_path.as_posix()}"
    )
    _persist_active_screen(ctx, feature)
    if prompt_confirm("Generate and preview this screen now (live sync)?", default=True):
        device_id = _wizard_pick_flutter_device()
        _, launched, pipeline_result = asyncio.run(
            sync_preview_workflow(
                project_dir=project_dir,
                screen_name=feature,
                prefer_live=True,
                device_id=device_id,
            )
        )
        print_pipeline_warnings(pipeline_result.warnings)
        if launched is False:
            console.print(f"[yellow]Sync complete — Flutter run stopped.[/yellow] — {feature}")
        else:
            console.print(f"[green]Sync & preview complete[/green] — {feature}")
    elif prompt_confirm("Wire main.dart to this screen?", default=True):
        wire_active_screen_blocking(
            project_dir=project_dir, screen_name=feature, allow_dev_profile=True
        )
        console.print(f"[green]Active screen wired:[/green] {feature}")


def _wizard_dump_figma_file(
    ctx: typer.Context,
    parsed: ParsedFigmaInput,
    *,
    project_dir: Path,
    advanced: bool,
) -> None:
    """Dump a full Figma file with quick defaults or advanced scope/policy."""
    import asyncio

    from figma_flutter_agent.batch.dump_mode import (
        BatchDumpMode,
        DumpWritePolicy,
        assets_attempted,
        batch_dump_menu_options,
        batch_dump_mode_from_menu,
        default_write_policy,
        plan_for_mode,
        write_policy_from_menu,
        write_policy_menu_options,
    )
    from figma_flutter_agent.batch.file_dump import dump_full_figma_file
    from figma_flutter_agent.batch.screen_report import (
        print_screen_download_report,
        screen_download_all_ok,
    )
    from figma_flutter_agent.config import load_settings
    from figma_flutter_agent.dev.project import resolve_manifest_path
    from figma_flutter_agent.figma.connector import FigmaConnector

    if advanced:
        mode_label = prompt_choice(
            "Batch download scope",
            batch_dump_menu_options(),
            default=batch_dump_menu_options()[0],
        )
        dump_mode = batch_dump_mode_from_menu(mode_label)
        dump_plan = plan_for_mode(dump_mode)
        if dump_plan.write_json or assets_attempted(dump_plan):
            policy_label = prompt_choice(
                "Write policy",
                write_policy_menu_options(),
                default=(
                    write_policy_menu_options()[0]
                    if default_write_policy(dump_mode) is DumpWritePolicy.SKIP_EXISTING
                    else write_policy_menu_options()[1]
                ),
            )
            write_policy = write_policy_from_menu(policy_label)
        else:
            write_policy = DumpWritePolicy.REWRITE
    else:
        dump_mode = BatchDumpMode.ALL
        write_policy = DumpWritePolicy.REWRITE
        dump_plan = plan_for_mode(dump_mode)

    settings = load_settings()
    token = settings.figma_token().strip()
    if not token:
        console.print("[red]FIGMA_ACCESS_TOKEN is not set[/red]")
        raise typer.Exit(code=1)

    manifest_path = resolve_manifest_path(project_dir)
    manifest_merge = _prompt_import_manifest_mode(manifest_path)

    async def _run() -> object:
        async with FigmaConnector(token, settings.figma_api_base_url) as connector:
            return await dump_full_figma_file(
                connector,
                file_key=parsed.file_key,
                project_dir=project_dir,
                manifest_path=manifest_path,
                mode=dump_mode,
                write_policy=write_policy,
                assets=settings.agent.assets,
                manifest_merge=manifest_merge,
            )

    result = asyncio.run(_run())
    assets_exported = assets_attempted(dump_plan)
    console.print(
        f"[green]Fetched file[/green] mode={dump_mode.value}, {len(result.screens)} screens, "
        f"{result.icon_count} SVG, {result.raster_count} raster"
    )
    print_screen_download_report(
        console,
        result.screen_reports,
        with_assets=assets_exported,
        orphan_exportables=result.orphan_exportables,
        rate_limited=result.rate_limited,
    )
    if not screen_download_all_ok(result.screen_reports, with_assets=assets_exported):
        raise typer.Exit(code=1)


def _wizard_batch_generate(ctx: typer.Context) -> None:
    import asyncio

    from figma_flutter_agent.batch.manifest import load_batch_manifest
    from figma_flutter_agent.batch.run import run_batch_generate
    from figma_flutter_agent.config import load_settings
    from figma_flutter_agent.dev.project import ensure_project_config
    from figma_flutter_agent.generation.mode import (
        apply_generation_layout_mode,
        force_llm_regen_for_mode,
    )

    root = _wizard_project_dir(ctx)
    config_path = ensure_project_config(root)
    manifest_path = prompt_manifest_path(ctx, root)
    manifest = load_batch_manifest(manifest_path)
    settings = load_settings(config_path)
    generation_mode = prompt_generation_layout_mode(settings)
    settings = apply_generation_layout_mode(settings, generation_mode)
    force_llm_regen = force_llm_regen_for_mode(generation_mode)
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


def _wizard_list_screens(ctx: typer.Context) -> None:
    mode_label = prompt_choice(
        "List mode",
        _list_menu_options(),
        default=_list_menu_options()[0],
    )
    if _menu_command(mode_label) == "delete":
        _wizard_delete_screens(ctx)
    else:
        _wizard_list_screens_view(ctx)


def _wizard_list_screens_view(ctx: typer.Context) -> None:
    from figma_flutter_agent.batch.manifest import (
        format_screen_list,
        load_batch_manifest,
    )
    from figma_flutter_agent.dev.project import resolve_manifest_path
    from figma_flutter_agent.dev.wizard import (
        build_run_plan,
        collect_screen_preflight,
        format_screen_preflight,
    )

    root = _wizard_project_dir(ctx)
    manifest = load_batch_manifest(resolve_manifest_path(root))
    active = _wizard_active_screen_label(ctx)
    console.print(format_screen_list(manifest, active=active))
    if active is not None:
        try:
            plan = build_run_plan(project_dir=root, screen_name=active)
            console.print("")
            console.print(format_screen_preflight(collect_screen_preflight(plan)))
        except (FileNotFoundError, ValueError):
            pass
    if prompt_confirm("Select a different active screen?", default=False):
        _wizard_select_active_screen(ctx)


def _wizard_delete_screens(ctx: typer.Context) -> None:
    from figma_flutter_agent.batch.manifest import (
        format_screen_list,
        load_batch_manifest,
        remove_screens_from_manifest,
    )
    from figma_flutter_agent.dev.project import resolve_manifest_path

    root = _wizard_project_dir(ctx)
    manifest_path = resolve_manifest_path(root)
    manifest = load_batch_manifest(manifest_path)
    active = _wizard_active_screen_label(ctx)
    console.print(format_screen_list(manifest, active=active))
    raw = prompt_text("Slugs to delete (comma-separated)", default="").strip()
    if not raw:
        console.print("[yellow]Nothing to delete.[/yellow]")
        return
    names = [part.strip() for part in raw.split(",") if part.strip()]
    try:
        updated, removed = remove_screens_from_manifest(manifest_path, names)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        return
    state = _wizard_state(ctx)
    if state.active_screen in removed:
        _persist_active_screen(ctx, None)
    console.print(
        f"[green]Removed {len(removed)} screen(s):[/green] {', '.join(removed)} "
        f"({len(updated.screens)} remaining)"
    )


def _wizard_live_check(ctx: typer.Context) -> None:
    import asyncio

    from figma_flutter_agent.config import load_settings
    from figma_flutter_agent.figma.connector import FigmaConnector
    from figma_flutter_agent.figma.url import FigmaUrlKind
    from figma_flutter_agent.stages.fetch import fetch_figma_frame

    configure_logging = __import__(
        "figma_flutter_agent.logging_setup",
        fromlist=["configure_logging"],
    ).configure_logging
    configure_logging(verbose=False)
    settings = load_settings()
    token = settings.figma_token().strip()
    if not token:
        console.print("[red]FIGMA_ACCESS_TOKEN is not set[/red]")
        raise typer.Exit(code=1)
    console.print("[green]FIGMA_ACCESS_TOKEN[/green] present")
    project_dir = _wizard_project_dir(ctx)
    parsed = prompt_figma_input(
        ctx=ctx,
        project_dir=project_dir,
        expect_kind=FigmaUrlKind.FRAME,
        optional=True,
    )
    dump = prompt_confirm("Write raw dump to .figma_debug?", default=False)
    if parsed is None:
        console.print(
            "[yellow]No frame URL — configure screens.yaml, FIGMA_DEFAULT_URL, "
            "or FIGMA_SMOKE_* to smoke-test fetch.[/yellow]"
        )
        raise typer.Exit(code=0)
    file_key = parsed.file_key
    node_id = parsed.node_id or ""

    async def _run_fetch() -> None:
        async with FigmaConnector(token, settings.figma_api_base_url) as connector:
            result = await fetch_figma_frame(
                connector,
                file_key=file_key,
                node_id=node_id,
                project_dir=project_dir,
                verbose=dump,
            )
        console.print(
            f"[green]Live fetch OK[/green] frame={result.root.get('name')!r} "
            f"links={len(result.prototype_links)}"
        )

    asyncio.run(_run_fetch())
