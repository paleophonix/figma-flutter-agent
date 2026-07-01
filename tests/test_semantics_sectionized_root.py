"""Semantics guards for sectionized responsive screen roots."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.generator.ir.passes.sectionize import sectionize_root_stack
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.parser.semantics import classify_screen_ir
from figma_flutter_agent.schemas import WidgetIrKind


def _load_product_detail_vertical_root():
    from figma_flutter_agent.schemas import CleanDesignTreeNode

    payload = json.loads(
        Path("tests/fixtures/layouts/product_detail_vertical.json").read_text(encoding="utf-8"),
    )
    return CleanDesignTreeNode.model_validate(payload)


def test_sectionized_root_classifies_as_nav_scroll_host_not_accordion() -> None:
    clean = _load_product_detail_vertical_root()
    screen_ir = default_screen_ir(clean)
    updated_ir, updated_clean = sectionize_root_stack(
        screen_ir,
        clean,
        responsive_reflow_enabled=True,
    )
    classified_ir, report = classify_screen_ir(updated_ir, updated_clean)
    assert classified_ir.root.kind == WidgetIrKind.NAV_SCROLL_HOST
    assert classified_ir.root.kind != WidgetIrKind.CONTAINER_ACCORDION
    assert report.semantic is not None
