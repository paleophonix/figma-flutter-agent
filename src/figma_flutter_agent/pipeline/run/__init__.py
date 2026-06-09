"""End-to-end generation pipeline."""

from .core import run_pipeline
# Re-export names used by patch.object in tests
from .core import (  # noqa: F401
    execute_llm_stage,
    export_figma_assets,
    fetch_figma_frame,
    parse_figma_url,
    run_analyze_repair_loop,
)

__all__ = [
    "run_pipeline",
    "execute_llm_stage",
    "export_figma_assets",
    "fetch_figma_frame",
    "parse_figma_url",
    "run_analyze_repair_loop",
]
