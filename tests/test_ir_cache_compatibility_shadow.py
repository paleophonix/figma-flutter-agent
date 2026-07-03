"""Shadow IR cache compatibility tests (Program 10 P0-1b)."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.config import Settings
from figma_flutter_agent.debug.ir_cache import (
    compare_ir_cache_compatibility,
    ir_cache_metadata_for_write,
    screen_ir_cache_fingerprint,
)
from figma_flutter_agent.debug.ir_cache_report import (
    IR_CACHE_COMPATIBILITY_REPORT_JSON,
    write_ir_cache_compatibility_report,
)
from figma_flutter_agent.debug.ir_dumps import write_screen_ir_snapshot
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from tests.synthetic.builders import column_tree


def test_compare_legacy_unknown_when_stamps_missing(tmp_path: Path) -> None:
    tree = column_tree()
    settings = Settings()
    legacy = {"cleanTreeHash": "abc", "cleanRootFigmaId": tree.id}
    current = screen_ir_cache_fingerprint(tree, settings=settings)
    verdict, missing, _ = compare_ir_cache_compatibility(legacy, current)
    assert verdict == "legacy_unknown"
    assert missing


def test_shadow_report_written(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    tree = column_tree()
    screen_ir = default_screen_ir(tree)
    write_screen_ir_snapshot(
        stage="llm_validated",
        feature_name="home",
        screen_ir=screen_ir,
        project_dir=project,
        extra=ir_cache_metadata_for_write(tree, settings=Settings()),
    )
    from figma_flutter_agent.debug.ir_load import resolve_screen_ir_dump_path

    dump_path = resolve_screen_ir_dump_path(project, "home")
    verdict, report_path = write_ir_cache_compatibility_report(
        project_dir=project,
        feature_name="home",
        dump_path=dump_path,
        clean_tree=tree,
        settings=Settings(),
    )
    assert verdict == "compatible"
    assert report_path.name == IR_CACHE_COMPATIBILITY_REPORT_JSON
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["verdict"] == "compatible"
