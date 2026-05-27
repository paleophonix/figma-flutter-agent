"""Pipeline accessibility gate ordering (strict contrast before auto-fix)."""

from __future__ import annotations

from pathlib import Path

import pytest

from figma_flutter_agent.config import Settings
from figma_flutter_agent.errors import FlutterProjectError
from figma_flutter_agent.figma.url import ParsedFigmaUrl
from figma_flutter_agent.pipeline_context import PipelineContext
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeStyle, NodeType


def _low_contrast_tree() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="1:1",
        name="Screen",
        type=NodeType.COLUMN,
        style=NodeStyle(background_color="0xFFFFFFFF"),
        children=[
            CleanDesignTreeNode(
                id="1:2",
                name="Muted label",
                type=NodeType.TEXT,
                text="Hello",
                style=NodeStyle(text_color="0xFFCCCCCC", font_size=14),
            )
        ],
    )


def _context(*, auto_fix: bool, strict_contrast: bool) -> PipelineContext:
    settings = Settings()
    settings = settings.model_copy(
        update={
            "agent": settings.agent.model_copy(
                update={
                    "accessibility": settings.agent.accessibility.model_copy(
                        update={"auto_fix": auto_fix}
                    ),
                    "quality": settings.agent.quality.model_copy(
                        update={"strict_contrast": strict_contrast}
                    ),
                }
            )
        }
    )
    ctx = PipelineContext(
        settings=settings,
        project_dir=Path("."),
        parsed=ParsedFigmaUrl(file_key="abc", node_id="1:1"),
        dry_run=False,
        verbose=False,
        resolved_sync=False,
        feature_name=None,
        regenerate_templates=False,
    )
    ctx.clean_tree = _low_contrast_tree()
    return ctx


def test_strict_contrast_fails_before_auto_fix_even_when_auto_fix_enabled() -> None:
    ctx = _context(auto_fix=True, strict_contrast=True)
    with pytest.raises(FlutterProjectError, match="Low contrast"):
        ctx.enforce_accessibility_gates()
    ctx.apply_accessibility_fixes()
    assert ctx.clean_tree is not None
    assert ctx.clean_tree.children[0].style.text_color in {"0xFF000000", "0xFFFFFFFF"}


def test_auto_fix_without_strict_contrast_repairs_tree() -> None:
    ctx = _context(auto_fix=True, strict_contrast=False)
    ctx.enforce_accessibility_gates()
    ctx.apply_accessibility_fixes()
    assert ctx.clean_tree is not None
    assert ctx.clean_tree.children[0].style.text_color in {"0xFF000000", "0xFFFFFFFF"}
