"""Infer Flutter pubspec package name from generated Dart import URIs."""

from __future__ import annotations

import re

_EXTERNAL_PACKAGE_NAMES = frozenset(
    {
        "auto_route",
        "cupertino_icons",
        "flutter",
        "flutter_bloc",
        "flutter_riverpod",
        "flutter_svg",
        "go_router",
        "meta",
        "provider",
        "riverpod",
    }
)

_PROJECT_LIB_SEGMENTS = frozenset(
    {
        "core",
        "features",
        "generated",
        "presentation",
        "theme",
        "widgets",
    }
)

_PACKAGE_IMPORT_URI_RE = re.compile(
    r"import\s+'package:(?P<package>[^/']+)/(?P<subpath>[^']+)'"
)


def infer_project_package_name(
    source: str,
    *,
    default: str = "demo_app",
) -> str:
    """Return the pubspec package name for project-local imports in *source*.

    Third-party dependencies (for example ``flutter_svg``) are ignored even when
    they appear before ``package:<app>/theme/...`` imports in the file header.

    Args:
        source: Dart source to scan for ``package:`` import URIs.
        default: Fallback when no project package import is found.

    Returns:
        Inferred pubspec ``name`` for project-local ``lib/`` imports.
    """
    project_local: list[str] = []
    other_non_external: list[str] = []
    for match in _PACKAGE_IMPORT_URI_RE.finditer(source):
        package = match.group("package")
        top_segment = match.group("subpath").split("/", 1)[0]
        if package in _EXTERNAL_PACKAGE_NAMES:
            continue
        if top_segment in _PROJECT_LIB_SEGMENTS:
            project_local.append(package)
        else:
            other_non_external.append(package)
    if project_local:
        return project_local[0]
    if other_non_external:
        return other_non_external[0]
    return default


def infer_project_package_name_from_sources(
    sources: list[str],
    *,
    default: str = "demo_app",
) -> str:
    """Scan multiple Dart sources and return the first inferred project package."""
    for source in sources:
        inferred = infer_project_package_name(source, default="")
        if inferred:
            return inferred
    return default
