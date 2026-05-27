"""Layout-file fixed-size validation in codegen_checks."""

import pytest

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.codegen_checks import validate_generated_dart
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def test_layout_fixed_width_in_sized_box_fails() -> None:
    tree = CleanDesignTreeNode(id="1", name="Screen", type=NodeType.COLUMN)
    planned = {
        "lib/features/home/home_screen.dart": """
class HomeScreen extends StatelessWidget {
  Widget build(BuildContext context) {
    final textScaler = MediaQuery.textScalerOf(context);
    return GeneratedScreenShell(child: const Placeholder());
  }
}
""",
        "lib/generated/home_layout.dart": """
class HomeLayout extends StatelessWidget {
  Widget build(BuildContext context) {
    final textScaler = MediaQuery.textScalerOf(context);
    return SizedBox(width: 120, child: Text('x', textScaler: textScaler));
  }
}
""",
    }

    with pytest.raises(GenerationError, match="layout Dart contains .* fixed width"):
        validate_generated_dart(
            planned,
            tree,
            responsive_enabled=True,
            avoid_fixed_sizes=True,
        )


def test_layout_double_infinity_and_positioned_allowed() -> None:
    tree = CleanDesignTreeNode(id="1", name="Screen", type=NodeType.STACK)
    planned = {
        "lib/features/home/home_screen.dart": """
class HomeScreen extends StatelessWidget {
  Widget build(BuildContext context) {
    final textScaler = MediaQuery.textScalerOf(context);
    return GeneratedScreenShell(child: const Placeholder());
  }
}
""",
        "lib/generated/home_layout.dart": """
class HomeLayout extends StatelessWidget {
  Widget build(BuildContext context) {
    final textScaler = MediaQuery.textScalerOf(context);
    return Stack(children: [
      Positioned(left: 0, top: 0, width: 80, height: 40, child: Text('x', textScaler: textScaler)),
      SizedBox(width: double.infinity, child: Text('y', textScaler: textScaler)),
    ]);
  }
}
""",
    }

    validate_generated_dart(
        planned,
        tree,
        responsive_enabled=True,
        avoid_fixed_sizes=True,
    )


def test_layout_fixed_width_allowed_for_stack_root_frames() -> None:
    tree = CleanDesignTreeNode(id="1", name="Screen", type=NodeType.STACK)
    planned = {
        "lib/features/home/home_screen.dart": """
class HomeScreen extends StatelessWidget {
  Widget build(BuildContext context) {
    final textScaler = MediaQuery.textScalerOf(context);
    return GeneratedScreenShell(child: const Placeholder());
  }
}
""",
        "lib/generated/home_layout.dart": """
class HomeLayout extends StatelessWidget {
  Widget build(BuildContext context) {
    final textScaler = MediaQuery.textScalerOf(context);
    return SizedBox(width: 96.0, height: 96.0, child: Stack(children: []));
  }
}
""",
    }

    validate_generated_dart(
        planned,
        tree,
        responsive_enabled=True,
        avoid_fixed_sizes=True,
    )
