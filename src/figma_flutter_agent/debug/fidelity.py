"""Fidelity shadow report dumps under ``.figma_debug/fidelity/``."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.debug.paths import FIGMA_DEBUG_DIR
from figma_flutter_agent.generator.ir.fidelity.report import FidelityShadowReport

FIDELITY_DIR = "fidelity"


def fidelity_report_path(feature_name: str) -> Path:
    """Return the per-feature fidelity shadow report path."""
    safe = feature_name.replace("/", "_").strip() or "screen"
    return Path(FIGMA_DEBUG_DIR) / FIDELITY_DIR / f"{safe}.json"


def write_fidelity_shadow_report(
    feature_name: str,
    report: FidelityShadowReport,
    *,
    project_dir: Path | None = None,
) -> Path:
    """Write fidelity shadow report JSON and return the file path."""
    path = fidelity_report_path(feature_name)
    if project_dir is not None:
        path = project_dir / ".figma_debug" / FIDELITY_DIR / f"{feature_name.replace('/', '_')}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    return path
