"""Screen asset export gap detection aligned with the generation pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from loguru import logger

from figma_flutter_agent.assets.collect import collect_exportable_nodes
from figma_flutter_agent.assets.composite_icons import collect_figma_composite_icon_groups
from figma_flutter_agent.assets.effects import index_figma_nodes
from figma_flutter_agent.assets.eligibility import figma_images_api_skip_export
from figma_flutter_agent.assets.names import expected_svg_export_rel_path
from figma_flutter_agent.assets.screen_frame import build_screen_frame_exclude_ids
from figma_flutter_agent.config import AssetsConfig
from figma_flutter_agent.parser.boundaries.assets import (
    build_asset_node_index,
    collect_render_boundary_asset_plan,
    lookup_asset_path_for_node,
)
from figma_flutter_agent.pipeline.dump import load_fetch_result_from_dump
from figma_flutter_agent.schemas import CleanDesignTreeNode
from figma_flutter_agent.stages.fetch import FigmaFetchResult
from figma_flutter_agent.stages.parse import FigmaParseResult, parse_figma_frame

SvgExportKind = Literal["icon", "boundary_svg"]


@dataclass(frozen=True)
class ScreenAssetGapPartition:
    """Missing screen asset exports split by recoverability."""

    downloadable_missing_ids: frozenset[str]
    api_unexportable_ids: frozenset[str]
    boundary_missing_ids: frozenset[str]

    @property
    def total_missing(self) -> int:
        """Count all missing export slots (downloadable, blur, and boundary)."""
        return (
            len(self.downloadable_missing_ids)
            + len(self.api_unexportable_ids)
            + len(self.boundary_missing_ids)
        )

    @property
    def check_blocking_missing(self) -> int:
        """Missing exports that should fail wizard asset check."""
        return len(self.downloadable_missing_ids)


@dataclass(frozen=True)
class ScreenSvgExportExpectation:
    """One SVG export the screen pipeline expects on disk."""

    node_id: str
    layer_name: str
    kind: SvgExportKind

    @property
    def expected_rel_path(self) -> str:
        """Project-relative path used by ``AssetExporter`` for this node."""
        return expected_svg_export_rel_path(self.layer_name, self.node_id, self.kind)


def collect_screen_svg_export_entries(
    figma_root: dict,
    clean_tree: CleanDesignTreeNode,
    *,
    exclude_node_ids: frozenset[str],
    illustrations_enabled: bool = True,
) -> tuple[ScreenSvgExportExpectation, ...]:
    """Return planned icon and render-boundary SVG exports for one parsed screen."""
    boundary_exports, flatten_excludes = collect_render_boundary_asset_plan(clean_tree)
    exportables = collect_exportable_nodes(
        figma_root,
        illustrations_enabled=illustrations_enabled,
        exclude_node_ids=set(exclude_node_ids),
        flatten_exclude_node_ids=set(flatten_excludes),
        render_boundary_node_ids=set(boundary_exports),
    )
    return tuple(
        ScreenSvgExportExpectation(node_id=node_id, layer_name=name, kind=kind)
        for node_id, name, kind in exportables
        if kind in {"icon", "boundary_svg"}
    )


def exportable_icon_ids_for_tree(
    figma_root: dict,
    clean_tree: CleanDesignTreeNode,
    *,
    exclude_node_ids: frozenset[str],
    illustrations_enabled: bool = True,
) -> frozenset[str]:
    """Return Figma node ids that should have on-disk exports for one screen.

    Uses the same ``collect_exportable_nodes`` filters as ``AssetExporter``:
    screen-frame excludes, render-boundary flatten excludes, and boundary ids.
    """
    return frozenset(
        entry.node_id
        for entry in collect_screen_svg_export_entries(
            figma_root,
            clean_tree,
            exclude_node_ids=exclude_node_ids,
            illustrations_enabled=illustrations_enabled,
        )
    )


def icon_ids_covered_on_disk(
    project_dir: Path,
    node_ids: frozenset[str],
    *,
    asset_index: dict[str, str] | None = None,
) -> frozenset[str]:
    """Return the subset of ``node_ids`` with a resolvable asset file under ``project_dir``."""
    index = asset_index if asset_index is not None else build_asset_node_index(project_dir)
    covered: set[str] = set()
    for node_id in node_ids:
        if lookup_asset_path_for_node(index, node_id) is not None:
            covered.add(node_id)
    return frozenset(covered)


def resolve_screen_asset_export_entries(
    *,
    dump_path: Path,
    file_key: str,
    primary_node_id: str,
    assets: AssetsConfig,
) -> tuple[ScreenSvgExportExpectation, ...]:
    """Parse a cached dump and return expected SVG exports for wizard diagnostics."""
    fetch_result = load_fetch_result_from_dump(
        dump_path,
        file_key=file_key,
        node_id=primary_node_id,
    )
    return resolve_asset_export_entries_from_fetch(
        fetch_result,
        primary_node_id=primary_node_id,
        assets=assets,
    )


def resolve_asset_export_entries_from_fetch(
    fetch_result: FigmaFetchResult,
    *,
    primary_node_id: str,
    assets: AssetsConfig,
    parse_result: FigmaParseResult | None = None,
    dev_mode_dump: object | None = None,
    dev_mode_css_override: bool = False,
) -> tuple[ScreenSvgExportExpectation, ...]:
    """Return expected SVG exports for a parsed or fallback fetch payload."""
    parsed = parse_result
    if parsed is None:
        try:
            parsed = parse_figma_frame(
                fetch_result,
                dev_mode_dump=dev_mode_dump,
                dev_mode_css_override=dev_mode_css_override,
            )
        except Exception:
            logger.exception("Preflight asset gap fell back to raw dump collect (parse failed)")
            exclude_node_ids = build_screen_frame_exclude_ids(primary_node_id)
            exportables = collect_exportable_nodes(
                fetch_result.root,
                illustrations_enabled=assets.illustrations,
                exclude_node_ids=set(exclude_node_ids),
            )
            return tuple(
                ScreenSvgExportExpectation(node_id=node_id, layer_name=name, kind="icon")
                for node_id, name, kind in exportables
                if kind == "icon"
            )

    exclude_node_ids = build_screen_frame_exclude_ids(primary_node_id)
    return collect_screen_svg_export_entries(
        fetch_result.root,
        parsed.clean_tree,
        exclude_node_ids=exclude_node_ids,
        illustrations_enabled=assets.illustrations,
    )


def resolve_screen_asset_icon_gap(
    *,
    dump_path: Path,
    project_dir: Path,
    file_key: str,
    primary_node_id: str,
    assets: AssetsConfig,
) -> tuple[frozenset[str], frozenset[str]]:
    """Parse a cached dump and compare expected vs on-disk icon exports.

    Args:
        dump_path: Raw Figma frame JSON used by offline runs.
        project_dir: Flutter project root containing ``assets/``.
        file_key: Figma file key for fetch replay.
        primary_node_id: Screen frame node id excluded from export.
        assets: Agent asset settings (illustrations toggle).

    Returns:
        Tuple of ``(expected_icon_ids, covered_icon_ids)``.
    """
    fetch_result = load_fetch_result_from_dump(
        dump_path,
        file_key=file_key,
        node_id=primary_node_id,
    )
    return resolve_asset_icon_gap_from_fetch(
        fetch_result,
        project_dir=project_dir,
        primary_node_id=primary_node_id,
        assets=assets,
    )


def resolve_asset_icon_gap_from_fetch(
    fetch_result: FigmaFetchResult,
    *,
    project_dir: Path,
    primary_node_id: str,
    assets: AssetsConfig,
    parse_result: FigmaParseResult | None = None,
    dev_mode_dump: object | None = None,
    dev_mode_css_override: bool = False,
    asset_index: dict[str, str] | None = None,
) -> tuple[frozenset[str], frozenset[str]]:
    """Compare expected vs on-disk icon exports for a parsed fetch payload."""
    entries = resolve_asset_export_entries_from_fetch(
        fetch_result,
        primary_node_id=primary_node_id,
        assets=assets,
        parse_result=parse_result,
        dev_mode_dump=dev_mode_dump,
        dev_mode_css_override=dev_mode_css_override,
    )
    expected = frozenset(entry.node_id for entry in entries)
    covered = icon_ids_covered_on_disk(project_dir, expected, asset_index=asset_index)
    return expected, covered


def partition_missing_asset_entries(
    entries: tuple[ScreenSvgExportExpectation, ...],
    covered: frozenset[str],
    figma_root: dict,
) -> ScreenAssetGapPartition:
    """Split missing exports into downloadable icons, blur API skips, and boundaries."""
    figma_nodes = index_figma_nodes(figma_root)
    composite_parents, _composite_skip = collect_figma_composite_icon_groups(figma_root)
    downloadable: set[str] = set()
    unexportable: set[str] = set()
    boundary_missing: set[str] = set()
    for entry in entries:
        if entry.node_id in covered:
            continue
        if entry.kind == "boundary_svg":
            boundary_missing.add(entry.node_id)
            continue
        raw_node = figma_nodes.get(entry.node_id, {})
        if figma_images_api_skip_export(
            raw_node,
            node_id=entry.node_id,
            composite_parent_ids=composite_parents,
        ):
            unexportable.add(entry.node_id)
        else:
            downloadable.add(entry.node_id)
    return ScreenAssetGapPartition(
        downloadable_missing_ids=frozenset(downloadable),
        api_unexportable_ids=frozenset(unexportable),
        boundary_missing_ids=frozenset(boundary_missing),
    )


def resolve_screen_asset_gap_detail(
    fetch_result: FigmaFetchResult,
    *,
    project_dir: Path,
    primary_node_id: str,
    assets: AssetsConfig,
    parse_result: FigmaParseResult | None = None,
    dev_mode_dump: object | None = None,
    dev_mode_css_override: bool = False,
    asset_index: dict[str, str] | None = None,
) -> tuple[tuple[ScreenSvgExportExpectation, ...], frozenset[str], ScreenAssetGapPartition]:
    """Return export entries, covered ids, and a partitioned missing gap report."""
    entries = resolve_asset_export_entries_from_fetch(
        fetch_result,
        primary_node_id=primary_node_id,
        assets=assets,
        parse_result=parse_result,
        dev_mode_dump=dev_mode_dump,
        dev_mode_css_override=dev_mode_css_override,
    )
    expected = frozenset(entry.node_id for entry in entries)
    index = asset_index if asset_index is not None else build_asset_node_index(project_dir)
    covered = icon_ids_covered_on_disk(project_dir, expected, asset_index=index)
    partition = partition_missing_asset_entries(entries, covered, fetch_result.root)
    return entries, covered, partition
