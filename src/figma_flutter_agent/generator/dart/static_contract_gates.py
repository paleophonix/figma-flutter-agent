"""Deterministic pre-write static gates on planned Dart sources."""

from __future__ import annotations

import re
from collections.abc import Mapping

from figma_flutter_agent.errors import PlannedDartGraphError

_WIDGET_CTOR_CALL_RE = re.compile(r"\b([A-Z][A-Za-z0-9_]*Widget\d*)\s*\(")
_NAMED_ARG_RE = re.compile(r"(?<![\w.])(?P<name>[a-z][A-Za-z0-9_]*)\s*:")
_CTOR_PARAM_RE = re.compile(
    r"(?:required\s+)?(?:this\.|super\.|final\s+[\w?<>,\s]+\s+)(?P<name>[a-z][A-Za-z0-9_]*)\b"
)
_FLUTTER_SDK_WIDGET_CTORS = frozenset(
    {
        "StatelessWidget",
        "StatefulWidget",
        "State",
        "Widget",
        "InheritedWidget",
        "RenderObjectWidget",
    }
)
_CONSUMER_PATH_PREFIXES = ("lib/generated/", "lib/features/", "lib/widgets/")


def _widget_class_paths(planned: Mapping[str, str]) -> dict[str, str]:
    from figma_flutter_agent.generator.planned.reconcile.class_inspect import (
        _widget_class_paths as class_paths,
    )

    return class_paths(dict(planned))


def _widget_build_snippet(content: str, class_name: str) -> str:
    from figma_flutter_agent.generator.planned.reconcile.class_inspect import (
        _widget_build_snippet as build_snippet,
    )

    return build_snippet(content, class_name=class_name)


def _find_matching_paren(source: str, open_index: int) -> int | None:
    from figma_flutter_agent.generator.planned.reconcile.ast_helpers import (
        _find_matching_paren as match_paren,
    )

    return match_paren(source, open_index)


def find_planned_widget_invocation_cycles(planned: Mapping[str, str]) -> list[list[str]]:
    """Return widget-class cycles in ``lib/widgets`` constructor invocation graphs."""
    class_paths = _widget_class_paths(planned)
    known = set(class_paths)
    graph: dict[str, list[str]] = {}
    for class_name, path in class_paths.items():
        content = planned.get(path, "")
        build = _widget_build_snippet(content, class_name)
        targets: list[str] = []
        for match in _WIDGET_CTOR_CALL_RE.finditer(build):
            target = match.group(1)
            if target in known and target != class_name:
                targets.append(target)
        if targets:
            graph[class_name] = targets

    cycles: list[list[str]] = []
    visited: set[str] = set()
    stack: list[str] = []

    def dfs(node: str) -> None:
        if node in stack:
            start = stack.index(node)
            cycles.append(stack[start:] + [node])
            return
        if node in visited:
            return
        visited.add(node)
        stack.append(node)
        for target in graph.get(node, []):
            dfs(target)
        stack.pop()

    for node in graph:
        dfs(node)
    return cycles


def _extract_constructor_param_names(content: str, class_name: str) -> set[str]:
    decl = re.search(rf"\bclass\s+{re.escape(class_name)}\s+extends\b", content)
    if decl is None:
        return set()
    ctor = re.search(
        rf"\b{re.escape(class_name)}\s*\(\s*\{{",
        content[decl.start() :],
    )
    if ctor is None:
        return {"key"}
    open_paren = decl.start() + ctor.start() + content[decl.start() + ctor.start() :].find("(")
    close = _find_matching_paren(content, open_paren)
    if close is None:
        return set()
    header = content[open_paren : close + 1]
    params = {match.group("name") for match in _CTOR_PARAM_RE.finditer(header)}
    params.add("key")
    return params


def _extract_named_args_from_call(source: str, start: int) -> set[str]:
    open_paren = source.find("(", start)
    if open_paren == -1:
        return set()
    close = _find_matching_paren(source, open_paren)
    if close is None:
        return set()
    block = source[open_paren : close + 1]
    return {match.group("name") for match in _NAMED_ARG_RE.finditer(block)}


def find_widget_callsite_constructor_mismatches(planned: Mapping[str, str]) -> list[str]:
    """List layout/screen/widget callsites passing named args absent from constructors."""
    class_paths = _widget_class_paths(planned)
    ctor_params = {
        class_name: _extract_constructor_param_names(planned[path], class_name)
        for class_name, path in class_paths.items()
    }
    errors: list[str] = []
    for path, content in planned.items():
        normalized = path.replace("\\", "/")
        if not normalized.endswith(".dart"):
            continue
        if not normalized.startswith(_CONSUMER_PATH_PREFIXES):
            continue
        for class_name in class_paths:
            search_from = 0
            while True:
                idx = content.find(f"{class_name}(", search_from)
                if idx == -1:
                    break
                named = _extract_named_args_from_call(content, idx)
                declared = ctor_params.get(class_name, set())
                unknown = sorted(arg for arg in named if arg not in declared)
                if unknown:
                    errors.append(
                        f"widget_callsite_matches_constructor: {normalized} calls "
                        f"{class_name} with unknown named args {unknown}"
                    )
                search_from = idx + len(class_name) + 1
    return errors


def find_extracted_widget_empty_or_recursive_shells(planned: Mapping[str, str]) -> list[str]:
    """List agent widgets whose build is shrink-only or unresolved delegate shell."""
    from figma_flutter_agent.generator.planned.reconcile.delegate_repair import (
        _is_foreign_delegate_widget_build,
        _is_self_referential_widget_build,
    )

    errors: list[str] = []
    class_paths = _widget_class_paths(planned)
    for class_name, path in class_paths.items():
        content = planned.get(path, "")
        rel = path.replace("\\", "/")
        if _is_self_referential_widget_build(content, class_name):
            errors.append(
                f"visible_extracted_must_not_emit_empty_or_recursive_shell: "
                f"{rel} build is self-referential"
            )
            continue
        if _is_foreign_delegate_widget_build(content, class_name):
            errors.append(
                f"visible_extracted_must_not_emit_empty_or_recursive_shell: "
                f"{rel} build is unresolved foreign delegate"
            )
            continue
        build = _widget_build_snippet(content, class_name)
        compact = re.sub(r"\s+", "", build)
        if "SizedBox.shrink()" in compact and not re.search(
            r"\b(Row|Column|Stack|Container|Expanded|Flexible|ClipRRect|Material)\s*\(",
            build,
        ):
            errors.append(
                f"visible_extracted_must_not_emit_empty_or_recursive_shell: "
                f"{rel} build returns only SizedBox.shrink"
            )
    return errors


def find_loose_flex_infinite_width_violations(planned: Mapping[str, str]) -> list[str]:
    """Detect ``Flexible(loose)`` descendants forcing ``width: double.infinity``."""
    from figma_flutter_agent.generator.layout.flex_policy.wrap import (
        _FLEX_PARENT_DATA_START_RE,
    )

    errors: list[str] = []
    for path, content in planned.items():
        rel = path.replace("\\", "/")
        if not rel.endswith(".dart"):
            continue
        pos = 0
        while pos < len(content):
            match = _FLEX_PARENT_DATA_START_RE.search(content, pos)
            if match is None:
                break
            start = match.start()
            if start >= 6 and content[start - 6 : start] == "const ":
                start -= 6
            open_paren = content.find("(", start)
            if open_paren < 0:
                pos = match.end()
                continue
            end = _find_matching_paren(content, open_paren)
            if end is None:
                pos = match.end()
                continue
            expr = content[start : end + 1]
            trimmed = expr.lstrip()
            if trimmed.startswith("Flexible(") and "width: double.infinity" in expr:
                if "fit: FlexFit.tight" not in expr:
                    errors.append(
                        f"row_flex_child_must_not_force_infinite_width: {rel} near offset {start}"
                    )
            pos = end + 1
    return errors


def find_nested_flex_parent_data_wrappers(planned: Mapping[str, str]) -> list[str]:
    """Detect ``Expanded``/``Flexible`` nested inside another flex parent-data wrapper."""
    from figma_flutter_agent.generator.layout.flex_policy.wrap import (
        _FLEX_PARENT_DATA_START_RE,
        _unwrap_flex_parent_data_wrapper,
    )

    errors: list[str] = []
    for path, content in planned.items():
        rel = path.replace("\\", "/")
        if not rel.endswith(".dart"):
            continue
        pos = 0
        while pos < len(content):
            match = _FLEX_PARENT_DATA_START_RE.search(content, pos)
            if match is None:
                break
            start = match.start()
            if start >= 6 and content[start - 6 : start] == "const ":
                start -= 6
            open_paren = content.find("(", start)
            if open_paren < 0:
                pos = match.end()
                continue
            end = _find_matching_paren(content, open_paren)
            if end is None:
                pos = match.end()
                continue
            expr = content[start : end + 1]
            outer = _unwrap_flex_parent_data_wrapper(expr.strip())
            if outer is not None and _unwrap_flex_parent_data_wrapper(outer[1].strip()) is not None:
                errors.append(
                    "generated_dart_must_not_contain_nested_flex_parent_data_wrappers: "
                    f"{rel} near offset {start}"
                )
            pos = end + 1
    return errors


def run_static_contract_gates(planned: Mapping[str, str]) -> None:
    """Run deterministic planned-Dart invariants before analyze/write.

    Args:
        planned: Relative project paths mapped to generated Dart sources.

    Raises:
        PlannedDartGraphError: When a static contract gate fails.
    """
    from figma_flutter_agent.generator.planned.reconcile.class_inspect import (
        find_missing_planned_widget_classes,
    )
    from figma_flutter_agent.generator.planned.reconcile.imports import (
        find_stale_widget_package_imports,
    )

    violations: list[str] = []

    stale_imports = find_stale_widget_package_imports(planned)
    violations.extend(stale_imports)

    missing_widgets = find_missing_planned_widget_classes(planned)
    for item in missing_widgets:
        violations.append(f"widget_ref_implies_def: {item}")

    for cycle in find_planned_widget_invocation_cycles(planned):
        preview = " -> ".join(cycle)
        violations.append(f"planned_widget_graph_acyclic: cycle {preview}")

    violations.extend(find_widget_callsite_constructor_mismatches(planned))
    violations.extend(find_extracted_widget_empty_or_recursive_shells(planned))
    violations.extend(find_nested_flex_parent_data_wrappers(planned))
    violations.extend(find_loose_flex_infinite_width_violations(planned))

    if not violations:
        return
    preview = "; ".join(violations[:8])
    if len(violations) > 8:
        preview += f" (+{len(violations) - 8} more)"
    raise PlannedDartGraphError(f"Static contract gates failed: {preview}")


def active_screen_disk_seed_paths(
    feature_name: str,
    *,
    architecture: str = "feature_first",
) -> tuple[str, ...]:
    """Return on-disk Dart paths that seed pre-launch import closure for one screen."""
    from figma_flutter_agent.generator.paths import screen_file_path

    return (
        f"lib/generated/{feature_name}_layout.dart",
        screen_file_path(feature_name, architecture=architecture),
    )


def gate_disk_widget_import_closure(
    project_dir,
    *,
    package_name: str | None = None,
    feature_name: str | None = None,
    architecture: str = "feature_first",
) -> None:
    """Fail when on-disk widget imports reference missing ``lib/widgets`` files.

    When *feature_name* is set, only the active screen layout, feature screen,
    and their widget import closure are validated so unrelated screen fossils do
    not block launch.

    Args:
        project_dir: Flutter project root.
        package_name: Optional pubspec package name override.
        feature_name: Optional active screen slug for scoped pre-launch scan.
        architecture: Project layout architecture for resolving screen paths.

    Raises:
        PlannedDartGraphError: When stale widget imports remain on disk.
    """
    from pathlib import Path

    from figma_flutter_agent.generator.dart.package_name import (
        infer_project_package_name_from_sources,
    )
    from figma_flutter_agent.generator.dart.project_validation.write_analyze import (
        expand_planned_package_import_closure,
    )
    from figma_flutter_agent.generator.planned.reconcile.imports import (
        find_stale_widget_package_imports,
    )

    root = Path(project_dir)
    catalog = load_disk_agent_dart_sources(root)
    if not catalog:
        return
    resolved_package = package_name or infer_project_package_name_from_sources(
        list(catalog.values())
    )
    if feature_name:
        seeds = {
            path: catalog[path]
            for path in active_screen_disk_seed_paths(feature_name, architecture=architecture)
            if path in catalog
        }
        if not seeds:
            return
        scan_map = expand_planned_package_import_closure(
            seeds,
            catalog,
            package_name=resolved_package,
        )
    else:
        scan_map = catalog
    stale = find_stale_widget_package_imports(scan_map)
    if not stale:
        return
    preview = "; ".join(stale[:5])
    if len(stale) > 5:
        preview += f" (+{len(stale) - 5} more)"
    raise PlannedDartGraphError(f"pre_launch_stale_import_scan: {preview}")


def load_disk_agent_dart_sources(project_dir) -> dict[str, str]:
    """Load agent-owned Dart sources from disk for pre-launch import scans."""
    from pathlib import Path

    root = Path(project_dir)
    sources: dict[str, str] = {}
    patterns = (
        root / "lib" / "widgets",
        root / "lib" / "generated",
        root / "lib" / "features",
    )
    for base in patterns:
        if not base.is_dir():
            continue
        for dart_file in base.rglob("*.dart"):
            rel = dart_file.relative_to(root).as_posix()
            try:
                sources[rel] = dart_file.read_text(encoding="utf-8")
            except OSError:
                continue
    return sources
