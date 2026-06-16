"""Write responsiveness diagnostic reports to the debug bundle."""

from __future__ import annotations

import json
from pathlib import Path

from loguru import logger

from figma_flutter_agent.debug.paths import screen_root
from figma_flutter_agent.generator.checks.layout import build_responsiveness_report
from figma_flutter_agent.schemas import CleanDesignTreeNode

_REPORT_FILENAME = "responsiveness_report.json"


def write_responsiveness_report(
    *,
    feature_name: str,
    clean_tree: CleanDesignTreeNode,
    project_dir: Path | None,
    responsive_enabled: bool = True,
) -> Path | None:
    """Persist ``responsiveness_report.json`` beside other screen debug artifacts.

    Args:
        feature_name: Active feature slug.
        clean_tree: Emit clean tree after layout passes.
        project_dir: Flutter project directory for debug bundle routing.

    Returns:
        Written file path, or ``None`` when ``project_dir`` is unset.
    """
    if project_dir is None:
        return None
    report = build_responsiveness_report(
        clean_tree,
        responsive_enabled=responsive_enabled,
    )
    bundle_dir = screen_root(project_dir, feature_name)
    bundle_dir.mkdir(parents=True, exist_ok=True)
    target = bundle_dir / _REPORT_FILENAME
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.bind(feature=feature_name, tier=report.get("tier")).debug(
        "Wrote responsiveness report to {}",
        target,
    )
    return target
