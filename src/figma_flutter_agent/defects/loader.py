"""Load defect corpus YAML from the repository."""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError as PydanticValidationError
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from figma_flutter_agent.defects.models import CaseDocument, FamiliesDocument, LoadedCorpus
from figma_flutter_agent.defects.paths import cases_dir, families_path

_yaml = YAML(typ="safe")


def load_families(path: Path | None = None) -> FamiliesDocument:
    """Load and parse ``families.yaml``.

    Args:
        path: Optional override for tests.

    Returns:
        Parsed families document.

    Raises:
        FileNotFoundError: When the families file is missing.
        PermissionError: When the families file cannot be read.
        ValueError: When YAML or schema validation fails.
    """
    resolved = path or families_path()
    file_path = resolved.as_posix()
    if not resolved.is_file():
        raise FileNotFoundError(f"families file not found: {file_path}")
    try:
        raw = resolved.read_text(encoding="utf-8")
    except OSError as exc:
        raise PermissionError(f"cannot read families file {file_path}: {exc}") from exc
    try:
        payload = _yaml.load(raw)
    except YAMLError as exc:
        raise ValueError(f"YAML parse error in {file_path}: {exc}") from exc
    if payload is None:
        raise ValueError(f"YAML parse error in {file_path}: empty document")
    try:
        return FamiliesDocument.model_validate(payload)
    except PydanticValidationError as exc:
        raise ValueError(
            "; ".join(
                f"{'.'.join(str(part) for part in item.get('loc', ()))}: {item.get('msg', 'validation error')}"
                for item in exc.errors()
            )
            or str(exc),
        ) from exc


def load_case(path: Path) -> CaseDocument:
    """Load one case YAML file.

    Args:
        path: Path to a case document.

    Returns:
        Parsed case document.

    Raises:
        FileNotFoundError: When the case file is missing.
        PermissionError: When the case file cannot be read.
        ValueError: When YAML or schema validation fails.
    """
    file_path = path.as_posix()
    if not path.is_file():
        raise FileNotFoundError(f"case file not found: {file_path}")
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PermissionError(f"cannot read case file {file_path}: {exc}") from exc
    try:
        payload = _yaml.load(raw)
    except YAMLError as exc:
        raise ValueError(f"YAML parse error in {file_path}: {exc}") from exc
    if payload is None:
        raise ValueError(f"YAML parse error in {file_path}: empty document")
    try:
        return CaseDocument.model_validate(payload)
    except PydanticValidationError as exc:
        raise ValueError(
            "; ".join(
                f"{'.'.join(str(part) for part in item.get('loc', ()))}: {item.get('msg', 'validation error')}"
                for item in exc.errors()
            )
            or str(exc),
        ) from exc


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

    Raises:
        FileNotFoundError: When required corpus files are missing.
        PermissionError: When corpus files cannot be read.
        ValueError: When YAML or schema validation fails.
    """
    families = load_families(families_file)
    case_root = cases_directory or cases_dir()
    cases: list[tuple[str, CaseDocument]] = []
    if case_root.is_dir():
        for case_path in sorted(case_root.glob("*.yaml")):
            cases.append((case_path.as_posix(), load_case(case_path)))
    return LoadedCorpus(families=families, cases=cases)
