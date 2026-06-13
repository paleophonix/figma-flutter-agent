"""Classification report dumps under ``.debug/<feature>/primary/``."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.debug.paths import semantics_report_path
from figma_flutter_agent.parser.semantics.report import SemanticClassificationReport


def write_classification_report(
    feature_name: str,
    report: SemanticClassificationReport,
    *,
    project_dir: Path | None = None,
) -> Path | None:
    """Write classification report JSON under ``<project>/.debug/<feature>/primary/``.

    Args:
        feature_name: Screen feature slug.
        report: Classification report payload.
        project_dir: Flutter project root; when omitted, the report is not written.

    Returns:
        Written path, or ``None`` when ``project_dir`` is unset.
    """
    if project_dir is None:
        return None
    path = semantics_report_path(project_dir, feature_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    return path
