"""AST rule dispatch helpers for Dart postprocess."""

from __future__ import annotations

from figma_flutter_agent.tools.ast_sidecar import AstRule, apply_ast_rules
from figma_flutter_agent.tools.ast_sidecar import ast_source_exceeds_sidecar_limit


def run_rules(
    source: str,
    rules: tuple[AstRule, ...],
    *,
    include_text_scaler: bool = False,
) -> str:
    if ast_source_exceeds_sidecar_limit(source):
        return source
    return apply_ast_rules(
        source,
        rules,
        include_text_scaler=include_text_scaler,
    ).source
