"""Per-screen IR cache shadow compatibility report (Program 10 P0-1b)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from figma_flutter_agent.config import Settings
from figma_flutter_agent.debug.ir_cache import (
    IrCacheCompatibilityVerdict,
    cached_ir_metadata,
    compare_ir_cache_compatibility,
    screen_ir_cache_fingerprint,
)
from figma_flutter_agent.debug.paths import screen_root
from figma_flutter_agent.schemas import CleanDesignTreeNode

IR_CACHE_COMPATIBILITY_REPORT_JSON = "ir-cache-compatibility-report.json"


def ir_cache_compatibility_report_path(project_dir: Path, feature_name: str) -> Path:
    return screen_root(project_dir, feature_name) / IR_CACHE_COMPATIBILITY_REPORT_JSON


def build_ir_cache_compatibility_report(
    *,
    dump_path: Path,
    clean_tree: CleanDesignTreeNode,
    settings: Settings,
) -> dict[str, Any]:
    cached = cached_ir_metadata(dump_path)
    current = screen_ir_cache_fingerprint(clean_tree, settings=settings)
    verdict, missing, mismatched = compare_ir_cache_compatibility(cached, current)
    return {
        "schemaVersion": "1",
        "dumpPath": dump_path.name,
        "verdict": verdict,
        "missingIdentityFields": list(missing),
        "mismatchedIdentityFields": list(mismatched),
        "cachedMetadata": {key: cached.get(key) for key in sorted(cached)},
        "currentFingerprint": current,
    }


def write_ir_cache_compatibility_report(
    *,
    project_dir: Path,
    feature_name: str,
    dump_path: Path,
    clean_tree: CleanDesignTreeNode,
    settings: Settings,
) -> tuple[IrCacheCompatibilityVerdict, Path]:
    payload = build_ir_cache_compatibility_report(
        dump_path=dump_path,
        clean_tree=clean_tree,
        settings=settings,
    )
    path = ir_cache_compatibility_report_path(project_dir, feature_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload["verdict"], path  # type: ignore[return-value]
