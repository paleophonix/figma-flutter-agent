"""E2E acceptance: fixture planning plus optional Dart validation."""

import json
import shutil
from pathlib import Path

import pytest

from figma_flutter_agent.config import Settings
from figma_flutter_agent.generator.dart.project_validation import validate_dart_project
from figma_flutter_agent.generator.planner import plan_from_figma_root
from figma_flutter_agent.generator.pubspec import commit_pubspec_batch, update_pubspec
from figma_flutter_agent.generator.writing.core import DartWriter

_FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "flutter_skeleton"


@pytest.mark.skipif(shutil.which("dart") is None, reason="dart SDK not installed")
def test_onboarding_fixture_planned_project_passes_dart_analyze(tmp_path: Path) -> None:
    """Plan deterministic outputs from onboarding fixture and validate with dart/flutter."""
    root = json.loads(Path("tests/fixtures/figma_node_sample.json").read_text(encoding="utf-8"))
    planned = plan_from_figma_root(root, Settings(), node_id=root["id"], package_name="demo_app")

    project_dir = tmp_path / "project"
    shutil.copytree(_FIXTURE_ROOT, project_dir)

    writer = DartWriter(project_dir, enable_backup=False)
    batch = writer.write_files(planned)
    pubspec_batch = update_pubspec(project_dir, ["assets/icons/"], needs_svg=False)
    validate_dart_project(project_dir)
    writer.commit_batch(batch)
    commit_pubspec_batch(pubspec_batch)
