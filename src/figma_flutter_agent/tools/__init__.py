"""Compiled-tool clients (AST sidecar, etc.)."""

from figma_flutter_agent.tools.ast_sidecar import (
    AstSidecarError,
    AstSidecarResult,
    apply_ast_rules,
    apply_codegen_ast_rules,
    ensure_named_widgets_on_pressed,
    extract_widget_by_figma_id,
    replace_widget_by_figma_id,
    require_ast_compiler,
    wrap_widget_on_pressed,
)

__all__ = [
    "AstSidecarError",
    "AstSidecarResult",
    "apply_ast_rules",
    "apply_codegen_ast_rules",
    "ensure_named_widgets_on_pressed",
    "extract_widget_by_figma_id",
    "replace_widget_by_figma_id",
    "require_ast_compiler",
    "wrap_widget_on_pressed",
]
