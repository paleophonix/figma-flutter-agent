"""Deterministic SCREEN vision bundle for recognise step."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

_VISION_ASSETS = (
    "figma.png",
    "flutter_render.png",
    "diff.png",
    "diff_heatmap.png",
)


def build_vision_bundle(
    *,
    debug_mirror: Path,
    repair_root: Path,
    case_mode: str,
    require_flutter_render: bool = False,
) -> dict[str, Any]:
    """Materialize vision assets under ``.repair/vision/`` and return bundle metadata.

    Args:
        debug_mirror: Screen debug mirror copied into the worktree.
        repair_root: ``.repair`` root in the worktree.
        case_mode: Run Gate case mode (``SCREEN`` or ``FORENSIC``).
        require_flutter_render: When true, SCREEN bundles need flutter/capture PNG.

    Returns:
        Bundle metadata including completeness flags for recognise gating.
    """
    vision_dir = repair_root / "vision"
    vision_dir.mkdir(parents=True, exist_ok=True)
    assets: dict[str, str] = {}
    for name in _VISION_ASSETS:
        source = debug_mirror / name
        if source.is_file():
            dest = vision_dir / name
            shutil.copy2(source, dest)
            assets[name] = dest.relative_to(repair_root.parent).as_posix()

    diff_stats: dict[str, Any] = {}
    capture_path = debug_mirror / "capture.json"
    if capture_path.is_file():
        loaded = json.loads(capture_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            diff_stats = {
                "changedRatio": loaded.get("changedRatio"),
                "score": loaded.get("score") or loaded.get("diff", {}).get("score"),
                "flutterCaptureOk": loaded.get("flutterCaptureOk"),
            }

    semantic_hints: dict[str, Any] = {}
    semantics_path = debug_mirror / "semantics.json"
    if semantics_path.is_file():
        loaded = json.loads(semantics_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            semantic_hints = {
                "nodeCount": len(loaded.get("nodes") or loaded.get("entries") or []),
                "kinds": sorted(
                    {
                        str(item.get("kind") or item.get("classification"))
                        for item in (loaded.get("nodes") or loaded.get("entries") or [])
                        if isinstance(item, dict) and (item.get("kind") or item.get("classification"))
                    }
                )[:20],
            }

    has_flutter_render = "flutter_render.png" in assets or "capture.png" in assets
    required = ("figma.png",) if case_mode == "SCREEN" else ()
    complete = all(name in assets for name in required)
    blocked_reason: str | None = None
    if case_mode == "SCREEN" and not complete:
        blocked_reason = "VISION_BUNDLE_INCOMPLETE"
    elif case_mode == "SCREEN" and require_flutter_render and not has_flutter_render:
        complete = False
        blocked_reason = "VISION_FLUTTER_RENDER_MISSING"
    return {
        "visionDir": vision_dir.relative_to(repair_root.parent).as_posix(),
        "assets": assets,
        "diffStats": diff_stats,
        "semanticHints": semantic_hints,
        "complete": complete,
        "hasFlutterRender": has_flutter_render,
        "blockedReason": blocked_reason,
    }
