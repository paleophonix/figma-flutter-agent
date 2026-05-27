import pytest

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.codegen_checks import validate_generated_dart
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def test_validate_generated_dart_checks_all_screen_files_for_shell() -> None:
    primary = CleanDesignTreeNode(id="1", name="Home", type=NodeType.CONTAINER)
    destination = CleanDesignTreeNode(
        id="2",
        name="Button",
        type=NodeType.BUTTON,
        accessibility_label="Continue",
    )
    planned_files = {
        "lib/features/home/home_screen.dart": """
class HomeScreen extends StatelessWidget {
  Widget build(BuildContext context) {
    final textScaler = MediaQuery.textScalerOf(context);
    return GeneratedScreenShell(child: Semantics(label: 'Continue', child: Text('Go')));
  }
}
""",
        "lib/features/details/details_screen.dart": """
class DetailsScreen extends StatelessWidget {
  Widget build(BuildContext context) => const Text('Details');
}
""",
    }

    with pytest.raises(GenerationError, match="details_screen.dart"):
        validate_generated_dart(
            planned_files,
            [primary, destination],
            responsive_enabled=True,
            avoid_fixed_sizes=True,
        )


def test_validate_generated_dart_collects_labels_from_all_trees() -> None:
    primary = CleanDesignTreeNode(id="1", name="Home", type=NodeType.CONTAINER)
    destination = CleanDesignTreeNode(
        id="2",
        name="Submit",
        type=NodeType.BUTTON,
        accessibility_label="Submit order",
    )
    planned_files = {
        "lib/features/home/home_screen.dart": """
class HomeScreen extends StatelessWidget {
  Widget build(BuildContext context) {
    final textScaler = MediaQuery.textScalerOf(context);
    return GeneratedScreenShell(child: Text('Home'));
  }
}
""",
        "lib/features/checkout/checkout_screen.dart": """
class CheckoutScreen extends StatelessWidget {
  Widget build(BuildContext context) {
    final textScaler = MediaQuery.textScalerOf(context);
    return GeneratedScreenShell(child: Text('Checkout'));
  }
}
""",
    }

    with pytest.raises(GenerationError, match="Semantics"):
        validate_generated_dart(
            planned_files,
            [primary, destination],
            responsive_enabled=True,
            avoid_fixed_sizes=True,
        )
