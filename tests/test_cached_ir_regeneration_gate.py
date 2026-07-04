"""Enforce-mode stale IR regeneration gate (Program 10 P0-1c)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from figma_flutter_agent.compiler.ir_cache_policy import IrCachePolicy, IrCachePolicyMode
from figma_flutter_agent.config import Settings
from figma_flutter_agent.debug.ir_cache import ir_cache_metadata_for_write
from figma_flutter_agent.debug.ir_dumps import write_screen_ir_snapshot
from figma_flutter_agent.errors import FlutterProjectError
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.pipeline.llm import load_cached_ir_llm_outcome
from tests.synthetic.builders import column_tree


def test_enforce_stale_ir_without_llm_key_raises_actionable_error(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    tree = column_tree()
    screen_ir = default_screen_ir(tree)
    stale_meta = ir_cache_metadata_for_write(tree, settings=Settings())
    stale_meta["generationConfigHash"] = "stale-config-hash"
    write_screen_ir_snapshot(
        stage="llm_validated",
        feature_name="home",
        screen_ir=screen_ir,
        project_dir=project,
        extra=stale_meta,
    )
    settings = Settings()
    log = MagicMock()
    policy = IrCachePolicy(mode=IrCachePolicyMode.ENFORCE)

    with pytest.raises(FlutterProjectError, match="LLM regeneration is unavailable"):
        load_cached_ir_llm_outcome(
            log,
            settings=settings,
            project_dir=project,
            resolved_feature="home",
            clean_tree=tree,
            tokens=MagicMock(),
            ir_cache_policy=policy,
            allow_regenerate=True,
        )

    from figma_flutter_agent.debug.ir_cache_report import ir_cache_compatibility_report_path

    report_path = ir_cache_compatibility_report_path(project, "home")
    assert report_path.is_file()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["verdict"] in {"legacy_unknown", "incompatible"}
