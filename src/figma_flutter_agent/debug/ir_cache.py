"""Cached screen IR compatibility checks against the current clean tree."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from figma_flutter_agent.compiler.generation_config_fingerprint import (
    generation_config_fingerprint,
)
from figma_flutter_agent.config import Settings
from figma_flutter_agent.errors import FlutterProjectError
from figma_flutter_agent.generator.ir.version import IR_SCHEMA_VERSION
from figma_flutter_agent.parser.version import PARSER_VERSION
from figma_flutter_agent.schemas import CleanDesignTreeNode, FlutterGenerationResponse
from figma_flutter_agent.sync.snapshot import hash_clean_tree

IR_CACHE_FINGERPRINT_VERSION = "1"

IrCacheCompatibilityVerdict = Literal["compatible", "incompatible", "legacy_unknown"]

CACHED_IR_INCOMPATIBLE_MESSAGE = (
    "Cached screen IR is incompatible with the current processed tree. "
    "Run generate for this screen before launch."
)

_REQUIRED_IDENTITY_FIELDS = (
    "parserVersion",
    "irSchemaVersion",
    "generationConfigFingerprintVersion",
    "generationConfigHash",
)


def cached_ir_metadata(path: Path) -> dict[str, object]:
    """Return top-level metadata fields stored beside ``screenIr``."""
    resolved = path.expanduser().resolve()
    if not path.is_file():
        return {}
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def cached_ir_clean_tree_hash(path: Path) -> str | None:
    """Return the clean-tree hash stamped on a cached IR dump, if present."""
    value = cached_ir_metadata(path).get("cleanTreeHash")
    return str(value) if value else None


def screen_ir_cache_fingerprint(
    clean_tree: CleanDesignTreeNode,
    *,
    settings: Settings | None = None,
) -> dict[str, object]:
    """Build a compatibility fingerprint for the current processed clean tree."""
    width = clean_tree.sizing.width
    height = clean_tree.sizing.height
    fingerprint: dict[str, object] = {
        "irCacheFingerprintVersion": IR_CACHE_FINGERPRINT_VERSION,
        "cleanTreeHash": hash_clean_tree(clean_tree),
        "cleanRootFigmaId": clean_tree.id,
        "cleanRootType": clean_tree.type.value,
        "cleanRootWidth": float(width) if width is not None else None,
        "cleanRootHeight": float(height) if height is not None else None,
        "parserVersion": PARSER_VERSION,
        "irSchemaVersion": IR_SCHEMA_VERSION,
    }
    if settings is not None:
        cfg_version, cfg_hash = generation_config_fingerprint(settings)
        fingerprint["generationConfigFingerprintVersion"] = cfg_version
        fingerprint["generationConfigHash"] = cfg_hash
    return fingerprint


def ir_cache_metadata_for_write(
    clean_tree: CleanDesignTreeNode,
    *,
    settings: Settings | None = None,
) -> dict[str, object]:
    """Return metadata merged into persisted screen IR snapshots."""
    resolved = settings if settings is not None else Settings()
    return screen_ir_cache_fingerprint(clean_tree, settings=resolved)


def compare_ir_cache_compatibility(
    cached_metadata: dict[str, object],
    current_fingerprint: dict[str, object],
) -> tuple[IrCacheCompatibilityVerdict, tuple[str, ...], tuple[str, ...]]:
    """Compare cached dump identity to current fingerprint (shadow helper)."""
    missing = tuple(
        field for field in _REQUIRED_IDENTITY_FIELDS if field not in cached_metadata
    )
    if missing:
        return "legacy_unknown", missing, ()
    mismatched: list[str] = []
    for field in _REQUIRED_IDENTITY_FIELDS:
        if str(cached_metadata.get(field)) != str(current_fingerprint.get(field)):
            mismatched.append(field)
    for field in ("cleanTreeHash", "cleanRootFigmaId"):
        if str(cached_metadata.get(field)) != str(current_fingerprint.get(field)):
            if field not in mismatched:
                mismatched.append(field)
    if mismatched:
        return "incompatible", (), tuple(mismatched)
    return "compatible", (), ()


def assert_cached_screen_ir_compatible(
    generation: FlutterGenerationResponse,
    clean_tree: CleanDesignTreeNode,
    *,
    dump_path: Path,
) -> None:
    """Raise when a cached IR dump cannot be replayed against ``clean_tree``.

    Args:
        generation: Cached generation payload.
        clean_tree: Current parsed clean tree.
        dump_path: Cached IR JSON path (for error messages).

    Raises:
        FlutterProjectError: When root identity or stamped tree hash disagrees.
    """
    screen_ir = generation.screen_ir
    if screen_ir is None:
        raise FlutterProjectError(
            f"Cached screen IR at {dump_path.name} is missing screenIr."
        )
    metadata = cached_ir_metadata(dump_path)
    current_hash = hash_clean_tree(clean_tree)
    cached_hash = metadata.get("cleanTreeHash")
    if cached_hash and str(cached_hash) != current_hash:
        raise FlutterProjectError(
            f"{CACHED_IR_INCOMPATIBLE_MESSAGE} ({dump_path.name}: cleanTreeHash mismatch)."
        )
    if screen_ir.root.figma_id != clean_tree.id:
        raise FlutterProjectError(
            f"{CACHED_IR_INCOMPATIBLE_MESSAGE} ({dump_path.name}: root figmaId mismatch)."
        )
    cached_root_id = metadata.get("cleanRootFigmaId")
    if cached_root_id and str(cached_root_id) != clean_tree.id:
        raise FlutterProjectError(
            f"{CACHED_IR_INCOMPATIBLE_MESSAGE} ({dump_path.name}: clean root id mismatch)."
        )
