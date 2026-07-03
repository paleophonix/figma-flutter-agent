# IR / LLM systemic rules coverage

Total `SYSTEMIC_BUG_RULES` entries: **52**.

Mapped sanitizer layers (representative subset):

| Topic | Rule prefix | Sanitizer | Test hint |
| --- | --- | --- | --- |
| constructor | NEVER declare `Key? key… | dart_syntax_repairs / AST | test_interaction |
| constructor | NEVER emit duplicate named parameters… | dart_syntax_repairs | dart analyze |
| typography | NEVER prefix `fontSize`… | AST theme pass | test_emit_fidelity |
| typography | NEVER nest chained `.copyWith`… | dart_syntax_repairs | planner reconcile |
| typography | NEVER set `TextStyle.height` to Figma line-heigh… | text_emit / decoration | test_checkbox_and_input_vertical_center |
| flex | NEVER use `Flex(fit:`… | ir/validate + wrap | test_flex_overflow_guards |
| flex | NEVER place a `TextField` directly inside a `Row… | ir/validate guards | test_ir_validate |
| scroll | NEVER place scrollable widgets directly inside… | ir/validate guards | test_ir_validate |
| stack | NEVER emit `stackPlacement` without bounded… | ir/validate graph | test_ir_validate |
| stack | Figma layers are ordered top-to-bottom… | parser/stack_paint | test_stack_paint |
| assets | NEVER reference `assets/` paths that are not exp… | ir/validate assets | test_ir_validate |
| ir_contract | NEVER duplicate `figmaId`… | ir/validate presence | test_ir_validate |
| touch | Interactive hit targets MUST be at least 44… | ir/validate guards | test_ir_validate |
| tokens | NEVER output raw `Color(0xFF… | ir/validate tokens | test_ir_validate |
| responsive | NEVER introduce `LayoutBuilder`… | prompt only | manual review |
| overflow | NEVER pin intrinsic button bodies… | flex_policy + invariants | test_bounded_slot_conservation |
| overflow | NEVER subtract host padding from `OverflowBox`… | widgets/text.py | test_flex_overflow_guards |
| overflow | NEVER pin a fixed-height artboard shell with `Si… | column/alignment emit | test_artboard_frame_growth |
| assets | NEVER use `Image.network`… | emit + validate | test_layout_card |

## Gaps to close

- Rules with **prompt only** and no deterministic sanitizer need AST or IR guard follow-up.
- Every new rule in `SYSTEMIC_BUG_RULES` should add a row here and a generic fixture test.
