"""Filesystem paths for the defect corpus."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.config.paths import agent_repo_root


def corpus_root() -> Path:
    """Return the repository-local defect corpus directory."""
    return agent_repo_root() / "corpus"


def families_path() -> Path:
    """Return the canonical families manifest path."""
    return corpus_root() / "families.yaml"


def cases_dir() -> Path:
    """Return the directory containing committed case YAML files."""
    return corpus_root() / "cases"


def index_dir() -> Path:
    """Return the directory containing per-family case index YAML files."""
    return corpus_root() / "index"
