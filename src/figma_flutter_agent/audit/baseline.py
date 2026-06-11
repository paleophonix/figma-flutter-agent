"""Capture offline audit baseline metadata."""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(slots=True)
class BaselineReport:
    """Recorded signoff baseline for systemic audit."""

    captured_at: str
    git_sha: str
    pytest_exit_code: int | None
    pytest_summary: str
    notes: list[str]


def _git_sha(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def capture_baseline_report(
    *,
    repo_root: Path | None = None,
    run_pytest: bool = False,
    pytest_mark: str = "not live_figma",
) -> BaselineReport:
    """Capture git SHA and optional pytest summary for audit docs."""
    root = repo_root or Path(__file__).resolve().parents[3]
    notes: list[str] = []
    exit_code: int | None = None
    summary = "skipped"
    if run_pytest:
        result = subprocess.run(
            ["poetry", "run", "pytest", "-q", "-m", pytest_mark, "--tb=no"],
            cwd=root,
            capture_output=True,
            text=True,
        )
        exit_code = result.returncode
        summary = (result.stdout or result.stderr or "").strip().splitlines()[-1:] 
        summary = summary[0] if summary else f"exit={exit_code}"
    else:
        notes.append("pytest not run; use --run-pytest to refresh summary")
    return BaselineReport(
        captured_at=datetime.now(UTC).isoformat(),
        git_sha=_git_sha(root),
        pytest_exit_code=exit_code,
        pytest_summary=summary,
        notes=notes,
    )


def write_baseline_markdown(report: BaselineReport, path: Path) -> None:
    """Write baseline report as markdown."""
    lines = [
        "# Audit baseline",
        "",
        f"- Captured: `{report.captured_at}`",
        f"- Git SHA: `{report.git_sha}`",
        f"- Pytest: `{report.pytest_summary}` (exit={report.pytest_exit_code})",
        "",
        "## Commands to refresh",
        "",
        "```bash",
        "poetry run figma-flutter doctor",
        "poetry run figma-flutter demo-signoff --strict --signoff-gates",
        "poetry run figma-flutter fixture-ir-validate",
        "poetry run figma-flutter fixture-geometry-check",
        "poetry run pytest -q -m \"not live_figma\"",
        "```",
        "",
    ]
    if report.notes:
        lines.extend(["## Notes", ""] + [f"- {note}" for note in report.notes])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    path.with_suffix(".json").write_text(
        json.dumps(asdict(report), indent=2),
        encoding="utf-8",
    )
