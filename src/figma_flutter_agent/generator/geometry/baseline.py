"""Flutter baseline oracle for typography metrics (WP-2)."""

from __future__ import annotations

import statistics
from pathlib import Path

from loguru import logger

from figma_flutter_agent.schemas import CleanDesignTreeNode

_DEFAULT_BASELINE_RATIO = 0.72
_MIN_LEARNED_RATIO = 0.35
_MAX_LEARNED_RATIO = 0.95
_FONT_BASELINE_RATIOS: dict[str, float] = {
    "roboto": 0.72,
    "inter": 0.73,
    "sf pro": 0.71,
}
_learned_ratios: dict[str, float] = {}


def normalize_font_family_key(font_family: str) -> str:
    """Normalize a Figma ``fontFamily`` string to an oracle lookup key."""
    return font_family.strip().lower()


def clear_baseline_oracle_cache() -> None:
    """Reset learned ratios (for tests and isolated pipeline runs)."""
    _learned_ratios.clear()


def _collect_font_families(node: CleanDesignTreeNode, families: set[str]) -> None:
    if node.style.font_family:
        families.add(normalize_font_family_key(node.style.font_family))
    for child in node.children:
        _collect_font_families(child, families)


def learn_baseline_ratios_from_tree(tree: CleanDesignTreeNode) -> dict[str, float]:
    """Derive median ``glyphTopOffset / fontSize`` per family from Figma text nodes."""
    samples: dict[str, list[float]] = {}

    def visit(node: CleanDesignTreeNode) -> None:
        style = node.style
        if (
            style.font_family
            and style.font_size is not None
            and style.font_size > 0
            and style.glyph_top_offset is not None
            and style.glyph_top_offset >= 0
        ):
            ratio = style.glyph_top_offset / style.font_size
            if _MIN_LEARNED_RATIO <= ratio <= _MAX_LEARNED_RATIO:
                key = normalize_font_family_key(style.font_family)
                samples.setdefault(key, []).append(ratio)
        for child in node.children:
            visit(child)

    visit(tree)
    learned: dict[str, float] = {}
    for key, values in samples.items():
        if values:
            learned[key] = statistics.median(values)
    return learned


def seed_baseline_oracle(
    tree: CleanDesignTreeNode,
    *,
    project_dir: Path | None = None,
) -> None:
    """Prime baseline ratios from the current tree and optional bundled fonts."""
    clear_baseline_oracle_cache()
    families: set[str] = set()
    _collect_font_families(tree, families)
    _learned_ratios.update(learn_baseline_ratios_from_tree(tree))

    if project_dir is None:
        return

    from figma_flutter_agent.fonts.metrics import baseline_ratio_from_project_fonts

    for family in sorted(families):
        key = normalize_font_family_key(family)
        if key in _learned_ratios:
            continue
        ratio = baseline_ratio_from_project_fonts(project_dir, family)
        if ratio is not None:
            clamped = max(_MIN_LEARNED_RATIO, min(_MAX_LEARNED_RATIO, ratio))
            _learned_ratios[key] = clamped
            logger.debug(
                "Baseline oracle loaded {} from bundled font ({:.3f})",
                family,
                clamped,
            )


def resolve_baseline_ratio(font_family: str | None) -> float:
    """Return the baseline ratio for a font family key."""
    if not font_family:
        return _DEFAULT_BASELINE_RATIO
    key = normalize_font_family_key(font_family)
    if key in _learned_ratios:
        return _learned_ratios[key]
    if key in _FONT_BASELINE_RATIOS:
        return _FONT_BASELINE_RATIOS[key]
    logger.debug(
        "Baseline oracle using {:.2f} default for {}",
        _DEFAULT_BASELINE_RATIO,
        font_family,
    )
    return _DEFAULT_BASELINE_RATIO


def flutter_baseline_offset(
    font_size: float,
    *,
    font_family: str | None = None,
) -> float:
    """Predict baseline offset from font size using learned or bundled oracle data."""
    if font_size <= 0:
        return 0.0
    return font_size * resolve_baseline_ratio(font_family)
