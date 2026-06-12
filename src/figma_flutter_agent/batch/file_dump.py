"""Download a full Figma file in one API call and slice screen dumps."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from figma_flutter_agent.batch.dump_mode import (
    BatchDumpMode,
    DumpWritePolicy,
    assets_attempted,
    plan_for_mode,
    resolve_batch_dump_mode,
    resolve_skip_existing_screens,
    skip_existing_assets,
)
from figma_flutter_agent.batch.frames import discover_page_level_frames
from figma_flutter_agent.batch.manifest import (
    BatchManifest,
    ScreenEntry,
    default_dump_path,
    write_batch_manifest,
)
from figma_flutter_agent.batch.screen_report import (
    ScreenDownloadReport,
    build_screen_download_reports,
)
from figma_flutter_agent.debug.paths import full_file_dump_path
from figma_flutter_agent.figma.client import FigmaConnector
from figma_flutter_agent.generator.layout.common import to_snake_case
from figma_flutter_agent.schemas import AssetManifest

if TYPE_CHECKING:
    from figma_flutter_agent.config import AssetsConfig


@dataclass(frozen=True)
class ScreenDumpEntry:
    """One screen extracted from a full-file dump."""

    feature: str
    node_id: str
    frame_name: str
    dump_path: Path


@dataclass
class FileDumpResult:
    """Outcome of a full-file dump operation."""

    file_key: str
    file_name: str | None
    full_file_path: Path
    screens: list[ScreenDumpEntry]
    manifest_path: Path | None = None
    asset_manifest: AssetManifest | None = None
    icon_count: int = 0
    raster_count: int = 0
    screen_reports: list[ScreenDownloadReport] = field(default_factory=list)
    orphan_exportables: int = 0
    rate_limited: bool = False
    mode: BatchDumpMode = BatchDumpMode.ALL


def _unique_feature_name(frame_name: str, node_id: str, used: dict[str, int]) -> str:
    base = to_snake_case(frame_name)
    if not base or base == "feature":
        base = f"screen_{node_id.replace(':', '_')}"
    count = used.get(base, 0)
    used[base] = count + 1
    if count == 0:
        return base
    return f"{base}_{count + 1}"


def _write_json(path: Path, payload: object, *, project_dir: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


async def dump_full_figma_file(
    connector: FigmaConnector,
    *,
    file_key: str,
    project_dir: Path,
    manifest_path: Path | None = None,
    write_manifest: bool = True,
    manifest_merge: bool = False,
    mode: BatchDumpMode | None = None,
    with_assets: bool | None = None,
    write_policy: DumpWritePolicy = DumpWritePolicy.REWRITE,
    skip_existing_screens: bool | None = None,
    assets: AssetsConfig | None = None,
) -> FileDumpResult:
    """Fetch or reuse a Figma file dump and optionally export media assets.

    Modes (``--mode``) split JSON and media API usage for free-tier quotas:

    - ``all``: one ``GET /v1/files/:key`` plus batched ``/images`` calls.
    - ``json``: file API only; writes screen dumps and manifest.
    - ``media`` / ``vector`` / ``raster``: read cached ``full_file_*.json``;
      no file API; export only the requested asset families via ``/images``.

    Args:
        connector: Active Figma connector.
        file_key: Figma file key.
        project_dir: Flutter project root for debug output and manifest.
        manifest_path: Target ``screens.yaml`` path; defaults to ``project_dir/screens.yaml``.
        write_manifest: When True, write or overwrite the batch manifest.
        manifest_merge: When True, merge discovered screens into an existing manifest
            instead of replacing it.
        skip_existing_screens: Keep existing ``.debug/raw/*_layout.json`` when write policy is
            ``skip-existing`` or this flag is set explicitly.
        write_policy: Rewrite all dumps/assets or skip files already on disk.
        mode: Dump mode; defaults to ``all`` or ``json`` from legacy ``with_assets``.
        with_assets: Legacy flag — ``False`` maps to ``json`` when ``mode`` is omitted.
        assets: Asset export settings; defaults to ``AssetsConfig()`` when omitted.

    Returns:
        ``FileDumpResult`` with paths to the full file, each screen dump, and assets.

    Raises:
        ValueError: When the file document is missing or contains no page-level frames.
        FileNotFoundError: When a media-only mode runs without a cached full-file dump.
    """
    from figma_flutter_agent.batch.asset_export import (
        AssetExportScope,
        export_assets_for_document,
        load_cached_file_document,
    )
    from figma_flutter_agent.config import AssetsConfig

    resolved_mode = resolve_batch_dump_mode(mode=mode, with_assets=with_assets)
    plan = plan_for_mode(resolved_mode)
    skip_screens = resolve_skip_existing_screens(
        write_policy=write_policy,
        skip_existing_screens=skip_existing_screens,
    )
    skip_assets = skip_existing_assets(write_policy)
    file_name: str | None = None

    if plan.fetch_json:
        file_response = await connector.fetch_file(file_key)
        document = file_response.document
        if not isinstance(document, dict):
            msg = f"Figma file {file_key} did not return a document payload."
            raise ValueError(msg)
        file_name = file_response.name

        full_file_path = full_file_dump_path(project_dir, file_key)
        _write_json(
            full_file_path,
            {
                "name": file_response.name,
                "document": document,
                "components": file_response.components,
                "componentSets": file_response.component_sets,
                "styles": file_response.styles,
            },
            project_dir=project_dir,
        )
        logger.info("Wrote full Figma file dump to {}", full_file_path.as_posix())
    else:
        document, file_name, full_file_path = load_cached_file_document(project_dir, file_key)
        logger.info("Using cached full Figma file dump at {}", full_file_path.as_posix())

    page_frames = discover_page_level_frames(document)
    if not page_frames:
        msg = (
            f"No page-level FRAME nodes found in Figma file {file_key}. "
            "Ensure screens are top-level frames on a page (not nested inside another frame)."
        )
        raise ValueError(msg)

    used_names: dict[str, int] = {}
    screens: list[ScreenDumpEntry] = []
    manifest_entries: list[ScreenEntry] = []
    screen_report_inputs: list[tuple[str, str, str, Path, bool]] = []

    for frame in page_frames:
        node_id = str(frame["id"])
        frame_name = str(frame.get("name") or node_id)
        feature = _unique_feature_name(frame_name, node_id, used_names)
        dump_path = default_dump_path(project_dir, feature)
        if plan.write_json:
            json_skipped = skip_screens and dump_path.is_file()
            if json_skipped:
                logger.info(
                    "Skipping existing screen dump for {} at {}", feature, dump_path.as_posix()
                )
            else:
                _write_json(dump_path, frame, project_dir=project_dir)
                logger.info(
                    "Wrote screen dump {} ({}) to {}", feature, node_id, dump_path.as_posix()
                )
        else:
            json_skipped = dump_path.is_file()
        entry = ScreenDumpEntry(
            feature=feature,
            node_id=node_id,
            frame_name=frame_name,
            dump_path=dump_path,
        )
        screens.append(entry)
        screen_report_inputs.append((feature, node_id, frame_name, dump_path, json_skipped))
        manifest_entries.append(
            ScreenEntry(
                feature=feature,
                node_id=node_id,
                dump=dump_path,
            )
        )

    resolved_manifest = manifest_path or (project_dir / "screens.yaml")
    if write_manifest and plan.write_json:
        new_manifest = BatchManifest(
            file_key=file_key,
            project_dir=project_dir,
            screens=tuple(manifest_entries),
        )
        if manifest_merge and resolved_manifest.is_file():
            from figma_flutter_agent.batch.manifest import (
                load_batch_manifest,
                merge_manifest_screens,
            )

            existing = load_batch_manifest(resolved_manifest)
            new_manifest = merge_manifest_screens(existing, new_manifest.screens)
        write_batch_manifest(resolved_manifest, new_manifest)
        logger.info(
            "Wrote batch manifest with {} screens to {}", len(screens), resolved_manifest.as_posix()
        )

    asset_manifest: AssetManifest | None = None
    icon_count = 0
    raster_count = 0
    exported_node_ids: set[str] = set()
    rate_limited = False
    if assets_attempted(plan):
        asset_settings = assets or AssetsConfig()
        asset_result = await export_assets_for_document(
            connector,
            file_key=file_key,
            document=document,
            project_dir=project_dir,
            assets=asset_settings,
            scope=AssetExportScope(
                export_svg=plan.export_svg,
                export_raster=plan.export_raster,
                export_blur_png=plan.export_blur_png,
            ),
            skip_existing_assets=skip_assets,
        )
        asset_manifest = asset_result.manifest
        icon_count = asset_result.icon_count
        raster_count = asset_result.raster_count
        exported_node_ids = set(asset_result.exported_node_ids)
        rate_limited = asset_result.rate_limited

    frames_by_id = {str(frame["id"]): frame for frame in page_frames}
    screen_reports, orphan_exportables = build_screen_download_reports(
        screen_report_inputs,
        frames_by_id=frames_by_id,
        exported_node_ids=exported_node_ids,
        assets_attempted=assets_attempted(plan),
    )

    return FileDumpResult(
        file_key=file_key,
        file_name=file_name,
        full_file_path=full_file_path,
        screens=screens,
        manifest_path=resolved_manifest if write_manifest and plan.write_json else None,
        asset_manifest=asset_manifest,
        icon_count=icon_count,
        raster_count=raster_count,
        screen_reports=screen_reports,
        orphan_exportables=len(orphan_exportables),
        rate_limited=rate_limited,
        mode=resolved_mode,
    )
