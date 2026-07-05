"""Emit laws exercised by the mobile_settings screen regressions."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from figma_flutter_agent.config.models import WidgetExtractionConfig
from figma_flutter_agent.generator.layout.widget_roots import (
    finalize_extracted_widget_body,
    validate_widget_build_has_no_parent_data_root,
)
from figma_flutter_agent.generator.widget_extraction.collect import collect_widget_specs
from figma_flutter_agent.generator.widget_extraction.enrich import apply_widget_enrich_response
from figma_flutter_agent.generator.widget_extractor import render_cluster_widgets
from figma_flutter_agent.schemas import CleanDesignTreeNode
from figma_flutter_agent.schemas.reusable_candidates import WidgetEnrichResponse

_FIXTURE = Path(".debug/screen/limbo/mobile_settings/processed.json")
_ENRICH = Path(".debug/screen/limbo/mobile_settings/widget_enrich.json")

_DIVIDER_STACK_BODY = (
    "Stack(clipBehavior: Clip.none, children: ["
    "Positioned(left: 0.0, bottom: 0.0, width: 343.0, height: 0.5, "
    "key: ValueKey('figma-I272_9316_126_1617'), "
    "child: Semantics(label: 'Divider', "
    "child: SvgPicture.asset('assets/icons/divider_I272_9316;126_1617.svg', "
    "width: 343.0, height: 1.0, fit: BoxFit.fitWidth)))])"
)


def test_single_positioned_child_stack_body_is_unwrapped() -> None:
    """A Stack whose only child is a Positioned unwraps to that child.

    Regression: SettingsDividerWidget returned a bare Stack of a single
    Positioned. In an unbounded-height Column the Stack fails ``size.isFinite``
    (``A Stack requires bounded constraints``) and the whole screen renders blank.
    """
    out = finalize_extracted_widget_body(_DIVIDER_STACK_BODY)
    assert not out.startswith("Stack("), out[:40]
    assert not out.startswith("Positioned("), out[:40]
    # The lone Positioned's child survives (bounded widget, safe in any host).
    assert out.startswith("Semantics(") or out.startswith("SvgPicture.asset(")
    assert "SvgPicture.asset(" in out


def test_multi_positioned_child_stack_body_kept() -> None:
    """A Stack with multiple positioned children is not unwrapped (overlapping)."""
    body = (
        "Stack(clipBehavior: Clip.none, children: ["
        "Positioned(left: 0.0, top: 0.0, child: Text('a')), "
        "Positioned(left: 5.0, top: 5.0, child: Text('b'))])"
    )
    out = finalize_extracted_widget_body(body)
    assert out.startswith("Stack(")


def test_unwrapped_divider_body_passes_parent_data_gate() -> None:
    """After unwrap the widget file must not trip the Positioned-root gate."""
    body = finalize_extracted_widget_body(_DIVIDER_STACK_BODY)
    source = (
        "class SettingsDividerWidget extends StatelessWidget {\n"
        "  @override\n"
        "  Widget build(BuildContext context) {\n"
        f"    return {body};\n"
        "  }\n"
        "}\n"
    )
    assert validate_widget_build_has_no_parent_data_root(source) == []


def _load_root() -> CleanDesignTreeNode:
    if not _FIXTURE.is_file():
        pytest.skip("mobile_settings debug dumps not available")
    processed = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    return CleanDesignTreeNode.model_validate(processed["cleanTree"])


def _cluster_summary(root: CleanDesignTreeNode) -> dict[str, int]:
    counts: Counter[str] = Counter()

    def walk(node: CleanDesignTreeNode) -> None:
        if node.cluster_id:
            counts[node.cluster_id] += 1
        for child in node.children:
            walk(child)

    walk(root)
    return dict(counts)


def test_settings_divider_cluster_widget_emits_bounded_root() -> None:
    """Integration: cluster render must not return a bare unbounded Stack root."""
    if not _ENRICH.is_file():
        pytest.skip("mobile_settings widget_enrich.json not available")
    root = _load_root()
    config = WidgetExtractionConfig()
    specs = collect_widget_specs(
        root,
        cluster_summary=_cluster_summary(root),
        config=config,
        llm_candidates=None,
    )
    enrich_raw = json.loads(_ENRICH.read_text(encoding="utf-8"))
    enrich = WidgetEnrichResponse.model_validate(enrich_raw["response"])
    specs = apply_widget_enrich_response(specs, enrich, widget_suffix="Widget")
    result = render_cluster_widgets(specs, uses_svg=True, clean_trees=[root])
    divider = result.files["lib/widgets/settings_divider_widget.dart"]
    assert "return Stack(" not in divider
    assert "SvgPicture.asset(" in divider
