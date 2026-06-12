"""Corpus oracle gate orchestration (EPIC 6 W0)."""

from figma_flutter_agent.validation.oracle.models import CorpusGateReport, ScreenOracleResult
from figma_flutter_agent.validation.oracle.profile_compare import (
    ProfileComparisonReport,
    compare_profile_soft_invariants,
)
from figma_flutter_agent.validation.oracle.reports import write_all_oracle_reports
from figma_flutter_agent.validation.oracle.runner import run_corpus_oracle

__all__ = [
    "CorpusGateReport",
    "ProfileComparisonReport",
    "ScreenOracleResult",
    "compare_profile_soft_invariants",
    "run_corpus_oracle",
    "write_all_oracle_reports",
]
