"""Dry-run output formatting."""

from __future__ import annotations

import json

from figma_flutter_agent.pipeline.result import PipelineResult


def format_dry_run_output(result: PipelineResult, *, include_design: bool = False) -> str:
    """Format dry-run output for CLI display."""
    payload: dict[str, object] = {
        "warnings": result.warnings,
        "plannedFiles": result.planned_files,
        "summary": {
            "runId": result.run_id,
            "plannedFileCount": len(result.planned_files),
            "cleanTreeHash": result.clean_tree_hash,
            "colorsHash": result.colors_hash,
            "typographyHash": result.typography_hash,
            "spacingHash": result.spacing_hash,
            "tokenCounts": {
                "colors": len(result.tokens.colors),
                "typography": len(result.tokens.typography),
                "spacing": len(result.tokens.spacing),
                "radii": len(result.tokens.radii),
                "elevations": len(result.tokens.elevations),
            },
        },
    }
    if include_design:
        from figma_flutter_agent.llm.payload_slim import (
            dump_clean_tree_for_llm,
            dump_tokens_for_llm,
        )

        payload["cleanTree"] = dump_clean_tree_for_llm(result.clean_tree)
        payload["tokens"] = dump_tokens_for_llm(result.tokens)
    return json.dumps(payload, indent=2, ensure_ascii=False)
