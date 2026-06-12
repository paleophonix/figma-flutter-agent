"""Persist screen IR JSON snapshots for offline debugging."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from loguru import logger

from figma_flutter_agent.debug.paths import screen_ir_dump_path
from figma_flutter_agent.render_log import render_artifacts_dir
from figma_flutter_agent.schemas import ExtractedWidget, ScreenIr

_STAGE_SAFE_RE = re.compile(r"[^\w.-]+")


def _safe_stage(stage: str) -> str:
    return _STAGE_SAFE_RE.sub("_", stage.strip()).strip("_") or "snapshot"


def _screen_ir_payload(
    *,
    stage: str,
    feature_name: str,
    screen_ir: ScreenIr,
    extracted_widgets: list[ExtractedWidget] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "stage": stage,
        "featureName": feature_name,
        "screenIr": screen_ir.model_dump(by_alias=True, exclude_none=True),
    }
    if extracted_widgets:
        payload["extractedWidgets"] = [
            widget.model_dump(by_alias=True, exclude_none=True) for widget in extracted_widgets
        ]
    if extra:
        payload.update(extra)
    if stage == "pre_emit":
        from figma_flutter_agent.generator.ir.version import EMITTER_VERSION

        payload["emitterVersion"] = EMITTER_VERSION
    return payload


def write_screen_ir_snapshot(
    *,
    stage: str,
    feature_name: str,
    screen_ir: ScreenIr,
    project_dir: Path | None = None,
    extracted_widgets: list[ExtractedWidget] | None = None,
    extra: dict[str, Any] | None = None,
) -> list[Path]:
    """Write screen IR to the Flutter project and/or the bound render-log session.

    Args:
        stage: Short slug (for example ``llm_validated``, ``pre_emit``, ``repair_02``).
        feature_name: Resolved screen feature slug.
        screen_ir: Screen IR to persist.
        project_dir: When set, writes ``.debug/ir/<feature>_<stage>.json``.
        extracted_widgets: Optional extracted widget IR bundled in the dump.
        extra: Optional metadata merged into the JSON root.

    Returns:
        Paths written (empty when ``screen_ir`` would not be serialized).
    """
    payload = _screen_ir_payload(
        stage=stage,
        feature_name=feature_name,
        screen_ir=screen_ir,
        extracted_widgets=extracted_widgets,
        extra=extra,
    )
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    written: list[Path] = []

    if project_dir is not None:
        path = screen_ir_dump_path(project_dir, feature_name, stage)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        written.append(path)
        logger.info("Saved screen IR dump ({}) to {}", stage, path.as_posix())
    elif (render_dir := render_artifacts_dir()) is not None:
        path = render_dir / "ir" / f"{_safe_stage(stage)}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        written.append(path)
        logger.debug("Saved screen IR dump ({}) to {}", stage, path.as_posix())

    return written
