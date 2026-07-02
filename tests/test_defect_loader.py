"""Tests for defect corpus YAML loader."""

from __future__ import annotations

from figma_flutter_agent.defects import load_corpus, load_families


def test_load_families_has_seed_entries() -> None:
    doc = load_families()
    ids = {family.id for family in doc.families}
    assert "llm_fidelity_authority_bypass" in ids
    assert "ir_override_without_provenance" in ids
    assert len(doc.families) >= 7


def test_load_corpus_reads_cases_directory() -> None:
    corpus = load_corpus()
    assert corpus.families.version == 1
    assert isinstance(corpus.cases, list)
