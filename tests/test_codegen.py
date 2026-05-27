from pathlib import Path
from unittest.mock import patch

import pytest

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.codegen import run_build_runner, run_pub_get


def test_run_pub_get_raises_on_failure(tmp_path: Path) -> None:
    with (
        patch(
            "figma_flutter_agent.generator.codegen.shutil.which", return_value="/usr/bin/flutter"
        ),
        patch("figma_flutter_agent.generator.codegen.subprocess.run") as run,
    ):
        run.return_value.returncode = 1
        run.return_value.stderr = "pub get failed"
        run.return_value.stdout = ""
        with pytest.raises(GenerationError, match="pub get failed"):
            run_pub_get(tmp_path)


def test_run_pub_get_requires_sdk_when_flag_set(tmp_path: Path) -> None:
    with (
        patch("figma_flutter_agent.generator.codegen.shutil.which", return_value=None),
        pytest.raises(GenerationError, match="required for pub get"),
    ):
        run_pub_get(tmp_path, require_dart_sdk=True)


def test_run_build_runner_requires_dart_when_flag_set(tmp_path: Path) -> None:
    with (
        patch("figma_flutter_agent.generator.codegen.shutil.which", return_value=None),
        pytest.raises(GenerationError, match="required for build_runner"),
    ):
        run_build_runner(tmp_path, require_dart_sdk=True)


def test_run_build_runner_raises_on_failure(tmp_path: Path) -> None:
    with (
        patch("figma_flutter_agent.generator.codegen.shutil.which", return_value="/usr/bin/dart"),
        patch("figma_flutter_agent.generator.codegen.subprocess.run") as run,
    ):
        run.return_value.returncode = 1
        run.return_value.stderr = "build_runner failed"
        run.return_value.stdout = ""
        with pytest.raises(GenerationError, match="build_runner failed"):
            run_build_runner(tmp_path)
