"""Write-stage analyze workspace resolution for incremental sync."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

_PACKAGE_IMPORT_URI_RE = re.compile(
    r"import\s+['\"]package:(?P<package>[^/']+)/(?P<subpath>[^'\"]+)['\"]"
)


def _package_import_to_lib_path(package_name: str, subpath: str) -> str:
    normalized = subpath.replace("\\", "/")
    if not normalized.endswith(".dart"):
        normalized = f"{normalized}.dart"
    return f"lib/{normalized}"


def expand_planned_package_import_closure(
    seeds: dict[str, str],
    catalog: dict[str, str],
    *,
    package_name: str,
) -> dict[str, str]:
    """Return *seeds* plus catalog entries for in-project ``package:`` imports.

    Args:
        seeds: Initial relative Dart paths and contents for analyze.
        catalog: Full planned-project sources used to satisfy import dependencies.
        package_name: Expected pubspec package name for project-local imports.

    Returns:
        Expanded mapping including transitive ``lib/`` dependencies from *catalog*.
    """
    resolved = dict(seeds)
    pending = list(seeds.keys())
    while pending:
        path = pending.pop()
        content = resolved.get(path)
        if content is None:
            continue
        for match in _PACKAGE_IMPORT_URI_RE.finditer(content):
            if match.group("package") != package_name:
                continue
            dep_path = _package_import_to_lib_path(package_name, match.group("subpath"))
            if dep_path in resolved or dep_path not in catalog:
                continue
            resolved[dep_path] = catalog[dep_path]
            pending.append(dep_path)
    return resolved


def resolve_planned_for_write_analyze(
    analyze_paths: Iterable[str],
    *,
    files_to_write: dict[str, str],
    planned_catalog: dict[str, str] | None,
    project_dir: Path,
    package_name: str,
) -> dict[str, str]:
    """Build the planned Dart map for write-stage ``dart analyze``.

    Resolution order per path: staged write payload, on-disk project file, then
    the full planned catalog from the current pipeline run. Package-import
    closure adds any additional ``lib/`` dependencies required by the seed set.

    Args:
        analyze_paths: Relative Dart paths selected for analyze.
        files_to_write: Staged write payload for this commit.
        planned_catalog: Full planned files from the current generation run.
        project_dir: Flutter project root for on-disk fallbacks.
        package_name: Pubspec package name for import closure.

    Returns:
        Relative paths mapped to Dart source text for analyze workspace emit.
    """
    catalog = dict(planned_catalog or {})
    catalog.update(files_to_write)
    seeds: dict[str, str] = {}
    for relative in analyze_paths:
        normalized = relative.replace("\\", "/")
        if normalized in files_to_write:
            seeds[normalized] = files_to_write[normalized]
            continue
        disk_path = project_dir / normalized
        if disk_path.is_file():
            seeds[normalized] = disk_path.read_text(encoding="utf-8")
            catalog.setdefault(normalized, seeds[normalized])
            continue
        if normalized in catalog:
            seeds[normalized] = catalog[normalized]
    return expand_planned_package_import_closure(
        seeds,
        catalog,
        package_name=package_name,
    )
