import json
from pathlib import Path

import pytest

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.codegen_checks import validate_generated_dart
from figma_flutter_agent.generator.layout_renderer import render_layout_file
from figma_flutter_agent.parser.tree import build_clean_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def test_fixture_generates_deterministic_layout() -> None:
    """E2E acceptance: Figma fixture JSON produces deterministic Dart layout."""
    fixture = Path("tests/fixtures/figma_node_sample.json")
    root = json.loads(fixture.read_text(encoding="utf-8"))
    tree, _, _, _ = build_clean_tree(root)

    files = render_layout_file(tree, feature_name="onboarding", uses_svg=False)
    layout = files["lib/generated/onboarding_layout.dart"]

    assert "class OnboardingLayout extends StatelessWidget" in layout
    assert "MediaQuery.textScalerOf(context)" in layout
    assert "Column(" in layout
    assert "Text('Welcome'" in layout
    assert "Text('Continue'" in layout
    assert "textScaler: textScaler" in layout


def test_validate_generated_dart_fails_without_text_scaler() -> None:
    tree = CleanDesignTreeNode(id="1", name="Screen", type=NodeType.CONTAINER)
    planned_files = {
        "lib/features/home/home_screen.dart": """
class HomeScreen extends StatelessWidget {
  Widget build(BuildContext context) {
    return GeneratedScreenShell(child: const Text('Home'));
  }
}
""",
    }

    with pytest.raises(GenerationError, match="textScalerOf"):
        validate_generated_dart(
            planned_files,
            tree,
            responsive_enabled=True,
            avoid_fixed_sizes=False,
        )


def test_validate_generated_dart_fails_on_fixed_width() -> None:
    tree = CleanDesignTreeNode(id="1", name="Screen", type=NodeType.CONTAINER)
    planned_files = {
        "lib/features/home/home_screen.dart": """
class HomeScreen extends StatelessWidget {
  Widget build(BuildContext context) {
    final textScaler = MediaQuery.textScalerOf(context);
    return GeneratedScreenShell(child: SizedBox(width: 100));
  }
}
""",
    }

    with pytest.raises(GenerationError, match="fixed width"):
        validate_generated_dart(
            planned_files,
            tree,
            responsive_enabled=True,
            avoid_fixed_sizes=True,
        )
