"""Sanitize and validate raw LLM Dart fragments before templating."""

from __future__ import annotations

import re
from collections.abc import Callable

from loguru import logger

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.dart.delimiters import (
    find_matching_paren as _find_matching_paren,
)
from figma_flutter_agent.generator.layout.common import (
    to_pascal_case,
    to_snake_case,
)
from figma_flutter_agent.generator.layout.style import (
    dart_color_expr,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_LEADING_DART_DIRECTIVE_RE = re.compile(r"^(?:import|export|part|part of)\s+")
_GENERATED_SCREEN_SHELL_CLASS_RE = re.compile(
    r"class\s+GeneratedScreenShell\s+extends\s+StatelessWidget\s*\{",
    re.MULTILINE,
)
_WIDGET_CLASS_RE = re.compile(
    r"\bclass\s+(?P<name>(?!GeneratedScreenShell\b)\w+)\s+extends\s+(?P<kind>StatelessWidget|StatefulWidget)\b"
)
_PASCAL_CASE_NAME_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")
_COPY_WIDTH_METRIC_SLACK = 1.06

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


def _canonical_widget_class_name(
    widget_name: str,
    *,
    declared_class: str | None = None,
) -> str:
    """Return a public PascalCase widget class name."""
    stripped = widget_name.strip()
    canonical = stripped if _PASCAL_CASE_NAME_RE.fullmatch(stripped) else to_pascal_case(stripped)
    if declared_class and declared_class.startswith("_") and len(declared_class) > 1:
        derived = declared_class[1:]
        if _PASCAL_CASE_NAME_RE.fullmatch(derived) and (
            not _PASCAL_CASE_NAME_RE.fullmatch(stripped)
            or canonical.lower() == derived.lower()
        ):
            return derived
    return canonical


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
    from figma_flutter_agent.generator.planned_dart import (
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


def validate_dart_delimiters(source: str) -> str | None:
    """Return a human-readable error when brackets/parens/braces are unbalanced.

    Skips Dart comments and string literals so braces inside them do not affect
    the structural balance check.

    Args:
        source: Dart source fragment to inspect.

    Returns:
        Error message, or ``None`` when delimiters balance.
    """
    stack: list[tuple[str, int]] = []
    pairs = {"(": ")", "[": "]", "{": "}"}
    closing = {")": "(", "]": "[", "}": "{"}
    line_number = 1
    index = 0
    length = len(source)

    while index < length:
        char = source[index]
        if char == "\n":
            line_number += 1
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
                    if source[index] == "\n":
                        line_number += 1
                    index += 1
                else:
                    index = length
                continue

        if char == "r" and index + 1 < length and source[index + 1] in {"'", '"'}:
            index = _skip_dart_string(source, index + 1)
            continue

        if char in {"'", '"'}:
            index = _skip_dart_string(source, index)
            continue

        if char in pairs:
            stack.append((char, line_number))
            index += 1
            continue

        if char in closing:
            if not stack or stack[-1][0] != closing[char]:
                return f"Unexpected '{char}' near line {line_number}"
            stack.pop()
            index += 1
            continue

        index += 1

    if stack:
        opener, opener_line = stack[-1]
        return f"Unclosed '{opener}' opened near line {opener_line}"

    return None


def _dart_delimiter_stack(source: str) -> list[str] | None:
    """Return unmatched open delimiters, or ``None`` when closers are invalid."""
    stack: list[str] = []
    pairs = {"(": ")", "[": "]", "{": "}"}
    closing = {")": "(", "]": "[", "}": "{"}
    index = 0
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
                    index = length
                continue

        if char == "r" and index + 1 < length and source[index + 1] in {"'", '"'}:
            index = _skip_dart_string(source, index + 1)
            continue

        if char in {"'", '"'}:
            index = _skip_dart_string(source, index)
            continue

        if char in pairs:
            stack.append(char)
            index += 1
            continue

        if char in closing:
            if not stack or stack[-1] != closing[char]:
                return None
            stack.pop()
            index += 1
            continue

        index += 1

    return stack


def balance_dart_delimiters(source: str) -> str | None:
    """Append missing ``)`` / ``]`` / ``}`` when the fragment only lacks closers.

    Args:
        source: Dart source fragment.

    Returns:
        Balanced source, or ``None`` when unexpected closers make auto-fix unsafe.
    """
    stack = _dart_delimiter_stack(source)
    if stack is None:
        return None
    if not stack:
        return source
    pairs = {"(": ")", "[": "]", "{": "}"}
    suffix = "".join(pairs[opener] for opener in reversed(stack))
    return f"{source.rstrip()}\n{suffix}\n"


def trim_surplus_dart_delimiters(source: str) -> str | None:
    """Drop stray ``)`` / ``]`` / ``}`` that do not match an opener.

    Args:
        source: Dart source fragment.

    Returns:
        Filtered source, or ``None`` when the scan cannot proceed safely.
    """
    pairs = {"(": ")", "[": "]", "{": "}"}
    closing = {")": "(", "]": "[", "}": "{"}
    stack: list[str] = []
    parts: list[str] = []
    index = 0
    length = len(source)

    while index < length:
        char = source[index]
        if char == "\n":
            parts.append(char)
            index += 1
            continue

        if char == "/" and index + 1 < length:
            next_char = source[index + 1]
            if next_char == "/":
                line_end = source.find("\n", index)
                if line_end == -1:
                    parts.append(source[index:])
                    break
                parts.append(source[index:line_end])
                index = line_end
                continue
            if next_char == "*":
                block_end = index + 2
                while block_end + 1 < length:
                    if source[block_end] == "*" and source[block_end + 1] == "/":
                        block_end += 2
                        break
                    block_end += 1
                else:
                    block_end = length
                parts.append(source[index:block_end])
                index = block_end
                continue

        if char == "r" and index + 1 < length and source[index + 1] in {"'", '"'}:
            end = _skip_dart_string(source, index + 1)
            parts.append(source[index:end])
            index = end
            continue

        if char in {"'", '"'}:
            end = _skip_dart_string(source, index)
            parts.append(source[index:end])
            index = end
            continue

        if char in pairs:
            stack.append(char)
            parts.append(char)
            index += 1
            continue

        if char in closing:
            if stack and stack[-1] == closing[char]:
                stack.pop()
                parts.append(char)
            index += 1
            continue

        parts.append(char)
        index += 1

    return "".join(parts)


def repair_dart_delimiters(source: str) -> str:
    """Best-effort delimiter repair: append missing closers, then trim surplus."""
    if validate_dart_delimiters(source) is None:
        return source

    balanced = balance_dart_delimiters(source)
    candidate = balanced if balanced is not None else source
    if validate_dart_delimiters(candidate) is None:
        return candidate

    trimmed = trim_surplus_dart_delimiters(candidate)
    if trimmed is not None:
        if validate_dart_delimiters(trimmed) is None:
            return trimmed
        balanced_trimmed = balance_dart_delimiters(trimmed)
        if balanced_trimmed is not None and validate_dart_delimiters(balanced_trimmed) is None:
            return balanced_trimmed

    from figma_flutter_agent.generator.dart.syntax_repairs import (
        fix_garbage_closers_after_link_rich,
    )

    link_fixed = fix_garbage_closers_after_link_rich(candidate)
    if link_fixed != candidate and validate_dart_delimiters(link_fixed) is None:
        return link_fixed

    return source


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


def _resolve_screen_class_name(source: str, expected_screen_class: str | None) -> str:
    if expected_screen_class:
        return expected_screen_class
    match = _WIDGET_CLASS_RE.search(source)
    if match is not None:
        return match.group("name")
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
    from figma_flutter_agent.generator.planned_dart import sanitize_screen_emit_syntax

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


def normalize_llm_extracted_widget_code(
    source: str,
    *,
    widget_name: str,
) -> tuple[str, str, str]:
    """Rename extracted widget classes to the canonical public ``widgetName``.

    LLMs often emit private helpers (``class _CircleAction``) while the schema
    ``widgetName`` is public (``CircleAction``). Widget files must expose a
    public class so the screen can import and instantiate them.

    Args:
        source: Raw widget ``code`` from structured LLM output.
        widget_name: Canonical PascalCase widget identifier from the schema.

    Returns:
        Tuple of sanitized source, the original primary class name (if any), and
        the canonical public class name.
    """
    match = _WIDGET_CLASS_RE.search(source)
    if match is None:
        return source, "", _canonical_widget_class_name(widget_name)

    actual = match.group("name")
    canonical = _canonical_widget_class_name(widget_name, declared_class=actual)
    updated = source
    if actual != canonical:
        updated = _rename_dart_identifier(source, actual, canonical)
        if match.group("kind") == "StatefulWidget":
            state_old = (
                f"_{actual}State" if not actual.startswith("_") else f"{actual}State"
            )
            state_new = f"_{canonical}State"
            if state_old in updated and state_old != state_new:
                updated = _rename_dart_identifier(updated, state_old, state_new)
        logger.info(
            "Renamed LLM extracted widget class {} to {}",
            actual,
            canonical,
        )
    return updated, actual, canonical


def _collect_widget_class_renames(
    extracted_widgets: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Collect private-to-public renames declared in extracted widget sources."""
    renames: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(old_name: str, new_name: str) -> None:
        if not old_name or old_name == new_name:
            return
        key = (old_name, new_name)
        if key in seen:
            return
        seen.add(key)
        renames.append(key)

    for widget_name, widget_code in extracted_widgets:
        _, actual, canonical = normalize_llm_extracted_widget_code(
            widget_code,
            widget_name=widget_name,
        )
        if actual:
            add(actual, canonical)
        if canonical and not canonical.startswith("_"):
            add(f"_{canonical}", canonical)
        for match in _WIDGET_CLASS_RE.finditer(widget_code):
            declared = match.group("name")
            if declared.startswith("_") and len(declared) > 1:
                derived = declared[1:]
                if _PASCAL_CASE_NAME_RE.fullmatch(derived):
                    add(declared, derived)
            if declared.startswith("_") and declared != canonical:
                add(declared, canonical)
    return renames


def _apply_widget_class_renames(source: str | None, renames: list[tuple[str, str]]) -> str:
    if not source:
        return ""
    updated = source
    for old_name, new_name in renames:
        updated = _rename_dart_identifier(updated, old_name, new_name)
    return updated


def _assign_unique_widget_class_names(
    metadata: list[tuple[str, str, str, str]],
) -> list[tuple[str, str, str, str]]:
    """Ensure each extracted widget uses a distinct public class name."""
    used: set[str] = set()
    unique: list[tuple[str, str, str, str]] = []
    for widget_name, normalized, canonical, file_stem in metadata:
        class_name = canonical
        if class_name in used:
            suffix = 2
            while f"{canonical}{suffix}" in used:
                suffix += 1
            class_name = f"{canonical}{suffix}"
            normalized = _rename_dart_identifier(normalized, canonical, class_name)
            logger.info(
                "Renamed duplicate LLM extracted widget class {} to {}",
                canonical,
                class_name,
            )
        used.add(class_name)
        unique.append((widget_name, normalized, class_name, file_stem))
    return unique


def prepare_llm_extracted_widgets(
    extracted_widgets: list[tuple[str, str]],
) -> tuple[list[tuple[str, str]], dict[str, str]]:
    """Normalize extracted widget classes and reconcile cross-widget references.

    LLM widgets often reference each other with stale private class names or embed
    duplicate helper class declarations. This function renames classes to their
    schema ``widgetName`` values, propagates those names across all widget bodies,
    and removes duplicate class declarations from sibling widgets and screens.

    Args:
        extracted_widgets: ``(widgetName, widgetCode)`` pairs from the LLM.

    Returns:
        Tuple of reconciled ``(widgetName, widgetCode)`` pairs and a mapping of
        canonical widget class name to widget file stem (snake_case).
    """
    renames = _collect_widget_class_renames(extracted_widgets)
    metadata: list[tuple[str, str, str, str]] = []
    for widget_name, widget_code in extracted_widgets:
        normalized, _, canonical = normalize_llm_extracted_widget_code(
            widget_code,
            widget_name=widget_name,
        )
        metadata.append(
            (widget_name, normalized, canonical, to_snake_case(widget_name))
        )

    metadata = _assign_unique_widget_class_names(metadata)
    class_to_file = {canonical: file_stem for _, _, canonical, file_stem in metadata}
    reconciled: list[tuple[str, str]] = []
    for widget_name, normalized, canonical, _file_stem in metadata:
        updated = _apply_widget_class_renames(normalized, renames)
        for _, _, other_class, _ in metadata:
            if other_class != canonical:
                updated = _safe_strip_widget_class_definition(
                    updated,
                    other_class,
                    strip_state=True,
                )
        reconciled.append((widget_name, updated))
    return reconciled, class_to_file


def sibling_widget_import_uris(
    code: str,
    *,
    own_class: str,
    class_to_file: dict[str, str],
    uri_for_path: Callable[[str], str],
) -> list[str]:
    """Return import URIs for extracted sibling widgets referenced in ``code``.

    Args:
        code: Reconciled widget Dart source.
        own_class: Canonical class name declared in ``code``.
        class_to_file: Mapping of canonical widget class to widget file stem.
        uri_for_path: Callback that turns a project-relative path into an import URI.

    Returns:
        Sorted unique import URIs for referenced sibling widgets.
    """
    imports: list[str] = []
    for class_name, file_stem in sorted(class_to_file.items()):
        if class_name == own_class:
            continue
        if re.search(rf"\b{re.escape(class_name)}\s*\(", code):
            imports.append(uri_for_path(f"widgets/{file_stem}.dart"))
    return sorted(set(imports))


def reconcile_extracted_widget_references(
    screen_code: str | None,
    extracted_widgets: list[tuple[str, str]],
) -> str:
    """Rewrite screen code to reference public extracted widget class names.

    Args:
        screen_code: Raw ``screenCode`` from structured LLM output.
        extracted_widgets: ``(widgetName, widgetCode)`` pairs from the LLM.

    Returns:
        Screen Dart source with extracted widget identifiers reconciled.
    """
    if not screen_code:
        return ""
    renames = _collect_widget_class_renames(extracted_widgets)
    _, class_to_file = prepare_llm_extracted_widgets(extracted_widgets)
    updated = _apply_widget_class_renames(screen_code, renames)
    for class_name in class_to_file:
        updated = _safe_strip_widget_class_definition(
            updated,
            class_name,
            strip_state=False,
        )
    return updated


def reconcile_extracted_widget_references_in_planned(
    planned_files: dict[str, str],
    extracted_widgets: list[tuple[str, str]],
) -> dict[str, str]:
    """Reconcile widget class names in planned screen and layout Dart files."""
    if not extracted_widgets:
        return planned_files
    updated = dict(planned_files)
    for path, content in planned_files.items():
        if not path.endswith(".dart"):
            continue
        if path.startswith("lib/widgets/"):
            continue
        reconciled = reconcile_extracted_widget_references(content, extracted_widgets)
        if reconciled != content:
            updated[path] = reconciled
    return updated


def _safe_strip_widget_class_definition(
    source: str,
    class_name: str,
    *,
    strip_state: bool,
) -> str:
    """Strip a duplicate widget class unless doing so would break Dart delimiters."""
    candidate = _strip_widget_class_definition(
        source,
        class_name,
        strip_state=strip_state,
    )
    if candidate == source or validate_dart_delimiters(candidate) is None:
        return candidate
    logger.warning(
        "Skipping widget class strip for {} because it would break Dart delimiters",
        class_name,
    )
    return source


def _strip_widget_class_definition(
    source: str,
    class_name: str,
    *,
    strip_state: bool = True,
) -> str:
    """Remove a duplicate widget class (and optionally its State) from Dart source."""
    if not class_name:
        return source
    match = re.search(
        rf"class\s+{re.escape(class_name)}\s+extends\s+(?:StatelessWidget|StatefulWidget)(?:<[^>]*>)?",
        source,
        re.MULTILINE,
    )
    if match is None:
        return source
    return _strip_widget_class_at(
        source,
        match.start(),
        class_name,
        strip_state=strip_state,
    )


def _strip_class_definition(
    source: str, class_name: str, extends_names: tuple[str, ...]
) -> str:
    extends_pattern = "|".join(re.escape(name) for name in extends_names)
    match = re.search(
        rf"class\s+{re.escape(class_name)}\s+extends\s+(?:{extends_pattern})(?:<[^>]*>)?",
        source,
        re.MULTILINE,
    )
    if match is None:
        return source
    return _strip_widget_class_at(
        source,
        match.start(),
        class_name,
        extends_names=extends_names,
        strip_state=False,
    )


def _strip_widget_class_at(
    source: str,
    class_start: int,
    class_name: str,
    *,
    extends_names: tuple[str, ...] = ("StatelessWidget", "StatefulWidget"),
    strip_state: bool = False,
) -> str:
    """Remove one widget class definition starting at ``class_start``."""
    if not class_name or class_start < 0 or class_start >= len(source):
        return source
    extends_pattern = "|".join(re.escape(name) for name in extends_names)
    header_match = re.match(
        rf"class\s+{re.escape(class_name)}\s+extends\s+(?:{extends_pattern})(?:<[^>]*>)?",
        source[class_start:],
    )
    if header_match is None:
        return source
    header_end = class_start + header_match.end()
    open_brace = _find_class_body_open_brace(source, header_end)
    if open_brace is None:
        return source
    close_brace = _find_matching_brace(source, open_brace)
    if close_brace is None:
        return source
    updated = source[:class_start] + source[close_brace + 1 :]
    if strip_state:
        updated = _strip_immediately_following_state_class(
            updated, class_start, class_name
        )
    return updated


def _strip_immediately_following_state_class(
    source: str,
    after_index: int,
    class_name: str,
) -> str:
    """Remove a ``State`` helper only when it directly follows the removed widget class."""
    state_name = f"_{class_name}State"
    tail = source[after_index:]
    state_match = re.match(
        rf"\s*class\s+{re.escape(state_name)}\s+extends\s+State(?:<[^>]*>)?",
        tail,
        re.MULTILINE,
    )
    if state_match is None:
        return source
    state_start = after_index + state_match.start()
    class_index = source.find("class", state_start)
    if class_index < 0:
        return source
    return _strip_widget_class_at(
        source,
        class_index,
        state_name,
        extends_names=("State",),
        strip_state=False,
    )


def dedupe_primary_widget_class(source: str, class_name: str) -> str:
    """Keep the first screen/widget class declaration and drop later duplicates."""
    pattern = re.compile(
        rf"class\s+{re.escape(class_name)}\s+extends\s+(?:StatelessWidget|StatefulWidget)",
        re.MULTILINE,
    )
    matches = list(pattern.finditer(source))
    if len(matches) <= 1:
        return source
    updated = source
    for match in reversed(matches[1:]):
        updated = _strip_widget_class_at(
            updated,
            match.start(),
            class_name,
            strip_state=True,
        )
    logger.info(
        "Removed {} duplicate {} class definition(s)",
        len(matches) - 1,
        class_name,
    )
    return updated


_CLASS_MEMBER_PREFIXES = (
    "const ",
    "final ",
    "var ",
    "@override",
    "@",
    "Widget ",
    "void ",
)


def _find_class_body_open_brace(source: str, header_index: int) -> int | None:
    """Return the ``{`` that opens a class body after the ``extends`` clause."""
    index = header_index
    length = len(source)
    generic_depth = 0

    while index < length:
        char = source[index]
        if char in " \t\r\n":
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

        if generic_depth == 0 and char == "{":
            return index
        if char == "<":
            generic_depth += 1
            index += 1
            continue
        if char == ">":
            generic_depth = max(0, generic_depth - 1)
            index += 1
            continue
        if generic_depth == 0:
            if source.startswith("implements", index) or source.startswith(
                "with", index
            ):
                index += 1
                continue
            if any(
                source.startswith(prefix, index) for prefix in _CLASS_MEMBER_PREFIXES
            ):
                return None
        if char.isalpha() or char == "_" or char in {",", "."}:
            index += 1
            continue
        if generic_depth == 0:
            return None
        index += 1
    return None


def ensure_valid_llm_widget_code(source: str, *, widget_name: str = "widget") -> str:
    """Sanitize extracted LLM widget code before templating.

    Widget fragments with only missing closing delimiters are auto-balanced; otherwise
    a minimal ``SizedBox`` placeholder is emitted so analyze/write can proceed.

    Args:
        source: Raw widget ``code`` from structured LLM output.
        widget_name: Widget identifier for log context.

    Returns:
        Sanitized Dart source.
    """
    sanitized = _ensure_valid_llm_dart_code(
        source,
        artifact=f"widget {widget_name}",
        strict=False,
    )
    repaired = repair_dart_delimiters(sanitized)
    if repaired != sanitized:
        logger.info("Repaired Dart delimiters for LLM widget {}", widget_name)
        sanitized = repaired
    if validate_dart_delimiters(sanitized) is not None:
        canonical = _canonical_widget_class_name(widget_name)
        logger.warning(
            "Replacing unrepairable LLM widget {} with SizedBox placeholder",
            widget_name,
        )
        sanitized = _minimal_stateless_widget_stub(canonical)
    normalized, _, _ = normalize_llm_extracted_widget_code(
        sanitized,
        widget_name=widget_name,
    )
    return normalized


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


def _skip_dart_string(source: str, start: int) -> int:
    """Return the index after a Dart string literal starting at ``start``."""
    if start >= len(source):
        return start

    quote = source[start]
    if quote not in {"'", '"'}:
        return start

    triple = start + 2 < len(source) and source[start : start + 3] == quote * 3
    if triple:
        end_marker = quote * 3
        index = start + 3
        while index + 2 < len(source):
            if source[index : index + 3] == end_marker:
                return index + 3
            index += 1
        return len(source)

    index = start + 1
    while index < len(source):
        char = source[index]
        if char == "\\":
            index += 2
            continue
        if char == quote:
            return index + 1
        index += 1
    return len(source)


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


def _collect_text_nodes(root: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    nodes: list[CleanDesignTreeNode] = []
    if root.type == NodeType.TEXT and root.text:
        nodes.append(root)
    for child in root.children:
        nodes.extend(_collect_text_nodes(child))
    return nodes


def _collect_all_nodes(root: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    nodes = [root]
    for child in root.children:
        nodes.extend(_collect_all_nodes(child))
    return nodes


def _find_parent_node(root: CleanDesignTreeNode, node_id: str) -> CleanDesignTreeNode | None:
    for child in root.children:
        if child.id == node_id:
            return root
        found = _find_parent_node(child, node_id)
        if found is not None:
            return found
    return None


def _node_has_multiline_copy(node: CleanDesignTreeNode) -> bool:
    if node.type == NodeType.TEXT and node.text:
        return "\n" in sanitize_figma_display_text(node.text)
    return any(_node_has_multiline_copy(child) for child in node.children)


def _copy_layout_width_for_metrics(figma_width: float) -> float:
    """Add slack so Flutter font metrics do not clip Figma-sized copy blocks."""
    slack_width = figma_width * _COPY_WIDTH_METRIC_SLACK
    return (
        round(slack_width, 1)
        if slack_width != int(slack_width)
        else float(int(slack_width))
    )


def _multiline_copy_column_width_from_tree(
    clean_tree: CleanDesignTreeNode,
) -> float | None:
    """Pick the Figma column width for copy blocks that contain intentional line breaks."""
    widths: list[float] = []
    for node in _collect_all_nodes(clean_tree):
        if node.type == NodeType.TEXT and node.text:
            sanitized = sanitize_figma_display_text(node.text)
            if "\n" in sanitized and node.sizing.width:
                widths.append(node.sizing.width)
        placement = node.stack_placement
        if placement is not None and placement.width and _node_has_multiline_copy(node):
            widths.append(placement.width)
    return max(widths) if widths else None


def _strip_positioned_height_from_block(block: str) -> str:
    return re.sub(
        r"(\n\s*)height:\s*[\d.]+,?\s*(?=\n\s*child:)",
        r"\1",
        block,
        count=1,
    )


def _positioned_has_edge(block: str, edge: str) -> bool:
    return re.search(rf"\b{edge}:\s*[\d.]+", block) is not None


def _drop_positioned_dimension(block: str, dimension: str) -> str:
    """Remove one ``width``/``height`` field from a ``Positioned`` argument list."""
    updated = re.sub(rf"\n\s*{dimension}:\s*[\d.]+,?\s*", "\n", block, count=1)
    if updated == block:
        updated = re.sub(rf",\s*{dimension}:\s*[\d.]+", "", block, count=1)
    return updated


def _normalize_positioned_block_constraints(block: str) -> str:
    """Drop ``width``/``height`` when opposing edges are also set (Flutter asserts)."""
    updated = block
    if (
        _positioned_has_edge(block, "left")
        and _positioned_has_edge(block, "right")
        and _positioned_has_edge(block, "width")
    ):
        updated = _drop_positioned_dimension(updated, "width")
    if (
        _positioned_has_edge(updated, "top")
        and _positioned_has_edge(updated, "bottom")
        and _positioned_has_edge(updated, "height")
    ):
        updated = _drop_positioned_dimension(updated, "height")
    return updated


def _format_layout_dimension(value: float) -> str:
    from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal

    return format_geometry_literal(value)


def _find_enclosing_positioned_span(screen_code: str, anchor: int) -> tuple[int, int] | None:
    pos_start = screen_code.rfind("Positioned(", 0, anchor)
    if pos_start == -1:
        return None
    paren_start = pos_start + len("Positioned")
    paren_end = _find_matching_paren(screen_code, paren_start)
    if paren_end is None:
        return None
    return pos_start, paren_end + 1


def _insert_positioned_size_fields(
    block: str,
    *,
    width: float | None = None,
    height: float | None = None,
) -> str:
    """Add missing ``width``/``height`` pins on a ``Positioned`` from Figma frame size."""
    insert_parts: list[str] = []
    if width is not None and not _positioned_has_edge(block, "width"):
        insert_parts.append(f"width: {_format_layout_dimension(width)},")
    if height is not None and not _positioned_has_edge(block, "height"):
        insert_parts.append(f"height: {_format_layout_dimension(height)},")
    if not insert_parts:
        return block
    insert = "\n                      ".join(insert_parts) + "\n                      "
    top_match = re.search(r"top:\s*[\d.]+,?\s*\n\s*", block)
    if top_match is not None:
        pos = top_match.end()
        return block[:pos] + insert + block[pos:]
    left_match = re.search(r"left:\s*[\d.]+,?\s*\n\s*", block)
    if left_match is not None:
        pos = left_match.end()
        return block[:pos] + insert + block[pos:]
    child_match = re.search(r"\n(\s*)child:", block)
    if child_match is not None:
        pos = child_match.start() + 1
        return block[:pos] + insert + block[pos:]
    return block


def fix_positioned_stack_bounds_from_tree(
    screen_code: str,
    clean_tree: CleanDesignTreeNode,
) -> str:
    """Pin ``Positioned`` width/height from Figma for every keyed absolute child.

    LLM screen bodies often emit ``Positioned(left, top)`` without explicit frame
    size even when ``stackPlacement`` / ``sizing`` provide it, which breaks golden
    capture (unbounded ``Stack`` hosts).

    Args:
        screen_code: Sanitized LLM ``screenCode`` fragment.
        clean_tree: Parsed design tree with ``stackPlacement`` metadata.

    Returns:
        Dart source with bounded ``Positioned`` hosts where Figma provides sizes.
    """
    from figma_flutter_agent.generator.layout.widget import figma_positioned_dimensions

    bounds_by_id: dict[str, tuple[float | None, float | None]] = {}

    def walk(node: CleanDesignTreeNode) -> None:
        width, height = figma_positioned_dimensions(node)
        if width is not None or height is not None:
            bounds_by_id[node.id] = (width, height)
        for child in node.children:
            walk(child)

    walk(clean_tree)
    if not bounds_by_id:
        return screen_code

    replacements: dict[int, tuple[int, str]] = {}
    for node_id, (width, height) in bounds_by_id.items():
        if width is None and height is None:
            continue
        tokens = {node_id, node_id.replace(":", "_")}
        for token in tokens:
            pattern = f"figma-{token}"
            anchor = screen_code.find(pattern)
            if anchor == -1:
                continue
            span = _find_enclosing_positioned_span(screen_code, anchor)
            if span is None:
                continue
            start, end = span
            block = screen_code[start:end]
            patched = _insert_positioned_size_fields(block, width=width, height=height)
            if patched != block:
                replacements[start] = (end, patched)
            break

    updated = screen_code
    for start in sorted(replacements, reverse=True):
        end, patched = replacements[start]
        updated = updated[:start] + patched + updated[end:]
    return updated


def fix_invalid_positioned_constraints(screen_code: str) -> str:
    """Remove illegal ``Positioned`` dimension combinations across ``screenCode``."""
    replacements: list[tuple[int, int, str]] = []
    index = 0
    while True:
        start = screen_code.find("Positioned(", index)
        if start == -1:
            break
        paren_start = start + len("Positioned")
        paren_end = _find_matching_paren(screen_code, paren_start)
        if paren_end is None:
            break
        block = screen_code[start : paren_end + 1]
        index = paren_end + 1
        normalized = _normalize_positioned_block_constraints(block)
        if normalized != block:
            replacements.append((start, paren_end + 1, normalized))
    for start, end, patched_block in reversed(replacements):
        screen_code = screen_code[:start] + patched_block + screen_code[end:]
    return screen_code


def _patch_multiline_copy_column_width(screen_code: str, width: float) -> str:
    """Widen the Positioned Column that hosts multiline marketing copy."""
    layout_width = _copy_layout_width_for_metrics(width)
    width_token = (
        f"{int(layout_width)}"
        if layout_width == int(layout_width)
        else f"{layout_width:g}"
    )
    replacements: list[tuple[int, int, str]] = []
    index = 0
    while True:
        start = screen_code.find("Positioned(", index)
        if start == -1:
            break
        paren_start = start + len("Positioned")
        paren_end = _find_matching_paren(screen_code, paren_start)
        if paren_end is None:
            break
        block = screen_code[start : paren_end + 1]
        index = paren_end + 1
        if "Column(" not in block:
            continue
        if not _node_has_multiline_copy_in_dart_block(block):
            continue
        if _positioned_has_edge(block, "right"):
            patched_block = _normalize_positioned_block_constraints(block)
            patched_block = _strip_positioned_height_from_block(patched_block)
            if patched_block != block:
                replacements.append((start, paren_end + 1, patched_block))
            continue
        if re.search(r"width:\s*[\d.]+", block):
            patched_block = re.sub(
                r"width:\s*[\d.]+", f"width: {width_token}", block, count=1
            )
        else:
            left_match = re.search(r"left:\s*([\d.]+)(?:\.0)?,\s*", block)
            if left_match is None:
                continue
            patched_block = re.sub(
                left_match.group(0),
                f"{left_match.group(0)}width: {width_token},\n                        ",
                block,
                count=1,
            )
        patched_block = _strip_positioned_height_from_block(patched_block)
        replacements.append((start, paren_end + 1, patched_block))
    for start, end, patched_block in reversed(replacements):
        screen_code = screen_code[:start] + patched_block + screen_code[end:]
    return screen_code


def _strip_multiline_copy_positioned_heights(screen_code: str) -> str:
    """Drop rigid Positioned heights on copy blocks (LLM often adds them back)."""
    replacements: list[tuple[int, int, str]] = []
    index = 0
    while True:
        start = screen_code.find("Positioned(", index)
        if start == -1:
            break
        paren_start = start + len("Positioned")
        paren_end = _find_matching_paren(screen_code, paren_start)
        if paren_end is None:
            break
        block = screen_code[start : paren_end + 1]
        index = paren_end + 1
        if "Column(" not in block or not _node_has_multiline_copy_in_dart_block(block):
            continue
        if not re.search(r"height:\s*[\d.]+", block):
            continue
        replacements.append(
            (start, paren_end + 1, _strip_positioned_height_from_block(block))
        )
    for start, end, patched_block in reversed(replacements):
        screen_code = screen_code[:start] + patched_block + screen_code[end:]
    return screen_code


def _node_has_multiline_copy_in_dart_block(block: str) -> bool:
    for _, _, body in _iter_dart_string_literals(block):
        decoded = _decode_dart_string_literal_content(body)
        if "\n" in sanitize_figma_display_text(decoded):
            return True
    if block.count("maxLines: 1") >= 2:
        return True
    return (
        block.count("softWrap: false") >= 2
        and "mainAxisSize: MainAxisSize.min" in block
    )


def _first_text_descendant(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    if node.type == NodeType.TEXT and node.text:
        return node
    for child in node.children:
        found = _first_text_descendant(child)
        if found is not None:
            return found
    return None


def _label_color_expr_for_filled_control(
    background_node: CleanDesignTreeNode,
    label_node: CleanDesignTreeNode,
) -> str:
    """Label color from Figma text fill; fall back to onPrimary only when the tree has no fill."""
    del background_node
    return dart_color_expr(
        label_node.style,
        css_key="color",
        fallback="Theme.of(context).colorScheme.onPrimary",
    )


def _collect_button_style_specs(
    clean_tree: CleanDesignTreeNode,
) -> dict[str, tuple[str, str]]:
    """Map button label copy to (background Color expr, label Color expr) from the clean tree."""
    specs: dict[str, tuple[str, str]] = {}
    for node in _collect_all_nodes(clean_tree):
        if node.type == NodeType.BUTTON:
            label_node = _first_text_descendant(node)
            if label_node is None or not label_node.text:
                continue
            background_expr = dart_color_expr(
                node.style,
                css_key="background-color",
                fallback="Theme.of(context).colorScheme.primary",
            )
            label_expr = _label_color_expr_for_filled_control(node, label_node)
            specs[label_node.text.strip()] = (background_expr, label_expr)

    for parent in _collect_all_nodes(clean_tree):
        background_node = next(
            (
                child
                for child in parent.children
                if child.type == NodeType.CONTAINER and child.style.background_color
            ),
            None,
        )
        if background_node is None:
            continue
        for child in parent.children:
            if child.type != NodeType.TEXT or not child.text:
                continue
            label = child.text.strip()
            if label in specs:
                continue
            background_expr = dart_color_expr(
                background_node.style,
                css_key="background-color",
                fallback="Theme.of(context).colorScheme.primary",
            )
            label_expr = _label_color_expr_for_filled_control(background_node, child)
            specs[label] = (background_expr, label_expr)
    return specs


def _collect_stack_filled_label_color_by_figma_id(
    clean_tree: CleanDesignTreeNode,
) -> dict[str, str]:
    """Map TEXT figma ids on filled stacks to Dart label color expressions."""
    specs: dict[str, str] = {}
    for parent in _collect_all_nodes(clean_tree):
        if parent.type != NodeType.STACK:
            continue
        fill_nodes = [
            child
            for child in parent.children
            if child.type == NodeType.CONTAINER and child.style.background_color
        ]
        if not fill_nodes:
            continue
        background_node = fill_nodes[0]
        for child in parent.children:
            if child.type != NodeType.TEXT or not child.text:
                continue
            specs[child.id] = _label_color_expr_for_filled_control(background_node, child)
    for node in _collect_all_nodes(clean_tree):
        if node.type != NodeType.BUTTON:
            continue
        label_node = _first_text_descendant(node)
        if label_node is None:
            continue
        specs[label_node.id] = _label_color_expr_for_filled_control(node, label_node)
    return specs


def _patch_secondary_text_below_opaque_fill(
    screen_code: str,
    clean_tree: CleanDesignTreeNode,
) -> str:
    """Move lower TEXT siblings below an opaque CONTAINER fill using stackPlacement only."""
    from figma_flutter_agent.generator.figma_anchor import figma_key_token

    updated = screen_code
    for parent in _collect_all_nodes(clean_tree):
        if parent.type != NodeType.STACK:
            continue
        fill_nodes = [
            child
            for child in parent.children
            if child.type == NodeType.CONTAINER
            and child.style.background_color
            and child.stack_placement is not None
        ]
        text_nodes = [
            child
            for child in parent.children
            if child.type == NodeType.TEXT
            and child.text
            and child.stack_placement is not None
        ]
        if len(fill_nodes) != 1 or len(text_nodes) < 2:
            continue
        fill_node = fill_nodes[0]
        fill_placement = fill_node.stack_placement
        if fill_placement is None:
            continue
        fill_height = fill_placement.height or fill_node.sizing.height
        if fill_height is None:
            continue
        fill_top = float(fill_placement.top or 0.0)
        fill_bottom = fill_top + float(fill_height)
        ordered_texts = sorted(
            text_nodes,
            key=lambda node: float(node.stack_placement.top or 0.0),
        )
        primary_top = float(ordered_texts[0].stack_placement.top or 0.0)
        for secondary in ordered_texts[1:]:
            placement = secondary.stack_placement
            if placement is None or placement.top is None:
                continue
            secondary_top = float(placement.top)
            if secondary_top < primary_top + 2.0:
                continue
            if secondary_top >= fill_bottom - 2.0:
                continue
            target_top = fill_bottom + 4.0
            token = re.escape(figma_key_token(secondary.id))
            pattern = rf"(key:\s*ValueKey\('{token}'\)[\s\S]{{0,500}}?top:\s*)([\d.]+)"
            updated, _count = re.subn(
                pattern,
                lambda match, top=target_top: f"{match.group(1)}{top}",
                updated,
                count=1,
            )
    return updated


def _patch_stack_filled_buttons_from_tree(
    screen_code: str,
    clean_tree: CleanDesignTreeNode,
) -> str:
    """Fix label colors on InkWell/Stack buttons matched by Figma ValueKey or label copy."""
    from figma_flutter_agent.generator.figma_anchor import figma_key_token

    specs_by_id = _collect_stack_filled_label_color_by_figma_id(clean_tree)
    updated = screen_code
    for figma_id, label_expr in specs_by_id.items():
        token = re.escape(figma_key_token(figma_id))
        key_pattern = rf"key:\s*ValueKey\('{token}'\)"
        for key_match in re.finditer(key_pattern, updated):
            window_start = key_match.start()
            window_end = min(len(updated), key_match.end() + 2500)
            window = updated[window_start:window_end]
            if "BoxDecoration" not in window and "InkWell" not in window:
                continue
            from figma_flutter_agent.generator.dart.delimiters import (
                replace_first_copywith_color,
            )

            patched_window, replacements = replace_first_copywith_color(
                window,
                label_expr,
            )
            if not replacements:
                patched_window, replacements = re.subn(
                    r"color:\s*Color\([^)]+\)",
                    f"color: {label_expr}",
                    window,
                    count=1,
                )
            if replacements:
                updated = updated[:window_start] + patched_window + updated[window_end:]
                break

    specs = _collect_button_style_specs(clean_tree)
    if not specs:
        return updated
    for label, (_background_expr, label_expr) in specs.items():
        escaped = re.escape(label)
        for match in re.finditer(rf"Text\(\s*['\"]{escaped}['\"]", updated):
            context_start = max(0, match.start() - 4000)
            context_end = min(len(updated), match.end() + 900)
            context = updated[context_start:context_end]
            if "BoxDecoration" not in context and "InkWell" not in context:
                continue
            window_start = match.start()
            window = updated[window_start:context_end]
            from figma_flutter_agent.generator.dart.delimiters import (
                replace_first_copywith_color,
            )

            patched_window, did_patch = replace_first_copywith_color(window, label_expr)
            if not did_patch:
                patched_window, replacements = re.subn(
                    r"color:\s*Color\([^)]+\)",
                    f"color: {label_expr}",
                    window,
                    count=1,
                )
                did_patch = bool(replacements)
            if did_patch:
                updated = updated[:window_start] + patched_window + updated[context_end:]
                break
    return updated


def _patch_material_buttons_from_tree(
    screen_code: str, clean_tree: CleanDesignTreeNode
) -> str:
    """Apply Figma fill/label colors to Material buttons matched by their visible label text."""
    specs = _collect_button_style_specs(clean_tree)
    if not specs:
        return screen_code

    updated = screen_code
    for label, (background_expr, label_expr) in specs.items():
        escaped_label = re.escape(label)
        for match in re.finditer(
            r"\b(?:FilledButton|ElevatedButton|TextButton)\s*\(", updated
        ):
            button_start = match.start()
            paren_start = match.end() - 1
            paren_end = _find_matching_paren(updated, paren_start)
            if paren_end is None:
                continue
            block = updated[button_start : paren_end + 1]
            if not re.search(rf"['\"]{escaped_label}['\"]", block):
                continue
            patched = block
            for bg_pattern in (
                r"backgroundColor:\s*Theme\.of\(\s*context\s*\)\s*\.colorScheme\.primary",
                r"backgroundColor:\s*theme\.colorScheme\.primary",
            ):
                patched = re.sub(
                    bg_pattern,
                    f"backgroundColor: {background_expr}",
                    patched,
                    count=1,
                    flags=re.DOTALL,
                )
            label_style = re.search(
                rf"Text\(\s*['\"]{escaped_label}['\"][\s\S]*?TextStyle\(\s*color:\s*[^,\n)]+",
                patched,
                flags=re.DOTALL,
            )
            if label_style is not None:
                fixed_label = re.sub(
                    r"color:\s*[^,\n)]+",
                    f"color: {label_expr}",
                    label_style.group(0),
                    count=1,
                )
                patched = (
                    patched[: label_style.start()]
                    + fixed_label
                    + patched[label_style.end() :]
                )
            else:
                for color_pattern in (
                    r"color:\s*Theme\.of\(\s*context\s*\)\s*\.colorScheme\.onPrimary",
                    r"color:\s*theme\.colorScheme\.onPrimary",
                ):
                    patched = re.sub(
                        color_pattern,
                        f"color: {label_expr}",
                        patched,
                        count=1,
                        flags=re.DOTALL,
                    )
            updated = updated[:button_start] + patched + updated[paren_end + 1 :]
            break
    return updated


def _ensure_theme_color_scheme_in_scope(screen_code: str) -> str:
    """Use ``Theme.of(context).colorScheme`` when no local ``theme`` binding exists."""
    if "theme.colorScheme" not in screen_code:
        return screen_code
    has_local_theme = "final ThemeData theme =" in screen_code or (
        "ThemeData theme =" in screen_code and "return Theme(" in screen_code
    )
    if has_local_theme:
        return screen_code
    return screen_code.replace(
        "theme.colorScheme",
        "Theme.of(context).colorScheme",
    )


def _patch_theme_wrapped_color_scheme(screen_code: str) -> str:
    """Route colorScheme lookups through the local ``theme`` when the screen re-themes itself."""
    if not re.search(
        r"final\s+ThemeData\s+theme\s*=\s*Theme\.of\s*\(\s*context\s*\)",
        screen_code,
    ):
        return screen_code
    if "return Theme(" not in screen_code:
        return screen_code
    theme_start = screen_code.find("return Theme(")
    if theme_start == -1:
        return screen_code
    tail = screen_code[theme_start:]
    return screen_code[:theme_start] + tail.replace(
        "Theme.of(context).colorScheme",
        "theme.colorScheme",
    )


_DART_STRING_LITERAL_RE = re.compile(
    r"""(['"])(?P<body>(?:\\.|(?!\1).)*)\1""",
    re.DOTALL,
)


def _dart_single_quoted_literal(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
    return f"'{escaped}'"


def _first_dart_string_body(source: str) -> str | None:
    """Return decoded content of the first Dart string literal in ``source``."""
    match = _DART_STRING_LITERAL_RE.search(source)
    if match is None:
        return None
    return match.group("body")


def _iter_dart_string_literals(source: str):
    """Yield ``(start, end, body)`` for each Dart string literal in ``source``."""
    for match in _DART_STRING_LITERAL_RE.finditer(source):
        yield match.start(), match.end(), match.group("body")


def sanitize_figma_display_text(text: str) -> str:
    """Normalize Figma copy for Flutter Text widgets."""
    updated = text.replace("\r\n", "\n")
    updated = re.sub(r"[ \t]+\n", "\n", updated)
    updated = re.sub(r"\n[ \t]+", "\n", updated)
    updated = updated.rstrip()
    if updated.endswith("\n"):
        updated = updated.rstrip("\n").rstrip()
    return updated


def _decode_dart_string_literal_content(text: str) -> str:
    """Decode escape sequences from a Dart single-quoted string body."""
    decoded: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char != "\\" or index + 1 >= len(text):
            decoded.append(char)
            index += 1
            continue
        escape = text[index + 1]
        if escape == "n":
            decoded.append("\n")
        elif escape == "r":
            decoded.append("\r")
        elif escape == "t":
            decoded.append("\t")
        elif escape == "\\":
            decoded.append("\\")
        elif escape == "'":
            decoded.append("'")
        elif escape == '"':
            decoded.append('"')
        else:
            decoded.append(escape)
        index += 2
    return "".join(decoded)


def _normalize_text_for_match(text: str, *, from_dart_literal: bool = False) -> str:
    if from_dart_literal:
        text = _decode_dart_string_literal_content(text)
    return " ".join(sanitize_figma_display_text(text).split())


def _figma_literal(text: str) -> str:
    return _dart_single_quoted_literal(sanitize_figma_display_text(text))


def _build_richtext_children_from_node(node: CleanDesignTreeNode) -> str:
    from figma_flutter_agent.generator.emit_text_span import (
        emit_text_span_children_from_node,
    )

    return ", ".join(emit_text_span_children_from_node(node))


def _patch_richtext_spans_from_tree(
    screen_code: str, clean_tree: CleanDesignTreeNode
) -> str:
    """Replace LLM RichText copy with Figma ``textSpans`` from the clean tree."""
    updated = screen_code
    for node in _collect_text_nodes(clean_tree):
        if node.type != NodeType.TEXT or not node.text_spans:
            continue
        marker = _normalize_text_for_match(node.text or "")
        if not marker:
            continue
        rich_index = updated.find("RichText(")
        while rich_index != -1:
            paren_start = updated.find("(", rich_index)
            block_end = (
                _find_matching_paren(updated, paren_start)
                if paren_start != -1
                else None
            )
            if block_end is None:
                break
            block = updated[rich_index : block_end + 1]
            block_norm = _normalize_text_for_match(block)
            if marker not in block_norm and not any(
                _normalize_text_for_match(part.text) in block_norm
                for part in node.text_spans
            ):
                rich_index = updated.find("RichText(", rich_index + 1)
                continue
            spans_body = _build_richtext_children_from_node(node)
            align = "center"
            if "textAlign: TextAlign.left" in block:
                align = "left"
            elif "textAlign: TextAlign.right" in block:
                align = "right"
            replacement = (
                f"RichText(\n"
                f"                                      textAlign: TextAlign.{align},\n"
                f"                                      text: TextSpan(\n"
                f"                                        children: [{spans_body}],\n"
                f"                                      ),\n"
                f"                                    )"
            )
            updated = updated[:rich_index] + replacement + updated[block_end + 1 :]
            break
    return updated


def _extract_widget_style_expr(widget_block: str) -> str | None:
    """Return the full `style:` expression from a Text/RichText widget block."""
    marker = re.search(r"\bstyle:\s*", widget_block)
    if marker is None:
        return None
    index = marker.end()
    while index < len(widget_block) and widget_block[index].isspace():
        index += 1
    if index >= len(widget_block):
        return None
    if widget_block[index] in {"'", '"'}:
        quote = widget_block[index]
        index += 1
        escape = False
        while index < len(widget_block):
            char = widget_block[index]
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == quote:
                index += 1
                break
            index += 1
    else:
        depth = 0
        while index < len(widget_block):
            char = widget_block[index]
            if char == "(":
                depth += 1
            elif char == ")":
                if depth == 0:
                    break
                depth -= 1
            elif char == "," and depth == 0:
                break
            index += 1
    return widget_block[marker.end() : index].strip()


def _multiline_copy_line_widget(
    *,
    line_literal: str,
    style_expr: str,
    align_prefix: str,
) -> str:
    return (
        "FittedBox(\n"
        "                                      fit: BoxFit.scaleDown,\n"
        f"                                      child: Text({line_literal}, "
        f"{align_prefix}"
        "softWrap: false, "
        f"style: {style_expr}, "
        "textScaler: MediaQuery.textScalerOf(context)),\n"
        "                                    )"
    )


def _multiline_copy_text_widget(
    *,
    sanitized_text: str,
    style_expr: str,
    align_prefix: str,
) -> str:
    """Render Figma hard line breaks as one Text per line (no soft-wrap reflow)."""
    first_line, second_line = (part.strip() for part in sanitized_text.split("\n", 1))
    if not first_line or not second_line:
        literal = _figma_literal(sanitized_text)
        return (
            f"Text({literal}, "
            f"{align_prefix}"
            "softWrap: false, "
            f"style: {style_expr}, "
            "textScaler: MediaQuery.textScalerOf(context))"
        )
    return (
        "Column(\n"
        "                                  mainAxisSize: MainAxisSize.min,\n"
        "                                  children: [\n"
        f"                                    {_multiline_copy_line_widget(line_literal=_figma_literal(first_line), style_expr=style_expr, align_prefix=align_prefix)},\n"
        f"                                    {_multiline_copy_line_widget(line_literal=_figma_literal(second_line), style_expr=style_expr, align_prefix=align_prefix)},\n"
        "                                  ],\n"
        "                                )"
    )


def collapse_nested_fitted_box_wrappers(screen_code: str) -> str:
    """Unwrap redundant ``FittedBox`` > ``FittedBox`` chains (keep inner wrapper)."""
    updated = screen_code
    index = 0
    while True:
        start = updated.find("FittedBox(", index)
        if start == -1:
            break
        paren_start = start + len("FittedBox")
        paren_end = _find_matching_paren(updated, paren_start)
        if paren_end is None:
            break
        block = updated[start : paren_end + 1]
        child_match = re.search(r"child:\s*FittedBox\s*\(", block)
        if child_match is None:
            index = paren_end + 1
            continue
        inner_offset = child_match.start()
        inner_paren = block.find("(", inner_offset)
        if inner_paren == -1:
            index = paren_end + 1
            continue
        inner_end = _find_matching_paren(block, inner_paren)
        if inner_end is None:
            index = paren_end + 1
            continue
        inner_block = block[inner_offset : inner_end + 1]
        updated = updated[:start] + inner_block + updated[paren_end + 1 :]
        index = start + len(inner_block)
    return updated


def _wrap_dart_text_fitted_box(text_widget: str) -> str:
    stripped = text_widget.strip()
    if stripped.startswith("FittedBox("):
        return text_widget
    indent_match = re.match(r"(\s*)", text_widget)
    indent = indent_match.group(1) if indent_match else ""
    inner_indent = f"{indent}  "
    return (
        f"{indent}FittedBox(\n"
        f"{inner_indent}fit: BoxFit.scaleDown,\n"
        f"{inner_indent}child: {stripped},\n"
        f"{indent})"
    )


def _apply_fitted_box_to_multiline_copy_lines(screen_code: str) -> str:
    """Scale down subtitle lines instead of clipping when metrics exceed Figma width."""
    index = 0
    while True:
        column_start = screen_code.find("Column(", index)
        if column_start == -1:
            break
        paren_start = column_start + len("Column")
        paren_end = _find_matching_paren(screen_code, paren_start)
        if paren_end is None:
            break
        block = screen_code[column_start : paren_end + 1]
        index = paren_end + 1
        if "mainAxisSize: MainAxisSize.min" not in block:
            continue
        text_matches = list(re.finditer(r"\bText\s*\(", block))
        if len(text_matches) < 2:
            continue
        subtitle_texts: list[tuple[int, int]] = []
        for text_match in text_matches:
            text_start = text_match.start()
            text_paren_start = text_match.end() - 1
            text_paren_end = _find_matching_paren(block, text_paren_start)
            if text_paren_end is None:
                subtitle_texts = []
                break
            text_block = block[text_start : text_paren_end + 1]
            if "softWrap: false" not in text_block:
                continue
            lookback = block[max(0, text_start - 160) : text_start]
            if "FittedBox(" in lookback:
                continue
            subtitle_texts.append((text_start, text_paren_end + 1))
        if len(subtitle_texts) < 2:
            continue
        patched_block = block
        for text_start, text_end in reversed(subtitle_texts):
            text_widget = patched_block[text_start:text_end]
            if text_widget.strip().startswith("FittedBox("):
                continue
            patched_block = (
                patched_block[:text_start]
                + _wrap_dart_text_fitted_box(text_widget)
                + patched_block[text_end:]
            )
        screen_code = (
            screen_code[:column_start] + patched_block + screen_code[paren_end + 1 :]
        )
    return screen_code


def _collapse_rigid_two_line_copy_column(screen_code: str, sanitized_text: str) -> str:
    """Replace legacy two-Text columns (maxLines: 1, softWrap: false) with one multiline Text."""
    if sanitized_text.count("\n") != 1:
        return screen_code
    first_line, second_line = (part.strip() for part in sanitized_text.split("\n", 1))
    if not first_line or not second_line:
        return screen_code
    first_norm = _normalize_text_for_match(first_line)
    second_norm = _normalize_text_for_match(second_line)
    index = 0
    while True:
        column_start = screen_code.find("Column(", index)
        if column_start == -1:
            break
        paren_start = column_start + len("Column")
        paren_end = _find_matching_paren(screen_code, paren_start)
        if paren_end is None:
            break
        block = screen_code[column_start : paren_end + 1]
        index = paren_end + 1
        if (
            "mainAxisSize: MainAxisSize.min" not in block
            or block.count("maxLines: 1") < 2
        ):
            continue
        text_matches = list(re.finditer(r"\bText\s*\(", block))
        if len(text_matches) < 2:
            continue
        line_norms: list[str] = []
        style_expr: str | None = None
        align_prefix = ""
        for text_match in text_matches[:2]:
            text_start = text_match.start()
            text_paren_start = text_match.end() - 1
            text_paren_end = _find_matching_paren(block, text_paren_start)
            if text_paren_end is None:
                break
            text_block = block[text_start : text_paren_end + 1]
            quote_body = _first_dart_string_body(text_block) or ""
            line_norms.append(
                _normalize_text_for_match(quote_body, from_dart_literal=True)
            )
            if style_expr is None:
                style_expr = _extract_widget_style_expr(text_block)
                align_match = re.search(r"textAlign:\s*(TextAlign\.\w+)", text_block)
                if align_match is not None:
                    align_prefix = f"textAlign: {align_match.group(1)}, "
        if line_norms != [first_norm, second_norm] or style_expr is None:
            continue
        replacement = _multiline_copy_text_widget(
            sanitized_text=sanitized_text,
            style_expr=style_expr,
            align_prefix=align_prefix,
        )
        return screen_code[:column_start] + replacement + screen_code[paren_end + 1 :]
    return screen_code


def _split_two_line_text_widget(screen_code: str, sanitized_text: str) -> str:
    """Normalize two-line marketing copy to a single multiline Text widget."""
    if sanitized_text.count("\n") != 1:
        return screen_code
    first_line, second_line = (part.strip() for part in sanitized_text.split("\n", 1))
    if not first_line or not second_line:
        return screen_code

    literal = _dart_single_quoted_literal(sanitized_text)
    text_iter = re.finditer(r"\bText\s*\(", screen_code)
    for match in text_iter:
        text_start = match.start()
        paren_start = match.end() - 1
        paren_end = _find_matching_paren(screen_code, paren_start)
        if paren_end is None:
            continue
        block = screen_code[text_start : paren_end + 1]
        quote_body = _first_dart_string_body(block) or ""
        block_norm = _normalize_text_for_match(quote_body, from_dart_literal=True)
        target_norm = _normalize_text_for_match(sanitized_text)
        first_norm = _normalize_text_for_match(first_line)
        second_norm = _normalize_text_for_match(second_line)
        if block_norm in {first_norm, second_norm}:
            continue
        if block_norm == target_norm and "softWrap: false" in block:
            if "Column(" in screen_code[max(0, text_start - 80) : text_start]:
                continue
            if "\n" in (quote_body or ""):
                continue
        if "maxLines: 1" in block and "softWrap: false" in block:
            continue
        if (
            literal not in block
            and _dart_single_quoted_literal(first_line) not in block
            and block_norm != target_norm
        ):
            continue
        style_expr = _extract_widget_style_expr(block)
        if style_expr is None:
            continue
        align_match = re.search(r"textAlign:\s*(TextAlign\.\w+)", block)
        align_prefix = (
            f"textAlign: {align_match.group(1)}, " if align_match is not None else ""
        )
        replacement = _multiline_copy_text_widget(
            sanitized_text=sanitized_text,
            style_expr=style_expr,
            align_prefix=align_prefix,
        )
        return screen_code[:text_start] + replacement + screen_code[paren_end + 1 :]
    return screen_code


def _patch_multiline_copy_from_tree(
    screen_code: str, clean_tree: CleanDesignTreeNode
) -> str:
    updated = screen_code
    for node in _collect_text_nodes(clean_tree):
        if node.type != NodeType.TEXT or node.text_spans:
            continue
        sanitized = sanitize_figma_display_text(node.text or "")
        if "\n" not in sanitized:
            continue
        updated = _collapse_rigid_two_line_copy_column(updated, sanitized)
        updated = _split_two_line_text_widget(updated, sanitized)
    return updated


def _target_text_positioned_height(node: CleanDesignTreeNode) -> float | None:
    """Return a minimum Positioned height when Figma box would clip glyph metrics."""
    if node.type != NodeType.TEXT or node.stack_placement is None:
        return None
    placement_height = node.stack_placement.height
    if placement_height is None:
        return None
    font_size = node.style.font_size
    if font_size is None or font_size <= 0:
        return None
    line_factor = node.style.line_height if node.style.line_height else 1.2
    min_height = font_size * line_factor
    if node.style.glyph_height is not None:
        min_height = max(min_height, node.style.glyph_height + 2.0)
    if placement_height >= min_height * 0.95:
        return None
    return round(min_height + 2.0, 1)


def _figma_multiline_text_frame(node: CleanDesignTreeNode) -> bool:
    """True when the Figma text box is taller than a single line (wrap in Flutter)."""
    if node.type != NodeType.TEXT:
        return False
    if "\n" in (node.text or ""):
        return True
    font_size = node.style.font_size
    if font_size is None or font_size <= 0:
        return False
    line_factor = node.style.line_height if node.style.line_height else 1.2
    placement = node.stack_placement
    if placement is None or placement.height is None:
        return False
    single_line_height = font_size * line_factor
    return float(placement.height) >= single_line_height * 1.35


def _estimated_text_width(node: CleanDesignTreeNode) -> float | None:
    text = (node.text or "").strip()
    font_size = node.style.font_size
    if not text or font_size is None or font_size <= 0:
        return None
    weight = (node.style.font_weight or "").lower()
    weight_scale = 1.12 if weight in {"w700", "w800", "w900", "bold"} else 1.0
    if weight in {"w500", "w600", "medium", "semibold"}:
        weight_scale = 1.05
    per_char = font_size * 0.56 * weight_scale
    letter_spacing = node.style.letter_spacing or 0.0
    width = len(text) * per_char + max(0, len(text) - 1) * letter_spacing
    return round(width + 12.0, 1)


def expand_text_positioned_widths_from_tree(
    screen_code: str,
    clean_tree: CleanDesignTreeNode,
) -> str:
    """Widen narrow Figma HUG text boxes so labels are not clipped in Flutter."""
    from figma_flutter_agent.parser.interaction import (
        button_stack_has_left_icon,
        stack_interaction_kind,
    )

    updated = screen_code
    for node in _collect_text_nodes(clean_tree):
        if node.text_spans or _figma_multiline_text_frame(node):
            continue
        parent = _find_parent_node(clean_tree, node.id)
        if parent is not None and stack_interaction_kind(parent) == "button":
            if button_stack_has_left_icon(parent):
                continue
        parent_width: float | None = None
        if parent is not None and parent.type == NodeType.STACK:
            parent_width = parent.sizing.width
            if parent.stack_placement is not None and parent.stack_placement.width is not None:
                parent_width = parent.stack_placement.width
        figma_text = (node.text or "").strip()
        target_width = _estimated_text_width(node)
        placement_width = (
            node.stack_placement.width if node.stack_placement is not None else None
        )
        if not figma_text or target_width is None or placement_width is None:
            continue
        min_width = max(placement_width, target_width)
        if (
            parent_width is not None
            and parent_width > 0
            and node.style.text_align == "CENTER"
        ):
            min_width = min(min_width, float(parent_width))
        if min_width <= placement_width + 1.5:
            continue
        escaped = re.escape(figma_text)
        for text_match in re.finditer(rf"Text\s*\(\s*['\"]({escaped})['\"]", updated):
            text_index = text_match.start()
            positioned_start = updated.rfind("Positioned(", 0, text_index)
            if positioned_start < 0:
                continue
            paren_open = updated.find("(", positioned_start)
            paren_close = _find_matching_paren(updated, paren_open)
            if paren_close is None or paren_close < text_index:
                continue
            block = updated[positioned_start : paren_close + 1]
            width_match = re.search(r"width:\s*([\d.]+)", block)
            if width_match is None:
                continue
            try:
                current_width = float(width_match.group(1))
            except ValueError:
                continue
            if current_width >= min_width - 1.0:
                continue
            width_token = (
                f"{min_width:g}" if min_width != int(min_width) else str(int(min_width))
            )
            new_block = re.sub(
                r"width:\s*[\d.]+",
                f"width: {width_token}",
                block,
                count=1,
            )
            updated = (
                updated[:positioned_start] + new_block + updated[paren_close + 1 :]
            )
            break
    return updated


def _strip_tight_text_positioned_heights(screen_code: str) -> str:
    """Drop fixed ``Positioned`` height on label rows that squash glyph metrics."""
    updated = screen_code
    search_from = 0
    while True:
        positioned_start = updated.find("Positioned(", search_from)
        if positioned_start < 0:
            break
        paren_open = updated.find("(", positioned_start)
        paren_close = _find_matching_paren(updated, paren_open)
        if paren_close is None:
            break
        block = updated[positioned_start : paren_close + 1]
        search_from = paren_close + 1
        if "Text(" not in block and "RichText(" not in block:
            continue
        height_match = re.search(r"height:\s*([\d.]+)", block)
        if height_match is None:
            continue
        font_match = re.search(r"fontSize:\s*([\d.]+)", block)
        if font_match is None:
            continue
        try:
            current_height = float(height_match.group(1))
            font_size = float(font_match.group(1))
        except ValueError:
            continue
        if current_height > font_size * 1.02:
            continue
        new_block = re.sub(r",?\s*height:\s*[\d.]+", "", block, count=1)
        if new_block == block:
            continue
        updated = updated[:positioned_start] + new_block + updated[paren_close + 1 :]
        search_from = positioned_start + len(new_block)
    return updated


_PROPORTIONAL_LEADING_MIN_LINE_HEIGHT = 1.15
_LINE_HEIGHT_RATIO_UPPER_BOUND = 3.0


def strip_tight_proportional_leading_in_text_styles(content: str) -> str:
    """Remove proportional leading when ``TextStyle.height`` is below a safe ratio.

    Flutter Web can paint zero-height glyphs when ``TextLeadingDistribution.proportional``
    is paired with a tight line-height factor inside a fixed ``Positioned`` box.
    """
    updated = content
    search_from = 0
    while True:
        match = re.search(r"height:\s*([\d.]+)", updated[search_from:])
        if match is None:
            break
        abs_start = search_from + match.start()
        try:
            ratio = float(match.group(1))
        except ValueError:
            search_from = abs_start + 1
            continue
        if ratio >= _PROPORTIONAL_LEADING_MIN_LINE_HEIGHT or ratio < 0.5:
            search_from = abs_start + match.end() - match.start()
            continue
        if ratio > _LINE_HEIGHT_RATIO_UPPER_BOUND:
            search_from = abs_start + match.end() - match.start()
            continue
        tail_start = search_from + match.end()
        trailing = updated[tail_start : tail_start + 220]
        leading = re.match(
            r"\s*,\s*leadingDistribution:\s*TextLeadingDistribution\.proportional,?",
            trailing,
            re.DOTALL,
        )
        if leading is None:
            search_from = tail_start
            continue
        updated = updated[:tail_start] + updated[tail_start + leading.end() :]
        search_from = abs_start
    return updated


def _relax_tight_text_positioned_heights(
    screen_code: str,
    clean_tree: CleanDesignTreeNode,
) -> str:
    """Widen tight Positioned heights around single-line labels (e.g. section dividers)."""
    updated = screen_code
    for node in _collect_text_nodes(clean_tree):
        figma_text = (node.text or "").strip()
        min_height = _target_text_positioned_height(node)
        if not figma_text or min_height is None:
            continue
        escaped = re.escape(figma_text)
        for text_match in re.finditer(rf"Text\s*\(\s*['\"]({escaped})['\"]", updated):
            text_index = text_match.start()
            positioned_start = updated.rfind("Positioned(", 0, text_index)
            if positioned_start < 0:
                continue
            paren_open = updated.find("(", positioned_start)
            paren_close = _find_matching_paren(updated, paren_open)
            if paren_close is None or paren_close < text_index:
                continue
            block = updated[positioned_start : paren_close + 1]
            height_match = re.search(r"height:\s*([\d.]+)", block)
            if height_match is None:
                continue
            try:
                current_height = float(height_match.group(1))
            except ValueError:
                continue
            if current_height >= min_height - 0.5:
                continue
            height_token = (
                f"{min_height:g}"
                if min_height != int(min_height)
                else str(int(min_height))
            )
            new_block = re.sub(
                r"height:\s*[\d.]+",
                f"height: {height_token}",
                block,
                count=1,
            )
            updated = (
                updated[:positioned_start] + new_block + updated[paren_close + 1 :]
            )
            break
    return updated


def apply_clean_tree_text_to_screen(
    screen_code: str,
    clean_tree: CleanDesignTreeNode,
) -> str:
    """Replace LLM-paraphrased copy with exact Figma text and tighten headline width."""
    updated = screen_code
    for node in sorted(
        _collect_text_nodes(clean_tree),
        key=lambda item: len(item.text or ""),
        reverse=True,
    ):
        figma_text = node.text
        if not figma_text or node.text_spans:
            continue
        literal = _figma_literal(figma_text)
        if literal in updated:
            continue
        normalized = _normalize_text_for_match(figma_text)
        for start, end, candidate in _iter_dart_string_literals(updated):
            candidate_norm = _normalize_text_for_match(
                candidate, from_dart_literal=True
            )
            if not candidate_norm:
                continue
            if candidate_norm == normalized or (
                len(normalized) >= 12
                and (
                    normalized.startswith(candidate_norm)
                    or candidate_norm.startswith(normalized)
                )
            ):
                updated = updated[:start] + literal + updated[end:]
                break

    updated = _patch_richtext_spans_from_tree(updated, clean_tree)
    updated = _patch_multiline_copy_from_tree(updated, clean_tree)
    copy_width = _multiline_copy_column_width_from_tree(clean_tree)
    if copy_width is not None:
        updated = _patch_multiline_copy_column_width(updated, copy_width)
    updated = _strip_multiline_copy_positioned_heights(updated)
    updated = fix_positioned_stack_bounds_from_tree(updated, clean_tree)
    updated = fix_invalid_positioned_constraints(updated)
    updated = _apply_fitted_box_to_multiline_copy_lines(updated)
    updated = _patch_material_buttons_from_tree(updated, clean_tree)
    updated = _patch_stack_filled_buttons_from_tree(updated, clean_tree)
    updated = _patch_secondary_text_below_opaque_fill(updated, clean_tree)
    updated = _relax_tight_text_positioned_heights(updated, clean_tree)
    updated = expand_text_positioned_widths_from_tree(updated, clean_tree)
    updated = _strip_tight_text_positioned_heights(updated)
    updated = _ensure_theme_color_scheme_in_scope(updated)
    updated = _patch_theme_wrapped_color_scheme(updated)
    updated = collapse_nested_fitted_box_wrappers(updated)
    from figma_flutter_agent.generator.dart.file_parts import relocate_directives_to_header

    return relocate_directives_to_header(updated)
