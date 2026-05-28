import pytest

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.codegen_checks import (
    _assert_valid_positioned_fields,
    remediate_text_scaler_contract,
    validate_generated_dart,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing, SizingMode


def test_remediate_text_scaler_contract_fixes_layout_spliced_refs() -> None:
    tree = CleanDesignTreeNode(id="1", name="Screen", type=NodeType.CONTAINER)
    planned = {
        "lib/features/sign_in/sign_in_screen.dart": """
class SignInScreen extends StatefulWidget {
  @override
  State<SignInScreen> createState() => _SignInScreenState();
}

class _SignInScreenState extends State<SignInScreen> {
  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        Positioned(
          key: ValueKey('figma-1_3576'),
          child: Text('LOG IN', textScaler: textScaler),
        ),
      ],
    );
  }
}
""",
    }
    fixed = remediate_text_scaler_contract(planned)
    validate_generated_dart(
        fixed,
        tree,
        responsive_enabled=False,
        avoid_fixed_sizes=False,
    )
    assert "MediaQuery.textScalerOf(context)" in fixed["lib/features/sign_in/sign_in_screen.dart"]


def test_validate_generated_dart_skips_text_scaler_for_non_text_widgets() -> None:
    tree = CleanDesignTreeNode(id="1", name="Screen", type=NodeType.CONTAINER)
    planned_files = {
        "lib/widgets/meditation_time_picker.dart": """
class MeditationTimePicker extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return const SizedBox();
  }
}
""",
        "lib/features/home/home_screen.dart": """
class HomeScreen extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final textScaler = MediaQuery.textScalerOf(context);
    return GeneratedScreenShell(child: Text('Home', textScaler: textScaler));
  }
}
""",
    }

    validate_generated_dart(
        planned_files,
        tree,
        responsive_enabled=True,
        avoid_fixed_sizes=False,
    )


def test_validate_generated_dart_requires_semantics_for_labeled_nodes() -> None:
    tree = CleanDesignTreeNode(
        id="1",
        name="Button",
        type=NodeType.BUTTON,
        accessibility_label="Continue",
    )
    planned_files = {
        "lib/features/home/home_screen.dart": "class HomeScreen extends StatelessWidget { Widget build(c) => Text('Go'); }",
    }

    with pytest.raises(GenerationError, match="Semantics"):
        validate_generated_dart(
            planned_files,
            tree,
            responsive_enabled=True,
            avoid_fixed_sizes=True,
        )


def test_strict_accessibility_requires_semantics_for_buttons_without_labels() -> None:
    tree = CleanDesignTreeNode(
        id="1",
        name="Submit",
        type=NodeType.BUTTON,
        text="Submit",
    )
    planned_files = {
        "lib/generated/home_layout.dart": """
class HomeLayout extends StatelessWidget {
  Widget build(BuildContext context) {
    final textScaler = MediaQuery.textScalerOf(context);
    return ElevatedButton(onPressed: () {}, child: Text('Submit'));
  }
}
""",
        "lib/features/home/home_screen.dart": """
class HomeScreen extends StatelessWidget {
  Widget build(BuildContext context) {
    final textScaler = MediaQuery.textScalerOf(context);
    return GeneratedScreenShell(child: const HomeLayout());
  }
}
""",
    }

    with pytest.raises(GenerationError, match="interactive controls"):
        validate_generated_dart(
            planned_files,
            tree,
            responsive_enabled=True,
            avoid_fixed_sizes=True,
            strict_accessibility_labels=True,
        )


def test_validate_generated_dart_passes_with_semantics_and_text_scaler() -> None:
    tree = CleanDesignTreeNode(
        id="1",
        name="Button",
        type=NodeType.BUTTON,
        accessibility_label="Continue",
    )
    planned_files = {
        "lib/features/home/home_screen.dart": """
class HomeScreen extends StatelessWidget {
  Widget build(BuildContext context) {
    final textScaler = MediaQuery.textScalerOf(context);
    return GeneratedScreenShell(
      child: Semantics(label: 'Continue', child: const Text('Continue')),
    );
  }
}
""",
    }

    warnings = validate_generated_dart(
        planned_files,
        tree,
        responsive_enabled=True,
        avoid_fixed_sizes=True,
    )
    assert isinstance(warnings, list)


def test_validate_generated_dart_accepts_semantics_in_layout_file() -> None:
    tree = CleanDesignTreeNode(
        id="1",
        name="Button",
        type=NodeType.BUTTON,
        accessibility_label="Continue",
    )
    planned_files = {
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
    return Semantics(label: 'Continue', child: ElevatedButton(onPressed: () {}, child: Text('Continue')));
  }
}
""",
    }

    warnings = validate_generated_dart(
        planned_files,
        tree,
        responsive_enabled=True,
        avoid_fixed_sizes=True,
    )
    assert isinstance(warnings, list)


def test_validate_generated_dart_warns_when_fill_nodes_missing_flex_widgets() -> None:
    tree = CleanDesignTreeNode(
        id="1",
        name="Row",
        type=NodeType.ROW,
        sizing=Sizing(width_mode=SizingMode.FILL),
        children=[
            CleanDesignTreeNode(
                id="2",
                name="Label",
                type=NodeType.TEXT,
                sizing=Sizing(width_mode=SizingMode.FILL),
            )
        ],
    )
    planned_files = {
        "lib/features/home/home_screen.dart": """
class HomeScreen extends StatelessWidget {
  Widget build(BuildContext context) {
    final textScaler = MediaQuery.textScalerOf(context);
    return GeneratedScreenShell(child: Row(children: [Text('A')]));
  }
}
""",
    }

    warnings = validate_generated_dart(
        planned_files,
        tree,
        responsive_enabled=True,
        avoid_fixed_sizes=True,
    )
    assert any("FILL-sized nodes" in warning for warning in warnings)


def test_validate_generated_dart_raises_on_fixed_width() -> None:
    tree = CleanDesignTreeNode(id="1", name="Screen", type=NodeType.CONTAINER)
    planned_files = {
        "lib/features/home/home_screen.dart": """
class HomeScreen extends StatelessWidget {
  Widget build(BuildContext context) {
    final textScaler = MediaQuery.textScalerOf(context);
    return GeneratedScreenShell(
      child: Column(children: [
        SizedBox(width: 100),
        SizedBox(width: 120),
        SizedBox(width: 140),
      ]),
    );
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
            use_deterministic_screen=True,
        )


def test_validate_generated_dart_warns_on_llm_screen_fixed_width() -> None:
    tree = CleanDesignTreeNode(id="1", name="Screen", type=NodeType.CONTAINER)
    planned_files = {
        "lib/features/reminders/reminders_screen.dart": """
class RemindersScreen extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final textScaler = MediaQuery.textScalerOf(context);
    return GeneratedScreenShell(
      child: SizedBox(width: 414, child: Text('SAVE', textScaler: textScaler)),
    );
  }
}
""",
    }

    warnings = validate_generated_dart(
        planned_files,
        tree,
        responsive_enabled=True,
        avoid_fixed_sizes=True,
        use_deterministic_screen=False,
    )

    assert any("fixed width values" in warning for warning in warnings)


def test_invalid_positioned_left_right_width_fails_validation() -> None:
    layout = """
class BadLayout extends StatelessWidget {
  Widget build(BuildContext context) {
    final textScaler = MediaQuery.textScalerOf(context);
    return Stack(children: [
      Positioned(left: 0, right: 1, width: 2, top: 0, child: Text('x', textScaler: textScaler)),
    ]);
  }
}
"""
    with pytest.raises(GenerationError, match="invalid Positioned"):
        _assert_valid_positioned_fields(layout, layout_path="lib/generated/bad_layout.dart")
