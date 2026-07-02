"""Cached screen IR compatibility checks against the current clean tree."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.errors import FlutterProjectError
from figma_flutter_agent.schemas import CleanDesignTreeNode, FlutterGenerationResponse
from figma_flutter_agent.sync.snapshot import hash_clean_tree

CACHED_IR_INCOMPATIBLE_MESSAGE = (
    "Cached screen IR is incompatible with the current processed tree. "
    "Run generate for this screen before launch."
)


def cached_ir_metadata(path: Path) -> dict[str, object]:
    """Return top-level metadata fields stored beside ``screenIr``."""
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
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


def screen_ir_cache_fingerprint(clean_tree: CleanDesignTreeNode) -> dict[str, object]:
    """Build a compatibility fingerprint for the current processed clean tree."""
    width = clean_tree.sizing.width
    height = clean_tree.sizing.height
    return {
        "cleanTreeHash": hash_clean_tree(clean_tree),
        "cleanRootFigmaId": clean_tree.id,
        "cleanRootType": clean_tree.type.value,
        "cleanRootWidth": float(width) if width is not None else None,
        "cleanRootHeight": float(height) if height is not None else None,
    }


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
        raise FlutterProjectError(f"Cached screen IR at {dump_path.name} is missing screenIr.")
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


def ir_cache_metadata_for_write(clean_tree: CleanDesignTreeNode) -> dict[str, object]:
    """Return metadata merged into persisted screen IR snapshots."""
    return screen_ir_cache_fingerprint(clean_tree)
