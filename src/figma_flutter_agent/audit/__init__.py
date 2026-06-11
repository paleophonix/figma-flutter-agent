"""Systemic pipeline audit tooling (diff-triada, predicate matrix, baseline)."""

from figma_flutter_agent.audit.baseline import capture_baseline_report
from figma_flutter_agent.audit.corpus import AUDIT_CORPUS, AuditCorpusEntry
from figma_flutter_agent.audit.diff_triada import run_diff_triada
from figma_flutter_agent.audit.fixtures import write_synthetic_layout_fixtures
from figma_flutter_agent.audit.predicate_matrix import (
    build_predicate_matrix,
    render_matrix_markdown,
)

__all__ = [
    "AUDIT_CORPUS",
    "AuditCorpusEntry",
    "build_predicate_matrix",
    "capture_baseline_report",
    "render_matrix_markdown",
    "run_diff_triada",
    "write_synthetic_layout_fixtures",
]
