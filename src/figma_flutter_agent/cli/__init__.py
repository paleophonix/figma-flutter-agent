"""Typer CLI entrypoint — assembles the figma-flutter command."""

from __future__ import annotations

import typer

from figma_flutter_agent.errors import FigmaFlutterError
from figma_flutter_agent.logging_setup import configure_logging
from figma_flutter_agent.wizard import (
    CliSession,
    run_main_wizard,
    tty_interactive_default,
)

from .helpers import _exit_domain_error, console
from .batch import app as _batch_app
from .live import visual_qa_app as _visual_qa_app
from .generate import generate, import_tokens_command, run_screen_command
from .fixtures import (
    fixture_geometry_check_command,
    fixture_golden_check_command,
    fixture_ir_validate_command,
    profile_refine_ready_command,
    validate_spec23_command,
)
from .live import (
    demo_signoff_command,
    doctor_command,
    live_check_command,
    version,
)

app = typer.Typer(add_completion=False, no_args_is_help=False, invoke_without_command=True)

# ── sub-apps ──────────────────────────────────────────────────────────────────
app.add_typer(_batch_app, name="batch")
app.add_typer(_visual_qa_app, name="visual-qa")

# ── generation ────────────────────────────────────────────────────────────────
app.command("generate")(generate)
app.command("run")(run_screen_command)
app.command("import-tokens")(import_tokens_command)

# ── fixtures / dev ────────────────────────────────────────────────────────────
app.command("fixture-ir-validate")(fixture_ir_validate_command)
app.command("fixture-golden-check")(fixture_golden_check_command)
app.command("fixture-geometry-check")(fixture_geometry_check_command)
app.command("profile-refine-ready")(profile_refine_ready_command)
app.command("validate-spec23")(validate_spec23_command)

# ── live / demo ───────────────────────────────────────────────────────────────
app.command("doctor")(doctor_command)
app.command("version")(version)
app.command("live-check")(live_check_command)
app.command("demo-signoff")(demo_signoff_command)


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


__all__ = ["app", "main"]
