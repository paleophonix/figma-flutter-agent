"""Write raw and processed screen debug JSON dumps."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger

from figma_flutter_agent.debug.paths import processed_dump_path, raw_dump_path
from figma_flutter_agent.llm.payload_slim import dump_clean_tree_for_llm, dump_tokens_for_llm
from figma_flutter_agent.parser.version import PARSER_VERSION
from figma_flutter_agent.schemas import CleanDesignTreeNode, DesignTokens


def _write_json(path: Path, payload: object, *, project_dir: Path | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_raw_dump(project_dir: Path, feature_name: str, root: dict[str, Any]) -> Path:
    """Persist raw Figma frame JSON under ``.debug/raw/``.

    Args:
        project_dir: Flutter project root.
        feature_name: Resolved screen feature slug.
        root: Raw Figma document node for the target frame.

    Returns:
        Path to the written dump file.
    """
    path = raw_dump_path(project_dir, feature_name)
    _write_json(path, root, project_dir=project_dir)
    logger.info("Saved raw Figma node dump to {}", path.as_posix())
    return path


def write_processed_dump(
    project_dir: Path,
    feature_name: str,
    *,
    clean_tree: CleanDesignTreeNode,
    tokens: DesignTokens,
) -> Path:
    """Persist parsed clean tree JSON under ``.debug/processed/``.

    Args:
        project_dir: Flutter project root.
        feature_name: Resolved screen feature slug.
        clean_tree: Parsed design tree.
        tokens: Extracted design tokens.

    Returns:
        Path to the written dump file.
    """
    path = processed_dump_path(project_dir, feature_name)
    payload = {
        "parserVersion": PARSER_VERSION,
        "cleanTree": dump_clean_tree_for_llm(clean_tree),
        "tokens": dump_tokens_for_llm(tokens),
    }
    _write_json(path, payload, project_dir=project_dir)
    logger.info("Saved processed design tree dump to {}", path.as_posix())
    return path
