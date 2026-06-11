"""UTF-8 I/O and AST sidecar dispatch for generated Dart."""

from __future__ import annotations

import re

from figma_flutter_agent.generator.dart.postprocess.calls import (
    repair_obsolete_dart_default_colons,
    sanitize_named_only_widget_calls,
)
from figma_flutter_agent.generator.dart.postprocess.calls import (
    split_top_level_commas as _split_top_level_commas,
)
from figma_flutter_agent.generator.dart.postprocess.imports import (
    ensure_app_layout_import,
    ensure_dart_ui_import,
    strip_self_widget_import,
)
from figma_flutter_agent.generator.dart.postprocess.io import (
    UTF8_ENCODING,
    read_dart_source,
    write_dart_source,
)
from figma_flutter_agent.generator.dart.postprocess.rules import run_rules
from figma_flutter_agent.generator.dart.postprocess.text import (
    TEXT_DISPLAY_WIDGET_RE,
    ensure_text_style_leading_distribution,
    fix_empty_text_before_text_scaler,
    fix_misplaced_text_style_parameters,
    fix_text_style_height_as_ratio,
)
from figma_flutter_agent.generator.dart.postprocess.text_scaler import (
    ensure_text_scaler_support,
    inline_orphan_text_scaler_refs,
    strip_const_runtime_text_scaler,
)
from figma_flutter_agent.tools.ast_sidecar import (
    AstRule,
    apply_codegen_ast_rules,
    ast_source_exceeds_sidecar_limit,
    ensure_named_widgets_on_pressed,
    wrap_widget_on_pressed,
)

COMPILER_EMITTED_FIGMA_KEY_RE = re.compile(r"ValueKey\('figma-[^']+'\)")


def _run_rules(
    source: str,
    rules: tuple[AstRule, ...],
    *,
    include_text_scaler: bool = False,
) -> str:
    return run_rules(source, rules, include_text_scaler=include_text_scaler)


def _should_skip_codegen_ast_for_compiler_emit(source: str) -> bool:
    """Skip codegen AST when deterministic emit already produced valid Dart."""
    from figma_flutter_agent.generator.dart.llm_codegen import validate_dart_delimiters

    if validate_dart_delimiters(source) is not None:
        return False
    return COMPILER_EMITTED_FIGMA_KEY_RE.search(source) is not None


def process_generated_dart_source(
    source: str,
    *,
    include_text_scaler: bool = True,
    use_ast_sidecar: bool = True,
) -> str:
    from loguru import logger

    from figma_flutter_agent.generator.dart.llm_codegen import validate_dart_delimiters

    pre_ast = source
    if not use_ast_sidecar:
        updated = source
    elif _should_skip_codegen_ast_for_compiler_emit(source):
        logger.info(
            "Skipping codegen AST for compiler-emitted Dart ({} bytes)",
            len(source.encode(UTF8_ENCODING)),
        )
        updated = source
    else:
        updated = apply_codegen_ast_rules(
            source,
            include_text_scaler=include_text_scaler,
        ).source
        delimiter_error = validate_dart_delimiters(updated)
        if delimiter_error is not None:
            from figma_flutter_agent.pipeline.warning_policy import log_recoverable

            log_recoverable(
                "Codegen AST broke Dart delimiters ({}); keeping pre-AST source",
                delimiter_error,
            )
            updated = pre_ast
    if include_text_scaler:
        updated = strip_const_runtime_text_scaler(updated)
    updated = ensure_app_layout_import(updated)
    updated = ensure_dart_ui_import(updated)
    from figma_flutter_agent.generator.dart.file_parts import relocate_directives_to_header

    return relocate_directives_to_header(updated)


def process_generated_dart_file(
    path: object,
    *,
    include_text_scaler: bool = True,
    use_ast_sidecar: bool = True,
) -> str:
    from pathlib import Path

    dart_path = Path(path)
    processed = process_generated_dart_source(
        read_dart_source(dart_path),
        include_text_scaler=include_text_scaler,
        use_ast_sidecar=use_ast_sidecar,
    )
    write_dart_source(dart_path, processed)
    return processed


def postprocess_generated_dart(source: str, *, include_text_scaler: bool = True) -> str:
    processed = process_generated_dart_source(source, include_text_scaler=include_text_scaler)
    processed = fix_text_style_height_as_ratio(processed)
    from figma_flutter_agent.generator.dart.llm_codegen import validate_dart_delimiters

    delimiter_error = validate_dart_delimiters(processed)
    if delimiter_error is not None:
        from figma_flutter_agent.pipeline.warning_policy import log_recoverable

        log_recoverable(
            "Postprocess broke Dart delimiters ({}); keeping pre-postprocess source",
            delimiter_error,
        )
        return source
    return processed


def apply_codegen_dart_fixes(
    source: str,
    *,
    include_text_scaler: bool = True,
    layout_via_ast: bool = False,
) -> str:
    del layout_via_ast
    return apply_codegen_ast_rules(
        source,
        include_text_scaler=include_text_scaler,
    ).source


def _wrap_widget_on_pressed_with_gesture_detector(source: str, widget_name: str) -> str:
    return wrap_widget_on_pressed(source, widget_name)


def discover_widgets_requiring_on_pressed(sources: dict[str, str]) -> tuple[str, ...]:
    names: list[str] = []
    required = re.compile(
        r"required\s+(?:this\.)?onPressed\b|required\s+VoidCallback\s+onPressed\b"
    )
    widget_class = re.compile(
        r"class\s+(?P<name>\w+)\s+extends\s+(?:StatelessWidget|StatefulWidget)\b"
    )
    for path, content in sources.items():
        normalized = path.replace("\\", "/")
        if not normalized.startswith("lib/widgets/") or not normalized.endswith(".dart"):
            continue
        if required.search(content) is None:
            continue
        match = widget_class.search(content)
        if match is not None:
            names.append(match.group("name"))
    return tuple(dict.fromkeys(names))


def ensure_required_on_pressed_callbacks(
    source: str,
    *,
    widget_names: tuple[str, ...],
) -> str:
    return ensure_named_widgets_on_pressed(source, widget_names)


def normalize_llm_dart_string_escapes(source: str) -> str:
    return _run_rules(source, ("normalize_string_literals",))


def strip_bare_unicode_escapes_outside_literals(source: str) -> str:
    return _run_rules(source, ("strip_bare_unicode_escapes",))


def strip_invalid_dart_imports(source: str) -> str:
    return _run_rules(source, ("sanitize_imports",))


def strip_embedded_auto_generated_markers(source: str) -> str:
    return _run_rules(source, ("sanitize_imports",))


def ensure_base_screen_imports(source: str) -> str:
    return _run_rules(source, ("sanitize_imports",))


def _ensure_flutter_gestures_import(source: str) -> str:
    return ensure_base_screen_imports(source)


def ensure_app_colors_import(source: str, *, package_name: str = "demo_app") -> str:
    del package_name
    return _run_rules(source, ("sanitize_imports",))


def fix_llm_dart_api_mistakes(
    source: str,
    *,
    apply_layout_strips: bool = False,
    apply_llm_widget_repairs: bool = True,
) -> str:
    del apply_layout_strips, apply_llm_widget_repairs
    return fix_text_style_height_as_ratio(_run_rules(source, ("fix_llm_api_mistakes",)))


def fix_invalid_alignment_literals(source: str) -> str:
    return _run_rules(source, ("fix_alignment_literals",))


def fix_misused_text_align_widget(source: str) -> str:
    return _run_rules(source, ("fix_llm_api_mistakes",))


def fix_misused_transform_origin_alignment(source: str) -> str:
    return _run_rules(source, ("fix_llm_api_mistakes",))


def ensure_bordered_box_decoration_fill(source: str) -> str:
    return _run_rules(source, ("fix_llm_api_mistakes",))


def ensure_outlined_button_opaque_fill(source: str) -> str:
    return _run_rules(source, ("fix_llm_api_mistakes",))


def wrap_bare_inkwell_with_material(source: str) -> str:
    return _run_rules(source, ("fix_llm_api_mistakes",))


def wrap_bare_textfield_with_material(source: str) -> str:
    return _run_rules(source, ("fix_llm_api_mistakes",))


def strip_design_canvas_gesture_matryoshka(source: str) -> str:
    return _run_rules(source, ("strip_design_canvas_gesture_matryoshka",))


def strip_llm_viewport_scale_hack(source: str) -> str:
    return _run_rules(source, ("strip_viewport_scale_transform",))


def strip_llm_responsive_layout_builder(source: str) -> str:
    return _run_rules(source, ("unwrap_scale_layout_builder",))


def unscale_design_expressions(source: str) -> str:
    from figma_flutter_agent.generator.dart.unscale import unscale_design_expressions as _unscale

    return _unscale(source)


def repair_orphan_design_canvas_identifiers(source: str) -> str:
    from figma_flutter_agent.generator.dart.unscale import (
        repair_orphan_design_canvas_identifiers as _repair,
    )

    return _repair(source)


def strip_named_parameter(source: str, param_name: str) -> str:
    from figma_flutter_agent.generator.dart.postprocess_params import (
        strip_named_parameter as _strip,
    )

    return _strip(source, param_name)


def fix_malformed_closure_syntax(source: str) -> str:
    return _run_rules(source, ("fix_llm_api_mistakes",))
