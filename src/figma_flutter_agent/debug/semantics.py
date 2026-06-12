"""Classification report dumps under ``.debug/semantics/``."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.debug.paths import FIGMA_DEBUG_DIR
from figma_flutter_agent.parser.semantics.report import SemanticClassificationReport

SEMANTICS_DIR = "semantics"


def semantics_report_path(feature_name: str) -> Path:
    """Return the per-feature classification report path."""
    safe = feature_name.replace("/", "_").strip() or "screen"
    return Path(FIGMA_DEBUG_DIR) / SEMANTICS_DIR / f"{safe}.json"


def write_classification_report(
    feature_name: str,
    report: SemanticClassificationReport,
    *,
    project_dir: Path | None = None,
) -> Path | None:
    """Write classification report JSON under ``<project>/.debug/semantics/``.

    Args:
        feature_name: Screen feature slug.
        report: Classification report payload.
        project_dir: Flutter project root; when omitted, the report is not written.

    Returns:
        Written path, or ``None`` when ``project_dir`` is unset.
    """
    if project_dir is None:
        return None
    safe = feature_name.replace("/", "_").strip() or "screen"
    path = project_dir / FIGMA_DEBUG_DIR / SEMANTICS_DIR / f"{safe}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    return path
