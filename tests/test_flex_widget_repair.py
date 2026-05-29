"""Repairs for mis-typed Flex vs Flexible widgets."""

from __future__ import annotations

from figma_flutter_agent.generator.dart_syntax_repairs import fix_misused_flex_widget_name
from figma_flutter_agent.fixtures.golden_planned import build_fixture_planned_files
from figma_flutter_agent.generator.planned_dart import reconcile_planned_dart_files


def test_fix_misused_flex_widget_name() -> None:
    source = "Row(children: [Flex(fit: FlexFit.loose, child: Text('x'))])"
    fixed = fix_misused_flex_widget_name(source)
    assert "Flexible(fit:" in fixed
    assert "Flex(fit:" not in fixed


def test_reconcile_fixture_layout_keeps_flexible_not_flex() -> None:
    planned = reconcile_planned_dart_files(build_fixture_planned_files("sign_up_and_sign_in"))
    layout = planned["lib/generated/sign_up_and_sign_in_layout.dart"]
    assert "Flex(fit:" not in layout
    assert "Flexible(fit:" in layout
