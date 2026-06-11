"""Write synthetic layout JSON fixtures for the audit corpus."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.audit.predicate_matrix import PATTERN_FIXTURES
from figma_flutter_agent.fixtures.screens_manifest import fixtures_root
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing, SizingMode

_FIXTURE_NAMES: dict[str, str] = {
    "consent_checkbox_row": "consent_checkbox_row.json",
    "spaceBetween_plain_stacks": "flex_summary_row.json",
    "prefilled_flex_input": "prefilled_input_field.json",
}


def _screen_shell(feature: str, child: CleanDesignTreeNode) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=f"{feature}:root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(
            width_mode=SizingMode.FIXED,
            width=390.0,
            height_mode=SizingMode.FIXED,
            height=844.0,
        ),
        children=[child],
    )


def write_synthetic_layout_fixtures(
    layouts_dir: Path | None = None,
) -> list[Path]:
    """Persist minimal clean-tree fixtures used by diff-triada and screens.yaml.

    Args:
        layouts_dir: Target directory; defaults to ``tests/fixtures/layouts``.

    Returns:
        Paths of files written or updated.
    """
    root = layouts_dir or fixtures_root() / "layouts"
    root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for pattern in PATTERN_FIXTURES:
        filename = _FIXTURE_NAMES.get(pattern.pattern_id)
        if filename is None:
            continue
        feature = filename.removesuffix("_layout.json").removesuffix(".json")
        tree = _screen_shell(feature, pattern.node)
        path = root / filename
        payload = json.loads(tree.model_dump_json(by_alias=True))
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written.append(path)
    return written
