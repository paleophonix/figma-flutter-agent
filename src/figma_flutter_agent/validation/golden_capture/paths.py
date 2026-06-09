"""Path helpers and asset utilities for golden capture."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from loguru import logger

from figma_flutter_agent.fixtures.assets import iter_layout_asset_keys
from figma_flutter_agent.schemas import CleanDesignTreeNode

_PLANNED_ASSET_PATH_RE = re.compile(r"""['"](assets/[^'"]+)['"]""")


def golden_test_relative_path(feature_name: str) -> str:
    """Return the relative golden test path for a feature screen."""
    return f"test/golden/{feature_name}_screen_test.dart"


def capture_test_relative_path(feature_name: str) -> str:
    """Return the lightweight visual-refine capture test path."""
    return f"test/capture/{feature_name}_screen_capture_test.dart"


def golden_png_relative_path(feature_name: str) -> str:
    """Return the relative golden PNG path for a feature screen."""
    return f"test/goldens/{feature_name}_screen.png"


def golden_figma_keys_relative_path(feature_name: str) -> str:
    """Return the relative JSON path for runtime ``figma-*`` widget bounds."""
    return f"test/goldens/{feature_name}_figma_keys.json"


def collect_planned_asset_paths(
    planned: Mapping[str, str],
    layout_tree: CleanDesignTreeNode | None = None,
) -> set[str]:
    """Collect asset paths referenced by planned Dart and the layout tree."""
    paths: set[str] = set()
    for content in planned.values():
        for match in _PLANNED_ASSET_PATH_RE.finditer(content):
            paths.add(match.group(1).replace("\\", "/"))
    if layout_tree is not None:
        paths.update(iter_layout_asset_keys(layout_tree))
    return paths


def _read_figma_key_rects(capture_dir: Path, feature_name: str) -> dict[str, Any] | None:
    keys_path = capture_dir / golden_figma_keys_relative_path(feature_name)
    if not keys_path.is_file():
        return None
    raw = keys_path.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning(
            "Golden capture: invalid {} ({})",
            keys_path.name,
            exc,
        )
        return None
    if not isinstance(payload, dict):
        return None
    return payload
