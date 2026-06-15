"""Tests for systemic audit tooling."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.audit.baseline import capture_baseline_report
from figma_flutter_agent.audit.corpus import AUDIT_CORPUS
from figma_flutter_agent.audit.diff_triada import run_diff_triada_for_entry
from figma_flutter_agent.audit.docs import write_all_audit_docs
from figma_flutter_agent.audit.fixtures import write_synthetic_layout_fixtures
from figma_flutter_agent.audit.predicate_matrix import (
    PATTERN_FIXTURES,
    build_predicate_matrix,
    render_matrix_markdown,
)


def test_build_predicate_matrix_covers_all_patterns() -> None:
    cells = build_predicate_matrix()
    pattern_ids = {item.pattern_id for item in PATTERN_FIXTURES}
    assert pattern_ids.issubset({cell.pattern_id for cell in cells})
    assert len(cells) == len(PATTERN_FIXTURES) * 10


def test_render_matrix_markdown_lists_patterns() -> None:
    markdown = render_matrix_markdown(build_predicate_matrix())
    assert "consent_checkbox_row" in markdown
    assert "layout_fact_row_tight_overflow_guard_label_row" in markdown


def test_write_synthetic_layout_fixtures(tmp_path: Path) -> None:
    written = write_synthetic_layout_fixtures(tmp_path)
    assert len(written) == 3
    for path in written:
        assert path.is_file()
        assert path.stat().st_size > 50


def test_capture_baseline_report_has_git_sha() -> None:
    report = capture_baseline_report(run_pytest=False)
    assert report.git_sha
    assert report.git_sha != "unknown" or report.captured_at


def test_diff_triada_bounded_order_card() -> None:
    entry = next(item for item in AUDIT_CORPUS if item.pattern_class == "bounded_overflow")
    record = run_diff_triada_for_entry(entry)
    assert record.node_count_pre > 0
    assert "bounded_order_card_layout.dart" in record.layout_dart_path


def test_write_all_audit_docs(tmp_path: Path) -> None:
    paths = write_all_audit_docs(tmp_path)
    assert (tmp_path / "pipeline-contracts.md").is_file()
    assert (tmp_path / "artifacts" / "diff_triada.json").is_file()
    assert len(paths) >= 10
