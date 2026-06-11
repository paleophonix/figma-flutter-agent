"""Screen Dart emission from screen IR."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.generator.ir.expression import emit_merged_root_expression
from figma_flutter_agent.generator.ir.tree import merge_screen_ir
from figma_flutter_agent.generator.ir.validate import apply_ir_guards, validate_screen_ir
from figma_flutter_agent.schemas import CleanDesignTreeNode, DesignTokens, ScreenIr


def emit_screen_code_from_ir(
    screen_ir: ScreenIr,
    *,
    clean_tree: CleanDesignTreeNode,
    screen_class: str,
    ctx: IrEmitContext,
    use_auto_route: bool = False,
    use_scaffold: bool = True,
    app_bar_title: str | None = None,
    responsive_shell: bool = False,
    extracted_class_by_widget_name: dict[str, str] | None = None,
    extracted_widget_names: frozenset[str] | None = None,
    project_dir: Path | None = None,
    tokens: DesignTokens | None = None,
) -> str:
    """Compile ``ScreenIr`` into a ``StatelessWidget`` Dart class."""
    if ctx.policy.validate:
        clean_tree = validate_screen_ir(
            screen_ir,
            clean_tree,
            extracted_widget_names=extracted_widget_names,
            project_dir=project_dir,
            tokens=tokens,
            apply_guards=ctx.policy.apply_guards,
        )
    elif ctx.policy.apply_guards:
        clean_tree = apply_ir_guards(screen_ir, clean_tree, tokens=tokens)
    merged = merge_screen_ir(
        clean_tree,
        screen_ir,
        extracted_class_by_widget_name=extracted_class_by_widget_name,
    )
    from figma_flutter_agent.generator.layout import body_needs_text_scaler
    from figma_flutter_agent.generator.layout.cupertino import screen_shell_dart

    body = emit_merged_root_expression(merged, ctx=ctx)
    if responsive_shell:
        body = f"GeneratedScreenShell(child: {body})"
    root_widget, screen_scaler = screen_shell_dart(
        body=body,
        theme_variant=ctx.theme_variant,
        use_scaffold=use_scaffold,
        title=app_bar_title or "Screen",
        needs_scaler_preamble=body_needs_text_scaler(body) or use_scaffold,
    )
    auto_route = "@RoutePage()\n" if use_auto_route else ""
    return f"""{auto_route}class {screen_class} extends StatelessWidget {{
  const {screen_class}({{super.key}});

  @override
  Widget build(BuildContext context) {{
{screen_scaler}    return {root_widget};
  }}
}}"""
