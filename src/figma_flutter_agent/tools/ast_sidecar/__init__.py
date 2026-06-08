"""AST sidecar public rule operations."""

from __future__ import annotations

from loguru import logger

from figma_flutter_agent.tools.ast_sidecar.commands import require_ast_compiler
from figma_flutter_agent.tools.ast_sidecar.keys import discover_figma_node_ids
from figma_flutter_agent.tools.ast_sidecar.transport import invoke_sidecar_json, oversized_ast_error
from figma_flutter_agent.tools.ast_sidecar.types import (
    AST_SIDECAR_MAX_SOURCE_BYTES,
    AstRule,
    AstSidecarError,
    AstSidecarResult,
    ast_source_exceeds_sidecar_limit,
)
from figma_flutter_agent.tools.ast_sidecar.widgets import (
    extract_widget_by_figma_id,
    list_bindings_in_dart_source,
    replace_widget_by_figma_id,
)

LAYOUT_RULES: tuple[AstRule, ...] = (
    "unscale_design_expressions",
    "unwrap_scale_layout_builder",
    "strip_viewport_scale_transform",
)

CODEGEN_AST_RULES: tuple[AstRule, ...] = ("codegen_pass",)


def apply_rules_chunked_by_figma_keys(
    source: str,
    rules: tuple[AstRule, ...],
    *,
    include_text_scaler: bool,
    command: list[str],
) -> str:
    """Apply AST rules per ``ValueKey('figma-...')`` subtree without a full-file pass."""
    working = source
    node_ids = discover_figma_node_ids(source)
    if not node_ids:
        raise oversized_ast_error(source)
    for node_id in node_ids:
        snippet = extract_widget_by_figma_id(working, node_id)
        if snippet is None:
            continue
        if ast_source_exceeds_sidecar_limit(snippet):
            raise oversized_ast_error(snippet)
        patched = apply_rules_subprocess(
            snippet,
            rules,
            include_text_scaler=include_text_scaler,
            command=command,
        )
        replaced = replace_widget_by_figma_id(working, node_id, patched.source)
        if replaced is not None:
            working = replaced
    return working


def apply_rules_subprocess(
    source: str,
    rules: tuple[AstRule, ...],
    *,
    include_text_scaler: bool,
    command: list[str],
) -> AstSidecarResult:
    response = invoke_sidecar_json(
        command,
        {
            "version": 1,
            "command": "apply_rules",
            "source": source,
            "rules": list(rules),
            "options": {"includeTextScaler": include_text_scaler},
        },
    )
    return AstSidecarResult(
        source=str(response.get("source", source)),
        backend="subprocess",
        edits=list(response.get("edits") or []),
    )


def rule_ran_in_edits(edits: list[dict[str, object]], rule: str) -> bool:
    return any(str(item.get("rule", "")) == rule for item in edits)


def apply_ast_rules(
    source: str,
    rules: tuple[AstRule, ...] | None = None,
    *,
    include_text_scaler: bool = True,
    prefer_subprocess: bool = True,
) -> AstSidecarResult:
    """Apply Dart AST sidecar rules to generated source."""
    del prefer_subprocess
    active_rules = rules or LAYOUT_RULES
    command = require_ast_compiler()
    if ast_source_exceeds_sidecar_limit(source):
        logger.info(
            "AST sidecar oversized ({} bytes); applying chunked pass by figma ValueKey",
            len(source.encode("utf-8")),
        )
        source = apply_rules_chunked_by_figma_keys(
            source,
            active_rules,
            include_text_scaler=include_text_scaler,
            command=command,
        )
        return AstSidecarResult(
            source=source,
            backend="subprocess",
            edits=[],
        )
    return apply_rules_subprocess(
        source,
        active_rules,
        include_text_scaler=include_text_scaler,
        command=command,
    )


def apply_codegen_ast_rules(
    source: str,
    *,
    include_text_scaler: bool = True,
    prefer_subprocess: bool = True,
) -> AstSidecarResult:
    """Run the full codegen AST pass."""
    del prefer_subprocess
    command = require_ast_compiler()
    if ast_source_exceeds_sidecar_limit(source):
        logger.warning(
            "Codegen AST skipped for oversized source ({} bytes); "
            "chunked codegen_pass can corrupt responsive screen shells",
            len(source.encode("utf-8")),
        )
        return AstSidecarResult(
            source=source,
            backend="skipped",
            edits=[],
        )
    return apply_rules_subprocess(
        source,
        CODEGEN_AST_RULES,
        include_text_scaler=include_text_scaler,
        command=command,
    )


def ensure_named_widgets_on_pressed(
    source: str,
    widget_names: tuple[str, ...],
) -> str:
    """Inject no-op ``onPressed`` for custom widget constructors."""
    if ast_source_exceeds_sidecar_limit(source):
        logger.warning(
            "Skipping ensure_named_widgets_on_pressed for oversized Dart ({} bytes)",
            len(source.encode("utf-8")),
        )
        return source
    response = invoke_sidecar_json(
        require_ast_compiler(),
        {
            "version": 1,
            "command": "ensure_named_widgets_on_pressed",
            "source": source,
            "widgetNames": list(widget_names),
        },
    )
    return str(response.get("source", source))


def wrap_widget_on_pressed(source: str, widget_name: str) -> str:
    """Move ``onPressed`` from a non-button widget onto ``GestureDetector``."""
    if ast_source_exceeds_sidecar_limit(source):
        logger.warning(
            "Skipping wrap_widget_on_pressed for oversized Dart ({} bytes)",
            len(source.encode("utf-8")),
        )
        return source
    response = invoke_sidecar_json(
        require_ast_compiler(),
        {
            "version": 1,
            "command": "wrap_widget_on_pressed",
            "source": source,
            "widgetName": widget_name,
        },
    )
    return str(response.get("source", source))
