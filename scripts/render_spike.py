#!/usr/bin/env python3
"""One-off rendering calibration harness (FID-40/41/42 spike infrastructure).

Loads synthetic spike fixtures, emits deterministic Dart snippets, and prints
candidate blur/sigma constants from ``render_units`` for manual pixel comparison.

This script does NOT run Flutter or Figma export — it prepares emit output and
conversion tables for offline overlay diffing via ``validation/pixeldiff.py``.

Usage:
    poetry run python scripts/render_spike.py
    poetry run python scripts/render_spike.py --fixture tests/fixtures/spikes/drop_shadow_blur_24.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from figma_flutter_agent.generator.layout_style import box_decoration_expr
from figma_flutter_agent.generator.layout_widget import render_node_body
from figma_flutter_agent.generator.render_units import (
    figma_blur_to_flutter_blur_radius,
    figma_blur_to_image_sigma,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_FIXTURES = _REPO_ROOT / "tests" / "fixtures" / "spikes"


def _load_node(path: Path) -> CleanDesignTreeNode:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return CleanDesignTreeNode.model_validate(payload)


def _shadow_candidates(figma_blur: float) -> list[tuple[str, float]]:
    calibrated = figma_blur_to_flutter_blur_radius(figma_blur)
    return [
        ("figma_raw", figma_blur),
        ("calibrated", calibrated),
        ("css_half", figma_blur / 2.0),
        ("css_inverted_sigma", (figma_blur / 2.0 - 0.5) / 0.57735),
    ]


def _sigma_candidates(figma_blur: float) -> list[tuple[str, float]]:
    return [
        ("figma_raw", figma_blur),
        ("calibrated_half", figma_blur_to_image_sigma(figma_blur)),
        ("css_half", figma_blur / 2.0),
    ]


def _report_fixture(path: Path) -> None:
    node = _load_node(path)
    print(f"\n=== {path.name} ===")
    emit = render_node_body(node)
    if emit:
        print("--- emit snippet (first 800 chars) ---")
        print(emit[:800])
    decoration = box_decoration_expr(node.style, width=node.sizing.width, height=node.sizing.height)
    if decoration:
        print("--- box decoration ---")
        print(decoration)
    blur = node.style.layer_blur or node.style.background_blur
    if blur:
        print(f"--- ImageFilter sigma candidates (figma blur={blur}) ---")
        for label, value in _sigma_candidates(blur):
            print(f"  {label}: {value:.4f}")
    for effect in node.style.effects:
        if effect.blur > 0:
            print(f"--- BoxShadow blurRadius candidates (figma blur={effect.blur}) ---")
            for label, value in _shadow_candidates(effect.blur):
                print(f"  {label}: {value:.4f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Rendering spike calibration reporter")
    parser.add_argument(
        "--fixture",
        type=Path,
        action="append",
        help="Spike fixture JSON (repeatable). Defaults to all in tests/fixtures/spikes/",
    )
    args = parser.parse_args()
    paths = args.fixture or sorted(_DEFAULT_FIXTURES.glob("*.json"))
    if not paths:
        raise SystemExit(f"No spike fixtures under {_DEFAULT_FIXTURES}")
    print("Render spike harness — candidate constants for manual pixel overlay")
    print(f"Fixtures: {len(paths)}")
    for path in paths:
        _report_fixture(path.resolve())


if __name__ == "__main__":
    main()
