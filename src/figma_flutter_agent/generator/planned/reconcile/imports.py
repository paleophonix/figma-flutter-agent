"""Import management for planned Dart files."""

from __future__ import annotations

import re
from pathlib import Path

from figma_flutter_agent.generator.paths import ImportContext

from .class_inspect import (
    _group_paths_by_class,
    _pick_canonical_widget_path,
    _widget_class_names_by_path,
    _widget_class_paths,
)
from .paths import (
    _detect_package_name,
    _is_large_planned_dart,
    preferred_widget_path_for_class,
)

_WIDGET_IMPORT_RE = re.compile(r"^import\s+'(?P<uri>package:[^']+/widgets/[^']+)';")
_RELATIVE_IMPORT_RE = re.compile(r"^import\s+['\"](?P<uri>[^'\"]+)['\"]\s*;\s*$")
_LLM_WIDGET_IMPORT_COMMENT_RE = re.compile(
    r"Import prebuilt dependencies|structural invariants",
    re.IGNORECASE,
)


def strip_llm_relative_widget_imports(content: str) -> str:
    """Remove bare ``import 'foo_widget.dart'`` paths LLMs add inside ``screenCode``."""
    kept: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            kept.append(line)
            continue
        if _LLM_WIDGET_IMPORT_COMMENT_RE.search(stripped) and stripped.startswith("//"):
            continue
        match = _RELATIVE_IMPORT_RE.match(stripped)
        if match is not None:
            uri = match.group("uri")
            if uri.startswith("package:") or uri.startswith("dart:"):
                kept.append(line)
                continue
            if "/" in uri or uri.startswith("."):
                kept.append(line)
                continue
            if uri.endswith(".dart"):
                continue
        kept.append(line)
    return "\n".join(kept)


def strip_unused_widget_imports(content: str, planned: dict[str, str]) -> str:
    """Drop widget imports when the screen body does not reference the class."""
    class_paths = _widget_class_paths(planned)
    if not class_paths:
        return content
    package_name = _detect_package_name(planned)
    import_ctx = ImportContext(
        package_name=package_name,
        use_package_imports=True,
        source_file="lib/features/screen.dart",
    )
    uri_to_class = {
        import_ctx.uri(path.removeprefix("lib/")): class_name
        for class_name, path in class_paths.items()
    }
    kept: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        pkg_match = _WIDGET_IMPORT_RE.match(stripped)
        if pkg_match is not None:
            class_name = uri_to_class.get(pkg_match.group("uri"))
            if class_name is not None and not re.search(
                rf"\b{re.escape(class_name)}\b",
                content,
            ):
                continue
        kept.append(line)
    return "\n".join(kept)


def strip_orphan_widget_imports(
    content: str,
    planned: dict[str, str],
    *,
    source_file: str,
) -> str:
    """Remove widget imports that point at files no longer present in ``planned``."""
    package_name = _detect_package_name(planned)
    import_ctx = ImportContext(
        package_name=package_name,
        use_package_imports=True,
        source_file=source_file,
    )
    valid_uris = {
        import_ctx.uri(path.removeprefix("lib/"))
        for path in planned
        if path.startswith("lib/widgets/") and path.endswith(".dart")
    }
    if not valid_uris:
        return content

    lines = content.splitlines()
    kept: list[str] = []
    for line in lines:
        match = _WIDGET_IMPORT_RE.match(line.strip())
        if match is None or match.group("uri") in valid_uris:
            kept.append(line)
    return "\n".join(kept)


def strip_ambiguous_widget_imports(
    content: str,
    planned: dict[str, str],
    *,
    source_file: str,
) -> str:
    """Remove widget imports that export the same class name as another imported file."""
    class_paths = _widget_class_paths(planned)
    if not class_paths:
        return content

    package_name = _detect_package_name(planned)
    import_ctx = ImportContext(
        package_name=package_name,
        use_package_imports=True,
        source_file=source_file,
    )
    class_names_by_path = _widget_class_names_by_path(planned)
    canonical_uri_by_class = {
        class_name: import_ctx.uri(path.removeprefix("lib/"))
        for class_name, path in class_paths.items()
    }

    lines = content.splitlines()
    imported: list[tuple[int, str, str]] = []
    for index, line in enumerate(lines):
        match = _WIDGET_IMPORT_RE.match(line.strip())
        if match is None:
            continue
        uri = match.group("uri")
        for path, class_name in class_names_by_path.items():
            if import_ctx.uri(path.removeprefix("lib/")) != uri:
                continue
            imported.append((index, uri, class_name))
            break

    class_imports: dict[str, list[tuple[int, str]]] = {}
    for index, uri, class_name in imported:
        class_imports.setdefault(class_name, []).append((index, uri))

    lines_to_remove: set[int] = set()
    for class_name, imports in class_imports.items():
        if len(imports) < 2:
            continue
        canonical_uri = canonical_uri_by_class.get(class_name)
        for index, uri in imports:
            if uri != canonical_uri:
                lines_to_remove.add(index)

    if not lines_to_remove:
        return content
    return "\n".join(line for index, line in enumerate(lines) if index not in lines_to_remove)


def ensure_referenced_widget_imports(planned: dict[str, str]) -> dict[str, str]:
    """Add missing widget imports when screens or layouts reference ``lib/widgets`` classes."""
    class_paths = _widget_class_paths(planned)
    if not class_paths:
        return planned

    package_name = _detect_package_name(planned)
    updated = dict(planned)
    for path, content in planned.items():
        if not _consumer_paths_needing_widget_imports(path):
            continue
        if _is_large_planned_dart(content):
            updated[path] = _insert_missing_widget_imports(
                content,
                class_paths=class_paths,
                package_name=package_name,
                source_file=path,
            )
            continue
        content = _insert_missing_widget_imports(
            content,
            class_paths=class_paths,
            package_name=package_name,
            source_file=path,
        )
        content = strip_llm_relative_widget_imports(content)
        content = strip_unused_widget_imports(content, updated)
        content = strip_orphan_widget_imports(content, updated, source_file=path)
        updated[path] = strip_ambiguous_widget_imports(
            content,
            updated,
            source_file=path,
        )
    return updated


def sync_widget_consumer_imports(
    planned: dict[str, str],
    *,
    skip_consolidate: bool = False,
) -> dict[str, str]:
    """Consolidate widget paths and align layout/screen import URIs with planned widgets."""
    from .class_inspect import consolidate_planned_widget_paths

    updated = planned if skip_consolidate else consolidate_planned_widget_paths(planned)
    updated = redirect_widget_imports_to_canonical(updated)
    updated = ensure_referenced_widget_imports(updated)
    return updated


def redirect_widget_imports_to_canonical(planned: dict[str, str]) -> dict[str, str]:
    """Rewrite widget import URIs so consumers target the canonical ``lib/widgets`` file."""
    class_paths = _widget_class_paths(planned)
    if not class_paths:
        return planned

    package_name = _detect_package_name(planned)
    from figma_flutter_agent.generator.layout.common import to_pascal_case

    updated = dict(planned)
    for path, content in planned.items():
        normalized = path.replace("\\", "/")
        if not normalized.endswith(".dart"):
            continue
        if not (
            _consumer_paths_needing_widget_imports(path)
            or normalized.startswith("lib/widgets/")
        ):
            continue
        if normalized.startswith("lib/widgets/") and _is_large_planned_dart(content):
            continue
        import_ctx = ImportContext(
            package_name=package_name,
            use_package_imports=True,
            source_file=path,
        )
        lines = content.splitlines()
        changed = False
        for index, line in enumerate(lines):
            match = _WIDGET_IMPORT_RE.match(line.strip())
            if match is None:
                continue
            uri = match.group("uri")
            if "/widgets/" not in uri:
                continue
            stem = Path(uri).stem
            inferred_class = to_pascal_case(stem)
            if inferred_class not in class_paths:
                continue
            widget_path = class_paths.get(inferred_class)
            if widget_path is None:
                continue
            canonical_uri = import_ctx.uri(widget_path.removeprefix("lib/"))
            if uri == canonical_uri:
                continue
            if not re.search(rf"\b{re.escape(inferred_class)}\b", content):
                continue
            lines[index] = line.replace(uri, canonical_uri)
            changed = True
        if changed:
            updated[path] = "\n".join(lines)
    return updated


def ensure_widget_sibling_imports(planned: dict[str, str]) -> dict[str, str]:
    """Add imports when Dart references another planned ``lib/widgets`` class."""
    class_paths = _widget_class_paths(planned)
    if not class_paths:
        return planned

    from .ast_helpers import _primary_public_widget_class_name

    package_name = _detect_package_name(planned)
    updated = dict(planned)
    for path, content in planned.items():
        normalized = path.replace("\\", "/")
        if not normalized.endswith(".dart"):
            continue
        if not (
            normalized.startswith("lib/widgets/")
            or normalized.startswith("lib/generated/")
            or (
                normalized.startswith("lib/features/")
                and normalized.endswith("_screen.dart")
            )
        ):
            continue
        import_ctx = ImportContext(
            package_name=package_name,
            use_package_imports=True,
            source_file=path,
        )
        own_class: str | None = None
        if normalized.startswith("lib/widgets/"):
            own_class = _primary_public_widget_class_name(content)
        imports_to_add: list[str] = []
        for class_name, widget_path in sorted(class_paths.items()):
            if class_name == own_class:
                continue
            if not re.search(rf"\b{re.escape(class_name)}\s*\(", content):
                continue
            widget_uri = import_ctx.uri(widget_path.removeprefix("lib/"))
            import_line = f"import '{widget_uri}';"
            if import_line not in content:
                imports_to_add.append(import_line)
        if imports_to_add:
            updated[path] = _insert_import_lines(content, imports_to_add)
    return updated


def filter_widget_import_stems(
    stems: list[str],
    planned_files: dict[str, str],
) -> list[str]:
    """Keep only widget import stems that have a matching planned ``lib/widgets`` file."""
    return [
        stem
        for stem in stems
        if f"lib/widgets/{stem}.dart" in planned_files
    ]


def widget_import_stems_for_screen(
    screen_code: str,
    planned_files: dict[str, str],
) -> list[str]:
    """Return widget file stems referenced by class name in a screen body."""
    stems: set[str] = set()
    for class_name, widget_path in _widget_class_paths(planned_files).items():
        if re.search(rf"\b{re.escape(class_name)}\s*\(", screen_code):
            stems.add(Path(widget_path).stem)
    return sorted(stems)


def _insert_import_lines(content: str, imports: list[str]) -> str:
    if not imports:
        return content
    lines = content.splitlines()
    last_import_idx = -1
    for index, line in enumerate(lines):
        if line.strip().startswith("import "):
            last_import_idx = index
    insert_idx = last_import_idx + 1 if last_import_idx >= 0 else 0
    for import_line in imports:
        if import_line in content:
            continue
        lines.insert(insert_idx, import_line)
        insert_idx += 1
    return "\n".join(lines)


def _consumer_paths_needing_widget_imports(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if normalized.startswith("lib/features/") and normalized.endswith("_screen.dart"):
        return True
    if normalized.startswith("lib/widgets/") and normalized.endswith(".dart"):
        return True
    if not normalized.startswith("lib/generated/"):
        return False
    return normalized.endswith("_layout.dart") or "_chunk_" in normalized


def _insert_missing_widget_imports(
    content: str,
    *,
    class_paths: dict[str, str],
    package_name: str,
    source_file: str,
) -> str:
    import_ctx = ImportContext(
        package_name=package_name,
        use_package_imports=True,
        source_file=source_file,
    )
    imports_to_add: list[str] = []
    normalized_source = source_file.replace("\\", "/")
    for class_name, widget_path in sorted(class_paths.items()):
        if f"{class_name}(" not in content:
            continue
        normalized_widget = widget_path.replace("\\", "/")
        if normalized_widget == normalized_source:
            continue
        widget_uri = import_ctx.uri(widget_path.removeprefix("lib/"))
        import_line = f"import '{widget_uri}';"
        if import_line not in content:
            imports_to_add.append(import_line)
    if imports_to_add:
        content = _insert_import_lines(content, imports_to_add)
    return content
