"""Load defect corpus YAML from the repository."""

from __future__ import annotations

from pathlib import Path

from ruamel.yaml import YAML

from figma_flutter_agent.defects.models import CaseDocument, FamiliesDocument, LoadedCorpus
from figma_flutter_agent.defects.paths import cases_dir, families_path

_yaml = YAML(typ="safe")


def load_families(path: Path | None = None) -> FamiliesDocument:
    """Load and parse ``families.yaml``.

    Args:
        path: Optional override for tests.

    Returns:
        Parsed families document.
    """
    resolved = path or families_path()
    payload = _yaml.load(resolved.read_text(encoding="utf-8"))
    return FamiliesDocument.model_validate(payload)


def load_case(path: Path) -> CaseDocument:
    """Load one case YAML file.

    Args:
        path: Path to a case document.

    Returns:
        Parsed case document.
    """
    payload = _yaml.load(path.read_text(encoding="utf-8"))
    return CaseDocument.model_validate(payload)


def load_corpus(
    *,
    families_file: Path | None = None,
    cases_directory: Path | None = None,
) -> LoadedCorpus:
    """Load families and all ``cases/*.yaml`` documents.

    Args:
        families_file: Optional families path override.
        cases_directory: Optional cases directory override.

    Returns:
        Combined corpus payload.
    """
    families = load_families(families_file)
    case_root = cases_directory or cases_dir()
    cases: list[tuple[str, CaseDocument]] = []
    if case_root.is_dir():
        for case_path in sorted(case_root.glob("*.yaml")):
            cases.append((case_path.as_posix(), load_case(case_path)))
    return LoadedCorpus(families=families, cases=cases)
