"""Screen code sanitization and validation utilities."""

from __future__ import annotations

import re
from collections.abc import Callable

from loguru import logger

from figma_flutter_agent.errors import GenerationError

from .delimiters import (
    _find_class_body_open_brace,
    _skip_dart_string,
    repair_dart_delimiters,
    validate_dart_delimiters,
)

_LEADING_DART_DIRECTIVE_RE = re.compile(r"^(?:import|export|part|part of)\s+")
_GENERATED_SCREEN_SHELL_CLASS_RE = re.compile(
    r"class\s+GeneratedScreenShell\s+extends\s+StatelessWidget\s*\{",
    re.MULTILINE,
)
_WIDGET_CLASS_RE = re.compile(
    r"\bclass\s+(?P<name>(?!GeneratedScreenShell\b)\w+)\s+extends\s+(?P<kind>StatelessWidget|StatefulWidget)\b"
)
_PASCAL_CASE_NAME_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")

_GESTURE_DETECTOR_PARAM_FIXES: dict[str, str] = {
    "horizontalDragStart": "onHorizontalDragStart",
    "horizontalDragUpdate": "onHorizontalDragUpdate",
    "horizontalDragEnd": "onHorizontalDragEnd",
    "verticalDragStart": "onVerticalDragStart",
    "verticalDragUpdate": "onVerticalDragUpdate",
    "verticalDragEnd": "onVerticalDragEnd",
    "panStart": "onPanStart",
    "panUpdate": "onPanUpdate",
    "panEnd": "onPanEnd",
}


def fix_llm_gesture_detector_param_names(source: str) -> str:
    """Map LLM ``GestureDetector`` callback names to Flutter ``on*`` parameters."""
    updated = source
    for wrong, right in _GESTURE_DETECTOR_PARAM_FIXES.items():
        updated = re.sub(rf"\b{re.escape(wrong)}\s*:", f"{right}:", updated)
    return updated


def sanitize_llm_screen_code(
    source: str,
    *,
    strip_generated_shell_class: bool = False,
) -> str:
    """Normalize LLM ``screenCode`` before embedding it in ``screen.dart.j2``.

    Args:
        source: Raw ``screenCode`` from structured LLM output.
        strip_generated_shell_class: When True, remove a duplicate
            ``GeneratedScreenShell`` class because the screen template injects it.

    Returns:
        Sanitized Dart class declaration(s) ready for templating.
    """
    updated = _strip_leading_imports(source.strip())
    if strip_generated_shell_class:
        updated = _strip_generated_screen_shell_class(updated)
    from figma_flutter_agent.generator.dart.postprocess import (
        normalize_llm_dart_string_escapes,
        strip_embedded_auto_generated_markers,
        strip_invalid_dart_imports,
    )
    from figma_flutter_agent.generator.planned.reconcile import (
        strip_llm_relative_widget_imports,
    )

    updated = strip_embedded_auto_generated_markers(updated)
    updated = strip_llm_relative_widget_imports(updated)
    updated = normalize_llm_dart_string_escapes(updated)
    updated = strip_invalid_dart_imports(updated)
    # _strip_all_directive_lines runs last: AST sanitize_imports may re-add
    # a flutter import; strip it so the template (which owns imports) stays clean.
    updated = _strip_all_directive_lines(updated)
    return updated.strip()


def normalize_llm_screen_class_name(source: str, expected_class: str) -> str:
    """Rename the primary LLM screen widget class to match routing/bootstrap.

    Args:
        source: Sanitized ``screenCode`` fragment.
        expected_class: Canonical screen class (for example ``MusicV2Screen``).

    Returns:
        Dart source with the primary widget class renamed when needed.
    """
    match = _WIDGET_CLASS_RE.search(source)
    if match is None:
        return source
    actual_class = match.group("name")
    if actual_class == expected_class:
        return source
    updated = _rename_dart_identifier(source, actual_class, expected_class)
    if match.group("kind") == "StatefulWidget":
        state_old = f"_{actual_class}State"
        state_new = f"_{expected_class}State"
        if state_old in updated:
            updated = _rename_dart_identifier(updated, state_old, state_new)
    logger.info(
        "Renamed LLM screen class {} to {}",
        actual_class,
        expected_class,
    )
    return updated


def _rename_dart_identifier(source: str | None, old_name: str, new_name: str) -> str:
    if old_name == new_name or not source:
        return source or ""
    return re.sub(rf"\b{re.escape(old_name)}\b", new_name, source)


def apply_safe_screen_code_patch(
    screen_code: str,
    patch: Callable[[str], str],
    *,
    label: str,
) -> str:
    """Apply a screen transform and revert when it breaks Dart delimiter balance."""
    updated = patch(screen_code)
    if updated == screen_code:
        return screen_code
    if validate_dart_delimiters(updated) is None:
        return updated
    repaired = repair_dart_delimiters(updated)
    if validate_dart_delimiters(repaired) is None:
        logger.warning(
            "{} broke Dart delimiters; keeping delimiter-repaired patch",
            label,
        )
        return repaired
    logger.warning(
        "{} broke Dart delimiters ({}); keeping prior screenCode",
        label,
        validate_dart_delimiters(updated),
    )
    return screen_code


def _minimal_stateless_widget_stub(class_name: str) -> str:
    return (
        f"class {class_name} extends StatelessWidget {{\n"
        f"  const {class_name}({{super.key}});\n\n"
        "  @override\n"
        "  Widget build(BuildContext context) {\n"
        "    return const SizedBox.shrink();\n"
        "  }\n"
        "}\n"
    )


def _layout_delegation_screen_stub(
    class_name: str,
    layout_class: str,
    *,
    responsive_enabled: bool,
) -> str:
    body = (
        f"GeneratedScreenShell(child: const {layout_class}())"
        if responsive_enabled
        else f"const {layout_class}()"
    )
    return (
        f"class {class_name} extends StatelessWidget {{\n"
        f"  const {class_name}({{super.key}});\n\n"
        "  @override\n"
        "  Widget build(BuildContext context) {\n"
        f"    return {body};\n"
        "  }\n"
        "}\n"
    )


def _is_valid_dart_public_type_name(name: str) -> bool:
    return bool(name) and name[0].isalpha() and name.isidentifier()


def _resolve_screen_class_name(source: str, expected_screen_class: str | None) -> str:
    if expected_screen_class:
        return expected_screen_class
    match = _WIDGET_CLASS_RE.search(source)
    if match is not None:
        actual = match.group("name")
        if _is_valid_dart_public_type_name(actual):
            return actual
    return "GeneratedScreen"


def ensure_valid_llm_screen_code(
    source: str,
    *,
    strip_generated_shell_class: bool = False,
    expected_screen_class: str | None = None,
    layout_class: str | None = None,
    responsive_enabled: bool = False,
    quiet_expected_fallback: bool = False,
) -> str:
    """Sanitize LLM screen code; repair delimiters or fall back to a minimal stub.

    Args:
        source: Raw ``screenCode`` from structured LLM output.
        strip_generated_shell_class: When True, remove duplicate shell class defs.
        expected_screen_class: When set, rename the primary widget class to this name.

    Returns:
        Sanitized Dart source.
    """
    from .positioned import fix_invalid_positioned_constraints
    from .widgets import dedupe_primary_widget_class

    sanitized = _ensure_valid_llm_dart_code(
        source,
        artifact="screen_code",
        strip_generated_shell_class=strip_generated_shell_class,
        strict=False,
    )
    repaired = repair_dart_delimiters(sanitized)
    if repaired != sanitized:
        logger.info("Repaired Dart delimiters in LLM screen_code")
        sanitized = repaired
    from figma_flutter_agent.generator.planned.reconcile import sanitize_screen_emit_syntax

    sanitized = sanitize_screen_emit_syntax(sanitized)
    if validate_dart_delimiters(sanitized) is not None or _WIDGET_CLASS_RE.search(sanitized) is None:
        class_name = _resolve_screen_class_name(sanitized, expected_screen_class)
        if layout_class:
            log_fn = logger.info if quiet_expected_fallback else logger.warning
            log_fn(
                "Replacing unrepairable LLM screen_code with deterministic {} wrapper",
                layout_class,
            )
            sanitized = _layout_delegation_screen_stub(
                class_name,
                layout_class,
                responsive_enabled=responsive_enabled,
            )
        else:
            logger.warning(
                "Replacing unrepairable LLM screen_code with minimal {} placeholder",
                class_name,
            )
            sanitized = _minimal_stateless_widget_stub(class_name)
    if expected_screen_class:
        sanitized = normalize_llm_screen_class_name(sanitized, expected_screen_class)
        sanitized = dedupe_primary_widget_class(sanitized, expected_screen_class)
    return fix_invalid_positioned_constraints(sanitized)


def _ensure_valid_llm_dart_code(
    source: str,
    *,
    artifact: str,
    strip_generated_shell_class: bool = False,
    strict: bool,
) -> str:
    sanitized = sanitize_llm_screen_code(
        source,
        strip_generated_shell_class=strip_generated_shell_class,
    )
    from figma_flutter_agent.generator.dart.postprocess import fix_malformed_closure_syntax

    sanitized = fix_malformed_closure_syntax(sanitized)
    delimiter_error = validate_dart_delimiters(sanitized)
    if delimiter_error is None:
        return sanitized

    message = f"LLM {artifact} has invalid Dart syntax: {delimiter_error}"
    if strict:
        raise GenerationError(message)
    logger.warning(message)
    return sanitized


def _strip_leading_imports(source: str) -> str:
    lines = source.splitlines()
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped:
            index += 1
            continue
        if _LEADING_DART_DIRECTIVE_RE.match(stripped):
            index += 1
            continue
        break
    return "\n".join(lines[index:])


def _strip_all_directive_lines(source: str) -> str:
    """Remove ``import``/``export`` lines LLMs embed inside ``screenCode`` (template owns imports)."""
    kept: list[str] = []
    for line in source.splitlines():
        stripped = line.strip()
        if stripped and _LEADING_DART_DIRECTIVE_RE.match(stripped):
            continue
        kept.append(line)
    return "\n".join(kept)


def _strip_generated_screen_shell_class(source: str) -> str:
    match = _GENERATED_SCREEN_SHELL_CLASS_RE.search(source)
    if match is None:
        return source

    open_brace = _find_class_body_open_brace(source, match.end())
    if open_brace is None:
        open_brace = source.find("{", match.start())
    if open_brace < 0:
        return source

    close_brace = _find_matching_brace(source, open_brace)
    if close_brace is None:
        return source

    return (source[: match.start()] + source[close_brace + 1 :]).strip()


def _find_matching_brace(source: str, open_index: int) -> int | None:
    if open_index >= len(source) or source[open_index] != "{":
        return None

    depth = 0
    index = open_index
    length = len(source)

    while index < length:
        char = source[index]
        if char == "\n":
            index += 1
            continue

        if char == "/" and index + 1 < length:
            next_char = source[index + 1]
            if next_char == "/":
                index += 2
                while index < length and source[index] != "\n":
                    index += 1
                continue
            if next_char == "*":
                index += 2
                while index + 1 < length:
                    if source[index] == "*" and source[index + 1] == "/":
                        index += 2
                        break
                    index += 1
                else:
                    return None
                continue

        if char == "r" and index + 1 < length and source[index + 1] in {"'", '"'}:
            index = _skip_dart_string(source, index + 1)
            continue

        if char in {"'", '"'}:
            index = _skip_dart_string(source, index)
            continue

        if char == "{":
            depth += 1
            index += 1
            continue
        if char == "}":
            depth -= 1
            index += 1
            if depth == 0:
                return index - 1
            continue
        index += 1
    return None
