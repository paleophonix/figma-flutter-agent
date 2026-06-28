"""Frozen planned Dart graph: finalize, validate, and write projection."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from figma_flutter_agent.errors import GenerationError, PlannedDartGraphError

if TYPE_CHECKING:
    pass


@dataclass(frozen=True)
class PlannedDartGraph:
    """Immutable planned Dart sources after finalize and graph validation."""

    files: Mapping[str, str]
    content_hash: str


def planned_graph_content_hash(files: Mapping[str, str]) -> str:
    """Return a stable SHA-256 digest over sorted path/content pairs."""
    digest = hashlib.sha256()
    for path, content in sorted(
        (key.replace("\\", "/"), value) for key, value in files.items()
    ):
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(content.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def build_planned_dart_graph(planned: Mapping[str, str]) -> PlannedDartGraph:
    """Wrap a planned file map as a graph without running reconciliation."""
    files = dict(planned)
    return PlannedDartGraph(files=files, content_hash=planned_graph_content_hash(files))


def validate_planned_dart_graph(
    graph: PlannedDartGraph,
    *,
    package_name: str = "demo_app",
) -> None:
    """Run full planned-graph invariants; raise ``PlannedDartGraphError`` on failure.

    Args:
        graph: Frozen or candidate planned graph.
        package_name: Flutter package name for import closure checks.

    Raises:
        PlannedDartGraphError: When imports, widget manifest, or class references fail.
    """
    from figma_flutter_agent.generator.planned.reconcile import (
        ensure_planned_widget_import_closure,
        ensure_planned_widget_manifest,
        find_missing_planned_widget_classes,
    )

    planned = dict(graph.files)
    missing = find_missing_planned_widget_classes(planned)
    if missing:
        preview = "; ".join(missing[:8])
        if len(missing) > 8:
            preview += f" (+{len(missing) - 8} more)"
        raise PlannedDartGraphError(
            f"Planned Dart references widget classes without lib/widgets bodies: {preview}",
        )
    try:
        ensure_planned_widget_manifest(planned)
    except GenerationError as exc:
        raise PlannedDartGraphError(str(exc)) from exc
    _ = package_name
    ensure_planned_widget_import_closure(planned)
    from figma_flutter_agent.generator.dart.static_contract_gates import (
        run_static_contract_gates,
    )

    run_static_contract_gates(planned)


def finalize_planned_dart_graph(
    planned: dict[str, str],
    *,
    package_name: str = "demo_app",
    project_dir: Path | None = None,
    responsive_enabled: bool = True,
) -> PlannedDartGraph:
    """Apply write-time reconcile mutations once, then validate and freeze.

    Args:
        planned: Full planned Dart file map from plan/repair/refine.
        package_name: Flutter package name.
        project_dir: Target Flutter project root.
        responsive_enabled: Whether responsive layout delegates apply.

    Returns:
        Validated frozen planned graph.

    Raises:
        PlannedDartGraphError: When graph invariants fail after finalize.
    """
    from figma_flutter_agent.generator.planned.reconcile import (
        force_polluted_feature_screens_to_layout,
        sync_widget_consumer_imports,
    )

    merged = force_polluted_feature_screens_to_layout(
        dict(planned),
        package_name=package_name,
        responsive_enabled=responsive_enabled,
        project_dir=project_dir,
    )
    synced = sync_widget_consumer_imports(merged, skip_consolidate=True)
    graph = build_planned_dart_graph(synced)
    validate_planned_dart_graph(graph, package_name=package_name)
    return graph


def assert_planned_graph_unchanged(
    graph: PlannedDartGraph,
    candidate: Mapping[str, str],
    *,
    context: str,
) -> None:
    """Fail when a candidate map diverges from a frozen graph hash.

    Args:
        graph: Previously frozen graph.
        candidate: Map that must match the frozen content hash.
        context: Diagnostic label for error messages.

    Raises:
        PlannedDartGraphError: When content hash differs.
    """
    if planned_graph_content_hash(candidate) == graph.content_hash:
        return
    raise PlannedDartGraphError(
        f"Planned Dart graph mutated after freeze ({context})",
    )


def project_write_payload(
    graph: PlannedDartGraph,
    files_to_write: dict[str, str],
) -> dict[str, str]:
    """Project incremental write keys onto the frozen graph without mutation.

    Pulls in layout/screen/widget dependencies referenced by the write subset.

    Args:
        graph: Frozen full planned graph.
        files_to_write: Relative paths selected for incremental write.

    Returns:
        Write payload keyed by paths to commit.
    """
    from figma_flutter_agent.generator.planned.reconcile.class_inspect import (
        _widget_class_paths,
    )

    synced = dict(graph.files)
    prepared = {path: synced[path] for path in files_to_write if path in synced}
    for path in list(prepared):
        if path in synced:
            prepared[path] = synced[path]

    for path, content in synced.items():
        normalized = path.replace("\\", "/")
        if normalized.endswith("_layout.dart") or (
            normalized.startswith("lib/features/") and normalized.endswith("_screen.dart")
        ):
            if path in files_to_write:
                prepared[path] = content

    class_paths = _widget_class_paths(synced)
    for path, content in synced.items():
        normalized = path.replace("\\", "/")
        if not normalized.startswith("lib/widgets/"):
            continue
        if path in files_to_write:
            prepared[path] = content

    for path, content in list(synced.items()):
        normalized = path.replace("\\", "/")
        if not (
            normalized.endswith("_layout.dart")
            or (normalized.startswith("lib/features/") and normalized.endswith("_screen.dart"))
        ):
            continue
        if path not in prepared and path not in files_to_write:
            continue
        body = content
        for class_name, widget_path in class_paths.items():
            if re.search(rf"\b{re.escape(class_name)}\b", body):
                prepared[widget_path] = synced[widget_path]
    return prepared
