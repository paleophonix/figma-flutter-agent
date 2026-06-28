"""Widget constructor signature mismatch routing for analyze repair."""

from __future__ import annotations

from figma_flutter_agent.stages.llm import LlmStageResult
from figma_flutter_agent.stages.llm_repair.models import LlmRepairStageResult
from figma_flutter_agent.stages.llm_repair.snapshot import (
    _apply_widget_constructor_signature_reconcile,
    _errors_suggest_widget_constructor_signature_mismatch,
)


def test_errors_suggest_widget_constructor_signature_mismatch() -> None:
    errors = (
        "error - lib/generated/sign_up_layout.dart:73:1572 - "
        "The named parameter 'label' isn't defined. - undefined_named_parameter",
        "error - lib/generated/sign_up_layout.dart:73:1587 - "
        "The named parameter 'isSelected' isn't defined. - undefined_named_parameter",
    )
    assert _errors_suggest_widget_constructor_signature_mismatch(errors)


def test_apply_widget_constructor_signature_reconcile_strips_chip_args() -> None:
    result = LlmRepairStageResult(
        planned_files={
            "lib/widgets/input_field_widget.dart": """
class InputFieldWidget extends StatelessWidget {
  const InputFieldWidget({super.key});
  @override
  Widget build(BuildContext context) => const SizedBox();
}
""",
            "lib/generated/sign_up_layout.dart": """
class SignUpLayout extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return InputFieldWidget(label: 'Lois', isSelected: false);
  }
}
""",
        },
        llm_result=LlmStageResult(),
    )
    assert _apply_widget_constructor_signature_reconcile(result)
    layout = result.planned_files["lib/generated/sign_up_layout.dart"]
    assert "label:" not in layout
    assert "isSelected" not in layout
