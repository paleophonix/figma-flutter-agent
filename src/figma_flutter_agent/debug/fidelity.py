"""Fidelity shadow report dumps under ``.debug/<feature>/secondary/``."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.debug.paths import fidelity_report_path
from figma_flutter_agent.generator.ir.fidelity.report import FidelityShadowReport


def write_fidelity_shadow_report(
    feature_name: str,
    report: FidelityShadowReport,
    *,
    project_dir: Path | None = None,
) -> Path | None:
    """Write fidelity shadow report JSON under ``<project>/.debug/<feature>/secondary/``.

    Returns:
        Written path, or ``None`` when ``project_dir`` is unset.
    """
    if project_dir is None:
        return None
    path = fidelity_report_path(project_dir, feature_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    return path
