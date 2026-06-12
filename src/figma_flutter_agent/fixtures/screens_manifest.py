"""Load canonical screen fixtures from ``tests/fixtures/screens.yaml``."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from ruamel.yaml import YAML

from figma_flutter_agent.errors import FigmaFlutterError
from figma_flutter_agent.schemas import CleanDesignTreeNode

_LEGACY_DEFAULT_ORACLE_MODES = frozenset({"strict_geometry", "strict_pixel"})

_FIXTURES_ROOT = Path(__file__).resolve().parents[3] / "tests" / "fixtures"
_MANIFEST_PATH = _FIXTURES_ROOT / "screens.yaml"

CorpusTier = Literal["strict_pixel_blocking", "advisory_pixel", "semantic_only"]


class OracleThresholds(BaseModel):
    """Per-fixture oracle thresholds for corpus gates."""

    model_config = ConfigDict(extra="forbid")

    non_text_pixel_max: float = 0.05
    geometry_iou_min: float = 0.95
    text_bounds_delta_max: float = 3.0
    text_region_pixel_max: float = 0.15


class ScreenFixtureEntry(BaseModel):
    """One screen entry from the fixtures manifest."""

    model_config = ConfigDict(extra="forbid")

    id: str
    layout: str
    feature: str
    golden_id: str | None = None
    description: str = ""
    ac2: bool = False
    corpus_tier: CorpusTier = "advisory_pixel"
    oracle_modes: list[str] = Field(
        default_factory=lambda: ["strict_geometry", "strict_pixel"],
    )
    thresholds: OracleThresholds = Field(default_factory=OracleThresholds)
    w1_case: bool = False

    @model_validator(mode="after")
    def _validate_tier_contract(self) -> ScreenFixtureEntry:
        if self.corpus_tier == "semantic_only":
            mode_set = set(self.oracle_modes)
            if mode_set <= _LEGACY_DEFAULT_ORACLE_MODES:
                self.oracle_modes = ["semantic"]
            elif mode_set & _LEGACY_DEFAULT_ORACLE_MODES:
                msg = (
                    f"semantic_only fixture {self.id!r} cannot use strict_geometry or "
                    "strict_pixel without removing semantic_only tier"
                )
                raise ValueError(msg)
        if self.corpus_tier == "strict_pixel_blocking" and self.golden_id is None:
            msg = f"strict_pixel_blocking fixture {self.id!r} requires golden_id"
            raise ValueError(msg)
        return self


class ScreensManifest(BaseModel):
    """Parsed ``screens.yaml`` document."""

    model_config = ConfigDict(extra="forbid")

    version: int = 1
    screens: list[ScreenFixtureEntry] = Field(default_factory=list)


def fixtures_root() -> Path:
    """Return the ``tests/fixtures`` directory path."""
    return _FIXTURES_ROOT


def manifest_path() -> Path:
    """Return the canonical ``screens.yaml`` path."""
    return _MANIFEST_PATH


@lru_cache(maxsize=1)
def load_screens_manifest(path: Path | None = None) -> ScreensManifest:
    """Load and validate the screen fixtures manifest.

    Args:
        path: Optional override path (defaults to ``tests/fixtures/screens.yaml``).

    Returns:
        Parsed manifest model.

    Raises:
        FigmaFlutterError: When the manifest file is missing or invalid.
    """
    resolved = (path or _MANIFEST_PATH).expanduser().resolve()
    if not resolved.is_file():
        raise FigmaFlutterError(f"Screen fixtures manifest not found: {resolved}")
    yaml_loader = YAML(typ="safe")
    raw: dict[str, Any] = yaml_loader.load(resolved.read_text(encoding="utf-8")) or {}
    try:
        manifest = ScreensManifest.model_validate(raw)
    except Exception as exc:
        raise FigmaFlutterError(f"Invalid screens manifest: {resolved}") from exc
    for entry in manifest.screens:
        layout_path = resolved.parent / entry.layout
        if not layout_path.is_file():
            raise FigmaFlutterError(f"Layout fixture missing for {entry.id}: {layout_path}")
    return manifest


def iter_by_tier(
    tier: CorpusTier,
    *,
    manifest: ScreensManifest | None = None,
) -> list[ScreenFixtureEntry]:
    """Return manifest entries matching ``tier``."""
    doc = manifest or load_screens_manifest()
    return [entry for entry in doc.screens if entry.corpus_tier == tier]


def blocking_screens(*, manifest: ScreensManifest | None = None) -> list[ScreenFixtureEntry]:
    """Return entries tagged ``strict_pixel_blocking``."""
    return iter_by_tier("strict_pixel_blocking", manifest=manifest)


def screens_with_golden(*, manifest: ScreensManifest | None = None) -> list[ScreenFixtureEntry]:
    """Return entries that have a committed golden baseline id."""
    doc = manifest or load_screens_manifest()
    return [entry for entry in doc.screens if entry.golden_id is not None]


def load_layout_tree(
    entry: ScreenFixtureEntry | str,
    *,
    manifest: ScreensManifest | None = None,
    fixtures_dir: Path | None = None,
) -> CleanDesignTreeNode:
    """Load a clean design tree JSON layout for a manifest entry.

    Args:
        entry: Screen id or manifest entry.
        manifest: Optional pre-loaded manifest.
        fixtures_dir: Optional fixtures root (defaults to ``tests/fixtures``).

    Returns:
        Parsed clean design tree root node.

    Raises:
        FigmaFlutterError: When the entry or layout file is missing.
    """
    root = fixtures_dir or _FIXTURES_ROOT
    doc = manifest or load_screens_manifest(root / "screens.yaml")
    resolved_entry: ScreenFixtureEntry | None
    if isinstance(entry, str):
        resolved_entry = next((s for s in doc.screens if s.id == entry), None)
        if resolved_entry is None:
            raise FigmaFlutterError(f"Unknown screen fixture id: {entry}")
    else:
        resolved_entry = entry
    layout_path = root / resolved_entry.layout
    if not layout_path.is_file():
        raise FigmaFlutterError(f"Layout fixture not found: {layout_path}")
    from figma_flutter_agent.parser.stack_paint import apply_stack_paint_order_to_clean_tree

    tree = CleanDesignTreeNode.model_validate_json(layout_path.read_text(encoding="utf-8"))
    return apply_stack_paint_order_to_clean_tree(tree)
