"""Cache reusable widget candidate LLM responses per screen."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from figma_flutter_agent.config.models import WidgetExtractionConfig
from figma_flutter_agent.debug.paths import screen_root
from figma_flutter_agent.schemas import CleanDesignTreeNode, DesignTokens
from figma_flutter_agent.schemas.reusable_candidates import ReusableWidgetCandidatesResponse

REUSABLE_CANDIDATES_JSON = "reusable_candidates.json"
WIDGET_ENRICH_JSON = "widget_enrich.json"


def reusable_candidates_cache_key(
    clean_tree: CleanDesignTreeNode,
    tokens: DesignTokens,
    config: WidgetExtractionConfig,
) -> str:
    """Build a stable cache key from design hashes and AI reusable settings."""
    from figma_flutter_agent.pipeline.incremental import design_hashes

    hashes = design_hashes(clean_tree, tokens)
    fingerprint = config.ai_reusable.model_dump_json()
    payload = f"{hashes.tree_hash}:{fingerprint}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _artifact_path(project_dir: Path, feature_name: str, filename: str) -> Path:
    return screen_root(project_dir, feature_name) / filename


def load_cached_reusable_candidates(
    project_dir: Path,
    feature_name: str,
    *,
    cache_key: str,
) -> ReusableWidgetCandidatesResponse | None:
    """Load cached reusable candidates when the cache key matches."""
    path = _artifact_path(project_dir, feature_name, REUSABLE_CANDIDATES_JSON)
    if not path.is_file():
        return None
    try:
        payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if payload.get("cacheKey") != cache_key:
        return None
    return ReusableWidgetCandidatesResponse.model_validate(payload.get("response", {}))


def write_cached_reusable_candidates(
    project_dir: Path,
    feature_name: str,
    *,
    cache_key: str,
    response: ReusableWidgetCandidatesResponse,
) -> None:
    """Persist reusable candidates for incremental stability."""
    path = _artifact_path(project_dir, feature_name, REUSABLE_CANDIDATES_JSON)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "cacheKey": cache_key,
                "response": response.model_dump(by_alias=True, mode="json"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def load_cached_widget_enrich(
    project_dir: Path,
    feature_name: str,
    *,
    cache_key: str,
) -> dict[str, Any] | None:
    """Load cached widget enrich payload when the cache key matches."""
    path = _artifact_path(project_dir, feature_name, WIDGET_ENRICH_JSON)
    if not path.is_file():
        return None
    try:
        payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if payload.get("cacheKey") != cache_key:
        return None
    return payload.get("response")
