"""Batch dump modes that split JSON and media API usage."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class BatchDumpMode(StrEnum):
    """What to download during ``batch dump-file``."""

    ALL = "all"
    JSON = "json"
    MEDIA = "media"
    VECTOR = "vector"
    RASTER = "raster"


class DumpWritePolicy(StrEnum):
    """Whether to overwrite files already present on disk."""

    REWRITE = "rewrite"
    SKIP_EXISTING = "skip-existing"


_WRITE_POLICY_MENU: tuple[tuple[str, DumpWritePolicy], ...] = (
    (
        "skip existing — download only missing JSON/assets (checks local files, no extra API)",
        DumpWritePolicy.SKIP_EXISTING,
    ),
    ("rewrite all — overwrite existing dumps and assets", DumpWritePolicy.REWRITE),
)


@dataclass(frozen=True)
class BatchDumpPlan:
    """Resolved work plan for a batch dump mode."""

    fetch_json: bool
    write_json: bool
    export_svg: bool
    export_raster: bool
    export_blur_png: bool


_BATCH_DUMP_MENU: tuple[tuple[str, BatchDumpMode], ...] = (
    ("all — JSON + SVG + raster (1× file API + images API)", BatchDumpMode.ALL),
    ("json only — screen dumps, no /images calls", BatchDumpMode.JSON),
    ("media only — SVG + raster from cached JSON (images API only)", BatchDumpMode.MEDIA),
    ("vector only — SVG icons from cached JSON", BatchDumpMode.VECTOR),
    ("raster only — PNG fills + blur fallbacks from cached JSON", BatchDumpMode.RASTER),
)

_FRAME_FETCH_MENU: tuple[tuple[str, BatchDumpMode], ...] = (
    ("all — JSON dump + SVG + raster", BatchDumpMode.ALL),
    ("json only — layout dump, no /images calls", BatchDumpMode.JSON),
    ("assets only — SVG + raster from cached dump (images API only)", BatchDumpMode.MEDIA),
)


def plan_for_mode(mode: BatchDumpMode) -> BatchDumpPlan:
    """Return API/write plan for ``mode``."""
    if mode is BatchDumpMode.ALL:
        return BatchDumpPlan(
            fetch_json=True,
            write_json=True,
            export_svg=True,
            export_raster=True,
            export_blur_png=True,
        )
    if mode is BatchDumpMode.JSON:
        return BatchDumpPlan(
            fetch_json=True,
            write_json=True,
            export_svg=False,
            export_raster=False,
            export_blur_png=False,
        )
    if mode is BatchDumpMode.MEDIA:
        return BatchDumpPlan(
            fetch_json=False,
            write_json=False,
            export_svg=True,
            export_raster=True,
            export_blur_png=True,
        )
    if mode is BatchDumpMode.VECTOR:
        return BatchDumpPlan(
            fetch_json=False,
            write_json=False,
            export_svg=True,
            export_raster=False,
            export_blur_png=False,
        )
    return BatchDumpPlan(
        fetch_json=False,
        write_json=False,
        export_svg=False,
        export_raster=True,
        export_blur_png=True,
    )


def assets_attempted(plan: BatchDumpPlan) -> bool:
    """Return True when the plan exports any media assets."""
    return plan.export_svg or plan.export_raster or plan.export_blur_png


def batch_dump_menu_options() -> list[str]:
    """Return numbered menu labels for interactive batch dump."""
    return [label for label, _mode in _BATCH_DUMP_MENU]


def frame_fetch_menu_options() -> list[str]:
    """Return menu labels for interactive single-frame fetch scope."""
    return [label for label, _mode in _FRAME_FETCH_MENU]


def frame_fetch_mode_from_menu(label: str) -> BatchDumpMode:
    """Map an interactive frame-fetch menu label to ``BatchDumpMode``."""
    for option_label, mode in _FRAME_FETCH_MENU:
        if label == option_label:
            return mode
    msg = f"Unknown frame fetch menu option: {label!r}"
    raise ValueError(msg)


def batch_dump_mode_from_menu(label: str) -> BatchDumpMode:
    """Map an interactive menu label to ``BatchDumpMode``."""
    for option_label, mode in _BATCH_DUMP_MENU:
        if label == option_label:
            return mode
    msg = f"Unknown batch dump menu option: {label!r}"
    raise ValueError(msg)


def write_policy_menu_options() -> list[str]:
    """Return menu labels for rewrite vs skip-existing."""
    return [label for label, _policy in _WRITE_POLICY_MENU]


def write_policy_from_menu(label: str) -> DumpWritePolicy:
    """Map an interactive menu label to ``DumpWritePolicy``."""
    for option_label, policy in _WRITE_POLICY_MENU:
        if label == option_label:
            return policy
    msg = f"Unknown write policy menu option: {label!r}"
    raise ValueError(msg)


def default_write_policy(mode: BatchDumpMode) -> DumpWritePolicy:
    """Pick a sensible default write policy for ``mode``."""
    if mode in {BatchDumpMode.MEDIA, BatchDumpMode.VECTOR, BatchDumpMode.RASTER}:
        return DumpWritePolicy.SKIP_EXISTING
    return DumpWritePolicy.REWRITE


def resolve_skip_existing_screens(
    *,
    write_policy: DumpWritePolicy,
    skip_existing_screens: bool | None,
) -> bool:
    """Resolve screen JSON skip flag from policy and explicit CLI override."""
    if skip_existing_screens is not None:
        return skip_existing_screens
    return write_policy is DumpWritePolicy.SKIP_EXISTING


def skip_existing_assets(write_policy: DumpWritePolicy) -> bool:
    """Return True when asset export should skip files already on disk."""
    return write_policy is DumpWritePolicy.SKIP_EXISTING


def resolve_batch_dump_mode(
    *,
    mode: BatchDumpMode | None,
    with_assets: bool | None,
) -> BatchDumpMode:
    """Resolve CLI mode from ``--mode`` or legacy ``--with-assets/--json-only``."""
    if mode is not None:
        return mode
    if with_assets is False:
        return BatchDumpMode.JSON
    return BatchDumpMode.ALL
