"""Settings purity lint gate tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINT = ROOT / "scripts" / "lint_settings_purity.py"
BASELINE = ROOT / "tests" / "fixtures" / "lint" / "settings_purity_baseline.txt"


def test_settings_purity_baseline_exists() -> None:
    assert BASELINE.is_file()


def test_settings_purity_gate_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(LINT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_settings_purity_collects_five_debt_sites() -> None:
    from scripts.lint_settings_purity import collect_violations

    violations = collect_violations()
    assert len(violations) == 5
    paths = {item.path for item in violations}
    assert "src/figma_flutter_agent/generator/ir/materialize.py" in paths
    assert "src/figma_flutter_agent/generator/ir/expression.py" in paths
