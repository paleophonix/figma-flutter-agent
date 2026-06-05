#!/usr/bin/env python3
"""One-off rendering calibration harness (FID-40/41/42 spike infrastructure).

Loads synthetic spike fixtures, emits deterministic Dart snippets, and prints
candidate blur/sigma constants from ``render_units`` for manual pixel comparison.

This script does NOT run Flutter or Figma export — it prepares emit output and
conversion tables for offline overlay diffing via ``validation/pixeldiff.py``.

Usage:
    poetry run python scripts/render_spike.py
    poetry run python scripts/render_spike.py --fixture tests/fixtures/spikes/drop_shadow_blur_24.json
    poetry run python scripts/render_spike.py --json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from figma_flutter_agent.generator.layout_style import box_decoration_expr
from figma_flutter_agent.generator.layout_widget import render_node_body
from figma_flutter_agent.generator.render_units import (
    figma_blur_to_flutter_blur_radius,
    figma_blur_to_image_sigma,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_FIXTURES = _REPO_ROOT / "tests" / "fixtures" / "spikes"
_FIXTURES_ROOT = _REPO_ROOT / "tests" / "fixtures"


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


def _fixture_report(path: Path) -> dict[str, Any]:
    """Build a JSON-serializable calibration report for one spike fixture."""
    node = _load_node(path)
    emit = render_node_body(node, uses_svg=False) or ""
    decoration = box_decoration_expr(
        node.style,
        width=node.sizing.width,
        height=node.sizing.height,
    )
    report: dict[str, Any] = {
        "fixture": path.name,
        "emit_snippet": emit[:800],
        "box_decoration": decoration,
        "sigma_candidates": {},
        "shadow_candidates": {},
    }
    blur = node.style.layer_blur or node.style.background_blur
    if blur:
        report["sigma_candidates"] = {
            label: round(value, 4) for label, value in _sigma_candidates(blur)
        }
    for effect in node.style.effects:
        if effect.blur > 0:
            report["shadow_candidates"][str(effect.blur)] = {
                label: round(value, 4) for label, value in _shadow_candidates(effect.blur)
            }
    return report


def _report_fixture(path: Path) -> None:
    report = _fixture_report(path)
    print(f"\n=== {report['fixture']} ===")
    if report["emit_snippet"]:
        print("--- emit snippet (first 800 chars) ---")
        print(report["emit_snippet"])
    if report["box_decoration"]:
        print("--- box decoration ---")
        print(report["box_decoration"])
    if report["sigma_candidates"]:
        blur = next(iter(report["sigma_candidates"].values()), None)
        print("--- ImageFilter sigma candidates ---")
        for label, value in report["sigma_candidates"].items():
            print(f"  {label}: {value:.4f}")
    for blur_key, candidates in report["shadow_candidates"].items():
        print(f"--- BoxShadow blurRadius candidates (figma blur={blur_key}) ---")
        for label, value in candidates.items():
            print(f"  {label}: {value:.4f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Rendering spike calibration reporter")
    parser.add_argument(
        "--fixture",
        type=Path,
        action="append",
        help="Spike fixture JSON (repeatable). Defaults to all in tests/fixtures/spikes/",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit candidate calibration table as JSON (for locking constants in render_units)",
    )
    args = parser.parse_args()
    paths = args.fixture or sorted(_DEFAULT_FIXTURES.glob("*.json"))
    if not paths:
        raise SystemExit(f"No spike fixtures under {_DEFAULT_FIXTURES}")

    resolved = [path.resolve() for path in paths]
    if args.json:
        gradient_hits: list[dict[str, object]] = []

        def _scan_gradients(payload: object) -> None:
            if isinstance(payload, dict):
                fills = payload.get("fills")
                if isinstance(fills, list):
                    for fill in fills:
                        if isinstance(fill, dict) and fill.get("type", "").startswith("GRADIENT"):
                            cs = fill.get("gradientColorSpace") or fill.get("colorSpace")
                            if cs or fill.get("gradientHandlePositions"):
                                gradient_hits.append({"colorSpace": cs, "id": payload.get("id")})
                for value in payload.values():
                    _scan_gradients(value)
            elif isinstance(payload, list):
                for item in payload:
                    _scan_gradients(item)

        for path in _FIXTURES_ROOT.rglob("*.json"):
            _scan_gradients(json.loads(path.read_text(encoding="utf-8")))

        payload = {
            "calibration_model": "css_stddev_half",
            "locked_constants": {
                "drop_shadow_blur_radius": "figma_blur_to_flutter_blur_radius(B) = (B/2 - 0.5) / 0.57735",
                "image_filter_sigma": "figma_blur_to_image_sigma(B) = B/2",
            },
            "fid44_gradient_audit": {
                "p3_or_handle_position_hits": gradient_hits,
                "resample_required": len(gradient_hits) > 0,
            },
            "fid46_svg_note": (
                "SVG vs PNG IoU spike deferred; classifier uses svg_path_element_count "
                f"threshold={120} when path count is available on node."
            ),
            "fixtures": [_fixture_report(path) for path in resolved],
        }
        print(json.dumps(payload, indent=2))
        return

    print("Render spike harness — candidate constants for manual pixel overlay")
    print(f"Fixtures: {len(resolved)}")
    for path in resolved:
        _report_fixture(path)


if __name__ == "__main__":
    main()
