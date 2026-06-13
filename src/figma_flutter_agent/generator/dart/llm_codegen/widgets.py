"""Widget code sanitization, deduplication, and cross-widget reconciliation."""

from __future__ import annotations

import re
from collections.abc import Callable

from loguru import logger

from figma_flutter_agent.generator.layout.common import to_pascal_case, to_snake_case

from .delimiters import (
    _find_class_body_open_brace,
    _skip_dart_string,
    repair_dart_delimiters,
    validate_dart_delimiters,
)

_WIDGET_CLASS_RE = re.compile(
    r"\bclass\s+(?P<name>(?!GeneratedScreenShell\b)\w+)\s+extends\s+(?P<kind>StatelessWidget|StatefulWidget)\b"
)
_PASCAL_CASE_NAME_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")

_CLASS_MEMBER_PREFIXES = (
    "const ",
    "final ",
    "var ",
    "@override",
    "@",
    "Widget ",
    "void ",
)


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
    from .screen import _rename_dart_identifier

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
    from .screen import _rename_dart_identifier

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
    from .screen import _rename_dart_identifier

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
            file_stem = to_snake_case(class_name)
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
    """Reconcile widget class names in planned screen Dart files (not layout)."""
    if not extracted_widgets:
        return planned_files
    updated = dict(planned_files)
    for path, content in planned_files.items():
        if not path.endswith(".dart"):
            continue
        if path.startswith("lib/widgets/"):
            continue
        normalized = path.replace("\\", "/")
        if normalized.endswith("_layout.dart") or "_chunk_" in normalized:
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
    from .screen import _ensure_valid_llm_dart_code, _minimal_stateless_widget_stub

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
