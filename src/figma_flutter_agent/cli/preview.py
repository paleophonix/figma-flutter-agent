"""CLI commands for fast browser preview capture."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from figma_flutter_agent.cli.helpers import _exit_domain_error, console
from figma_flutter_agent.errors import FastPreviewUnavailableError, FigmaFlutterError
from figma_flutter_agent.preview import (
    PreviewCaptureRequest,
    capture_preview_png,
    preview_scene_from_clean_tree,
)
from figma_flutter_agent.schemas.tree import CleanDesignTreeNode

preview_app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Fast browser preview capture (non-oracle).",
)


def preview_capture_command(
    layout_json: Path | None = typer.Option(
        None,
        "--layout-json",
        help="Path to a clean design tree JSON layout fixture",
    ),
    screen: str | None = typer.Option(
        None,
        "--screen",
        help="Manifest screen id (loads tests/fixtures layout)",
    ),
    out: Path = typer.Option(
        Path(".debug/renders/preview.png"),
        "--out",
        help="Output PNG path",
    ),
    timeout: float = typer.Option(
        5.0,
        "--timeout",
        min=1.0,
        help="Browser wait timeout in seconds",
    ),
    device_scale_factor: float = typer.Option(
        1.0,
        "--device-scale-factor",
        min=0.5,
        max=4.0,
        help="Device scale factor for Playwright capture",
    ),
) -> None:
    """Capture a fast browser preview PNG without Flutter test tooling."""
    try:
        tree, screen_id = _resolve_preview_tree(layout_json=layout_json, screen=screen)
        scene = preview_scene_from_clean_tree(tree)
        result = capture_preview_png(
            PreviewCaptureRequest(
                scene=scene,
                output_path=out,
                timeout_sec=timeout,
                device_scale_factor=device_scale_factor,
                screen_id=screen_id,
            ),
        )
    except FastPreviewUnavailableError as exc:
        console.print(f"[red]FastPreviewUnavailableError:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    except FigmaFlutterError as exc:
        _exit_domain_error(exc)
        raise
    except Exception as exc:
        console.print(f"[red]Preview capture failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if not result.ok or result.png is None:
        reason = result.reason or "preview capture failed"
        console.print(f"[red]{reason}[/red]")
        raise typer.Exit(code=1)

    elapsed = result.elapsed_sec or 0.0
    console.print(
        f"[green]Preview capture OK[/green] backend={result.backend} "
        f"nodes={len(scene.nodes)} elapsed={elapsed:.2f}s → {out.as_posix()}"
    )


def _resolve_preview_tree(
    *,
    layout_json: Path | None,
    screen: str | None,
) -> tuple[CleanDesignTreeNode, str | None]:
    if layout_json is not None and screen is not None:
        msg = "Use either --layout-json or --screen, not both"
        raise typer.BadParameter(msg)
    if layout_json is not None:
        if not layout_json.is_file():
            msg = f"Layout JSON not found: {layout_json.as_posix()}"
            raise typer.BadParameter(msg)
        payload = json.loads(layout_json.read_text(encoding="utf-8"))
        return CleanDesignTreeNode.model_validate(payload), layout_json.stem
    if screen is not None:
        from figma_flutter_agent.fixtures.screens_manifest import load_layout_tree

        return load_layout_tree(screen), screen
    msg = "Provide --layout-json or --screen"
    raise typer.BadParameter(msg)
