"""Typer CLI for defect corpus operations."""

from __future__ import annotations

import sys

import typer

from figma_flutter_agent.defects.validation import validate_corpus

defects_app = typer.Typer(add_completion=False, no_args_is_help=True)


@defects_app.command("validate")
def validate_command() -> None:
    """Validate ``corpus/`` families and cases."""
    errors = validate_corpus()
    if not errors:
        typer.echo("defect corpus: valid")
        raise typer.Exit(code=0)
    for error in errors:
        typer.echo(error.format())
    raise typer.Exit(code=1)


def main() -> None:
    """Entry point when invoked as a module."""
    defects_app()


if __name__ == "__main__":
    main()
    sys.exit(0)
