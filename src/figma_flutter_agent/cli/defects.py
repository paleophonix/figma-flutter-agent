"""Typer CLI for defect corpus operations."""

from __future__ import annotations

import sys

import typer

from figma_flutter_agent.defects.index import check_family_indexes, write_family_indexes
from figma_flutter_agent.defects.validation import validate_corpus

defects_app = typer.Typer(add_completion=False, no_args_is_help=True)


@defects_app.command("validate")
def validate_command() -> None:
    """Validate ``corpus/`` families and cases."""
    errors = validate_corpus()
    index_errors = check_family_indexes()
    if not errors and not index_errors:
        typer.echo("defect corpus: valid")
        raise typer.Exit(code=0)
    for error in errors:
        typer.echo(error.format())
    for message in index_errors:
        typer.echo(message)
    raise typer.Exit(code=1)


@defects_app.command("index")
def index_command(
    write: bool = typer.Option(
        False,
        "--write",
        help="Regenerate corpus/index/<family_id>.yaml from cases/",
    ),
    check: bool = typer.Option(
        False,
        "--check",
        help="Fail when index files are missing or out of date",
    ),
) -> None:
    """Build or verify per-family case indexes under ``corpus/index/``."""
    if write:
        paths = write_family_indexes()
        typer.echo(f"defect index: wrote {len(paths)} file(s)")
        raise typer.Exit(code=0)

    if check or not write:
        errors = check_family_indexes()
        if not errors:
            typer.echo("defect index: up to date")
            raise typer.Exit(code=0)
        for message in errors:
            typer.echo(message)
        raise typer.Exit(code=1)


def main() -> None:
    """Entry point when invoked as a module."""
    defects_app()


if __name__ == "__main__":
    main()
    sys.exit(0)
