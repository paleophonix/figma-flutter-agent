"""Enrich isolated golden-capture workspaces from the live Flutter project."""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from pathlib import Path

from loguru import logger
from ruamel.yaml import YAML


def enrich_planned_from_project(
    planned: Mapping[str, str],
    project_dir: Path,
) -> dict[str, str]:
    """Merge on-disk widgets, drop inline stubs, and wire imports for golden capture."""
    from figma_flutter_agent.generator.planned.reconcile import (
        ensure_referenced_widget_imports,
        hydrate_planned_widget_files_from_project,
        strip_inline_widget_duplicates_from_screens,
    )

    updated = hydrate_planned_widget_files_from_project(dict(planned), project_dir)
    updated = strip_inline_widget_duplicates_from_screens(updated)
    return ensure_referenced_widget_imports(updated)


def sync_pubspec_asset_directories(project_dir: Path, source_project: Path) -> None:
    """Copy every ``assets/<dir>/`` tree declared in the source pubspec."""
    source_pubspec = source_project / "pubspec.yaml"
    if not source_pubspec.is_file():
        return
    yaml = YAML()
    data = yaml.load(source_pubspec.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return
    flutter_section = data.get("flutter")
    if not isinstance(flutter_section, dict):
        return
    assets = flutter_section.get("assets")
    if not isinstance(assets, list):
        return
    for item in assets:
        normalized = str(item).replace("\\", "/")
        if not normalized.endswith("/"):
            continue
        rel_dir = normalized.rstrip("/")
        source_dir = source_project / rel_dir
        if not source_dir.is_dir():
            logger.debug("Golden enrich: source asset dir missing: {}", source_dir)
            continue
        destination = project_dir / rel_dir
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source_dir, destination)
        logger.info(
            "Golden capture: copied asset tree {} ({} files)",
            rel_dir,
            sum(1 for _ in destination.rglob("*") if _.is_file()),
        )


def sync_flutter_test_config(capture_dir: Path, source_project: Path) -> None:
    """Copy ``test/flutter_test_config.dart`` when the target app defines font loading."""
    source = source_project / "test" / "flutter_test_config.dart"
    if not source.is_file():
        return
    destination = capture_dir / "test" / "flutter_test_config.dart"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    logger.debug("Golden capture: copied {}", source.name)
