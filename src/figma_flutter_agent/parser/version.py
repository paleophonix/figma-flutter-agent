"""Parser semver stamped into processed debug dumps (CORE-21)."""

from __future__ import annotations

import json
from pathlib import Path

from loguru import logger

PARSER_VERSION = "2026.06.1"


def check_stale_processed_dump(
    project_dir: Path,
    feature_name: str,
    *,
    strict: bool = False,
) -> None:
    """Warn or fail when an on-disk processed dump predates the current parser.

    Args:
        project_dir: Flutter project root containing ``.figma_debug/processed/``.
        feature_name: Resolved screen slug.
        strict: When true, raise ``GenerationError`` instead of logging a warning.

    Raises:
        GenerationError: When ``strict`` is true and the stored parser version differs.
    """
    from figma_flutter_agent.debug.paths import processed_dump_path
    from figma_flutter_agent.errors import GenerationError

    path = processed_dump_path(project_dir, feature_name)
    if not path.is_file():
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return
    stored = payload.get("parserVersion")
    if stored is None:
        logger.warning(
            "Processed dump {} has no parserVersion; re-parse from raw before trusting NodeType",
            path.as_posix(),
        )
        return
    if stored == PARSER_VERSION:
        return
    message = (
        f"Stale processed dump {path.name} (parserVersion={stored!r}, "
        f"current={PARSER_VERSION!r}). Re-run generate from "
        f".figma_debug/raw/{feature_name}_layout.json or delete processed/."
    )
    if strict:
        raise GenerationError(message)
    logger.warning(message)
