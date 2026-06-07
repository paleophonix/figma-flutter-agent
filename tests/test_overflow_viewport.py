"""Codegen regression: layouts must not overflow a 320px logical viewport."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from figma_flutter_agent.config import Settings, apply_production_profile
from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.codegen_checks import validate_generated_dart
from figma_flutter_agent.generator.planner import plan_from_figma_root
from figma_flutter_agent.parser.tree import build_clean_tree
from figma_flutter_agent.stages.validate import ValidateStageRequest, validate_planned_generation


@pytest.mark.parametrize(
    "fixture_name",
    [
        "figma_node_sample.json",
        "figma_cards_sample.json",
        "figma_carousel_sample.json",
        "figma_scroll_vertical_sample.json",
    ],
)
def test_fixture_layouts_pass_narrow_viewport_codegen(fixture_name: str) -> None:
    root = json.loads(Path(f"tests/fixtures/{fixture_name}").read_text(encoding="utf-8"))
    settings = Settings()
    planned = plan_from_figma_root(root, settings, node_id=str(root["id"]))
    tree, _, _, _ = build_clean_tree(root)

    validate_generated_dart(
        planned,
        tree,
        responsive_enabled=settings.agent.responsive.enabled,
        avoid_fixed_sizes=settings.agent.layout.avoid_fixed_sizes,
    )


def test_production_profile_validates_primary_fixtures() -> None:
    settings = apply_production_profile(Settings())
    for fixture_name in ("figma_node_sample.json", "figma_cards_sample.json"):
        root = json.loads(Path(f"tests/fixtures/{fixture_name}").read_text(encoding="utf-8"))
        planned = plan_from_figma_root(root, settings, node_id=str(root["id"]))
        tree, _, _, cluster_summary = build_clean_tree(root)

        result = validate_planned_generation(
            ValidateStageRequest(
                planned_files=planned,
                clean_trees=[tree],
                responsive_enabled=settings.agent.responsive.enabled,
                avoid_fixed_sizes=settings.agent.layout.avoid_fixed_sizes,
                strict_accessibility_labels=settings.agent.quality.strict_accessibility_labels,
                cluster_summary=cluster_summary,
                cluster_min_count=settings.agent.generation.cluster_min_count,
                widget_suffix=settings.agent.naming.widget_suffix,
                enforce_cluster_widgets=settings.agent.generation.enforce_cluster_widgets,
            )
        )
        assert isinstance(result.warnings, list)


def test_narrow_viewport_allows_fittedbox_scaled_artboard() -> None:
    from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

    tree = CleanDesignTreeNode(id="1", name="Screen", type=NodeType.STACK)
    planned = {
        "lib/features/sign_up/sign_up_screen.dart": """
class SignUpScreen extends StatelessWidget {
  Widget build(BuildContext context) {
    final textScaler = MediaQuery.textScalerOf(context);
    return GeneratedScreenShell(child: const SignUpLayout());
  }
}
""",
        "lib/generated/sign_up_layout.dart": """
class SignUpLayout extends StatelessWidget {
  Widget build(BuildContext context) {
    final textScaler = MediaQuery.textScalerOf(context);
    return Material(
      child: FittedBox(
        fit: BoxFit.scaleDown,
        child: SizedBox(
          width: 414.0,
          height: 896.0,
          child: Stack(children: []),
        ),
      ),
    );
  }
}
""",
    }

    validate_generated_dart(
        planned,
        tree,
        responsive_enabled=True,
        avoid_fixed_sizes=False,
    )


def test_narrow_viewport_allows_layout_builder_bottom_chrome_artboard() -> None:
    from figma_flutter_agent.generator.layout.widgets.render import render_node_body
    from figma_flutter_agent.schemas import (
        CleanDesignTreeNode,
        NodeType,
        Sizing,
        StackPlacement,
    )

    root = CleanDesignTreeNode(
        id="1:319",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=390.0, height=844.0),
        children=[
            CleanDesignTreeNode(
                id="1:1330",
                name="BottomNavBar",
                type=NodeType.COLUMN,
                stack_placement=StackPlacement(vertical="BOTTOM", top=738.0, height=106.0),
            )
        ],
    )
    layout_body = render_node_body(root, uses_svg=False, is_layout_root=True)
    planned = {
        "lib/features/background/background_screen.dart": """
class BackgroundScreen extends StatelessWidget {
  Widget build(BuildContext context) {
  final textScaler = MediaQuery.textScalerOf(context);
  return GeneratedScreenShell(child: const BackgroundLayout());
  }
}
""",
        "lib/generated/background_layout.dart": f"""
class BackgroundLayout extends StatelessWidget {{
  Widget build(BuildContext context) {{
  final textScaler = MediaQuery.textScalerOf(context);
  return Material(child: {layout_body});
  }}
}}
""",
    }
    validate_generated_dart(
        planned,
        root,
        responsive_enabled=False,
        avoid_fixed_sizes=False,
    )


def test_narrow_viewport_rejects_fixed_width_above_320() -> None:
    from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

    tree = CleanDesignTreeNode(id="1", name="Screen", type=NodeType.COLUMN)
    planned = {
        "lib/features/home/home_screen.dart": """
class HomeScreen extends StatelessWidget {
  Widget build(BuildContext context) {
    final textScaler = MediaQuery.textScalerOf(context);
    return GeneratedScreenShell(child: const HomeLayout());
  }
}
""",
        "lib/generated/home_layout.dart": """
class HomeLayout extends StatelessWidget {
  Widget build(BuildContext context) {
    final textScaler = MediaQuery.textScalerOf(context);
    return SizedBox(width: 400, child: Text('wide', textScaler: textScaler));
  }
}
""",
    }

    with pytest.raises(GenerationError, match="narrow viewport"):
        validate_generated_dart(
            planned,
            tree,
            responsive_enabled=True,
            avoid_fixed_sizes=False,
        )
