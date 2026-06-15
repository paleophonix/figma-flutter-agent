"""Map SYSTEMIC_BUG_RULES to sanitizer layers for coverage audit."""

from __future__ import annotations

from dataclasses import dataclass

from figma_flutter_agent.llm.prompts.principles import SYSTEMIC_BUG_RULES


@dataclass(frozen=True, slots=True)
class RuleCoverageRow:
    """One systemic bug rule and expected sanitizer layer."""

    rule_prefix: str
    topic: str
    sanitizer_layer: str
    test_hint: str


RULE_COVERAGE: tuple[RuleCoverageRow, ...] = (
    RuleCoverageRow(
        "NEVER declare `Key? key", "constructor", "dart_syntax_repairs / AST", "test_interaction"
    ),
    RuleCoverageRow(
        "NEVER emit duplicate named parameters",
        "constructor",
        "dart_syntax_repairs",
        "dart analyze",
    ),
    RuleCoverageRow(
        "NEVER prefix `fontSize`", "typography", "AST theme pass", "test_emit_fidelity"
    ),
    RuleCoverageRow(
        "NEVER nest chained `.copyWith`", "typography", "dart_syntax_repairs", "planner reconcile"
    ),
    RuleCoverageRow(
        "NEVER set `TextStyle.height` to Figma line-height pixels",
        "typography",
        "text_emit / decoration",
        "test_checkbox_and_input_vertical_center",
    ),
    RuleCoverageRow(
        "NEVER use `Flex(fit:`", "flex", "ir/validate + wrap", "test_flex_overflow_guards"
    ),
    RuleCoverageRow(
        "NEVER place a `TextField` directly inside a `Row`",
        "flex",
        "ir/validate guards",
        "test_ir_validate",
    ),
    RuleCoverageRow(
        "NEVER place scrollable widgets directly inside",
        "scroll",
        "ir/validate guards",
        "test_ir_validate",
    ),
    RuleCoverageRow(
        "NEVER emit `stackPlacement` without bounded",
        "stack",
        "ir/validate graph",
        "test_ir_validate",
    ),
    RuleCoverageRow(
        "Figma layers are ordered top-to-bottom", "stack", "parser/stack_paint", "test_stack_paint"
    ),
    RuleCoverageRow(
        "NEVER reference `assets/` paths that are not exported",
        "assets",
        "ir/validate assets",
        "test_ir_validate",
    ),
    RuleCoverageRow(
        "NEVER duplicate `figmaId`", "ir_contract", "ir/validate presence", "test_ir_validate"
    ),
    RuleCoverageRow(
        "Interactive hit targets MUST be at least 44",
        "touch",
        "ir/validate guards",
        "test_ir_validate",
    ),
    RuleCoverageRow(
        "NEVER output raw `Color(0xFF", "tokens", "ir/validate tokens", "test_ir_validate"
    ),
    RuleCoverageRow(
        "NEVER introduce `LayoutBuilder`", "responsive", "prompt only", "manual review"
    ),
    RuleCoverageRow(
        "NEVER pin intrinsic button bodies",
        "overflow",
        "flex_policy + invariants",
        "test_bounded_slot_conservation",
    ),
    RuleCoverageRow(
        "NEVER subtract host padding from `OverflowBox`",
        "overflow",
        "widgets/text.py",
        "test_flex_overflow_guards",
    ),
    RuleCoverageRow(
        "NEVER pin a fixed-height artboard shell with `SizedBox(height:`",
        "overflow",
        "column/alignment emit",
        "test_artboard_frame_growth",
    ),
    RuleCoverageRow("NEVER use `Image.network`", "assets", "emit + validate", "test_layout_card"),
)


def render_systemic_rules_markdown() -> str:
    """Render SYSTEMIC_BUG_RULES coverage table."""
    lines = [
        "# IR / LLM systemic rules coverage",
        "",
        f"Total `SYSTEMIC_BUG_RULES` entries: **{len(SYSTEMIC_BUG_RULES)}**.",
        "",
        "Mapped sanitizer layers (representative subset):",
        "",
        "| Topic | Rule prefix | Sanitizer | Test hint |",
        "| --- | --- | --- | --- |",
    ]
    for row in RULE_COVERAGE:
        lines.append(
            f"| {row.topic} | {row.rule_prefix[:48]}… | {row.sanitizer_layer} | {row.test_hint} |"
        )
    lines.extend(
        [
            "",
            "## Gaps to close",
            "",
            "- Rules with **prompt only** and no deterministic sanitizer need AST or IR guard follow-up.",
            "- Every new rule in `SYSTEMIC_BUG_RULES` should add a row here and a generic fixture test.",
            "",
        ]
    )
    return "\n".join(lines)
