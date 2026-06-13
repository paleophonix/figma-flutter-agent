"""Load cached screen IR snapshots for offline plan/emit."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.debug.paths import (
    resolve_screen_ir_dump_file,
    screen_ir_dump_path,
)
from figma_flutter_agent.errors import FlutterProjectError
from figma_flutter_agent.schemas import ExtractedWidget, FlutterGenerationResponse, ScreenIr

_IR_STAGE_FALLBACK = ("llm_validated", "llm_parsed")


def resolve_screen_ir_dump_path(
    project_dir: Path,
    feature_name: str,
    *,
    explicit_path: Path | None = None,
) -> Path:
    """Resolve a screen IR JSON file under ``.debug/ir``.

    Args:
        project_dir: Flutter project root.
        feature_name: Screen feature slug (e.g. ``background``).
        explicit_path: Optional file or directory override from ``--from-ir-path``.

    Returns:
        Path to an existing IR dump JSON file.

    Raises:
        FlutterProjectError: When no matching IR snapshot exists.
    """
    if explicit_path is not None:
        candidate = explicit_path.expanduser().resolve()
        if candidate.is_file():
            return candidate
        if candidate.is_dir():
            for stage in _IR_STAGE_FALLBACK:
                path = candidate / f"{feature_name}_{stage}.json"
                if path.is_file():
                    return path
            msg = (
                f"No IR dump for feature {feature_name!r} under {candidate.as_posix()} "
                f"(expected {feature_name}_llm_validated.json or {feature_name}_llm_parsed.json)."
            )
            raise FlutterProjectError(msg)
        raise FlutterProjectError(f"IR dump path not found: {candidate.as_posix()}")

    for stage in _IR_STAGE_FALLBACK:
        path = resolve_screen_ir_dump_file(project_dir, feature_name, stage)
        if path is not None:
            return path

    ir_hint = screen_ir_dump_path(project_dir, feature_name, "llm_validated").parent.as_posix()
    raise FlutterProjectError(
        "No cached screen IR for "
        f"{feature_name!r} under {ir_hint}. "
        f"Run a full LLM generate first, or pass --from-ir-path."
    )


def load_generation_from_ir_dump(path: Path) -> FlutterGenerationResponse:
    """Build ``FlutterGenerationResponse`` from a ``write_screen_ir_snapshot`` JSON file.

    Args:
        path: IR dump containing ``screenIr`` and optional ``extractedWidgets``.

    Returns:
        Generation payload for the planner / IR emitter.

    Raises:
        FlutterProjectError: When the file is missing or malformed.
    """
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise FlutterProjectError(f"Screen IR dump not found: {resolved.as_posix()}")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FlutterProjectError(
            f"Could not read screen IR dump {resolved.as_posix()}: {exc}"
        ) from exc
    if not isinstance(payload, dict) or "screenIr" not in payload:
        raise FlutterProjectError(
            f"Invalid screen IR dump at {resolved.as_posix()}: missing screenIr root field."
        )
    try:
        screen_ir = ScreenIr.model_validate(payload["screenIr"])
        extracted = [
            ExtractedWidget.model_validate(widget)
            for widget in payload.get("extractedWidgets", [])
        ]
    except ValueError as exc:
        raise FlutterProjectError(
            f"Invalid screen IR schema in {resolved.as_posix()}: {exc}"
        ) from exc
    return FlutterGenerationResponse(
        screen_ir=screen_ir,
        extracted_widgets=extracted,
    )
