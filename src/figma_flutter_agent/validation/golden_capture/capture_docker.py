"""Docker-runtime golden capture execution."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from figma_flutter_agent.config import Settings
from figma_flutter_agent.dev.golden_capture_build import (
    ensure_golden_capture_image,
    golden_docker_auto_build_enabled,
)
from figma_flutter_agent.render_log import record_render_png
from figma_flutter_agent.schemas import CleanDesignTreeNode
from figma_flutter_agent.tools.process_run import (
    DOCKER_COMPOSE_TIMEOUT_SEC,
    run_subprocess,
)
from figma_flutter_agent.validation.golden_capture.capture_host import (
    _read_figma_key_rects,
)
from figma_flutter_agent.validation.golden_capture.logs import (
    _clip_reason,
    _first_process_line,
    _log_process_output,
)
from figma_flutter_agent.validation.golden_capture.paths import (
    golden_png_relative_path,
    golden_test_relative_path,
)
from figma_flutter_agent.validation.golden_capture.project import (
    _copy_skeleton_project,
    _materialize_capture_workspace,
    _prepare_flutter_test_build_dir,
)
from figma_flutter_agent.validation.golden_capture.result import GoldenCaptureResult
from figma_flutter_agent.validation.golden_runtime import golden_compose_file


def capture_planned_flutter_golden_png_docker(
    planned: dict[str, str],
    *,
    feature_name: str,
    project_dir: Path | None = None,
    update_goldens: bool = True,
    layout_tree: CleanDesignTreeNode | None = None,
) -> GoldenCaptureResult:
    """Capture golden PNG inside the ``docker/render-capture`` compose service."""
    compose = golden_compose_file()
    if not compose.is_file():
        return GoldenCaptureResult(reason="docker compose file missing")

    docker = shutil.which("docker")
    if docker is None:
        return GoldenCaptureResult(reason="docker CLI not found")

    golden_test_rel = golden_test_relative_path(feature_name)
    if golden_test_rel not in planned:
        return GoldenCaptureResult(reason=f"no {golden_test_rel} in plan")

    from figma_flutter_agent.validation.golden_capture.project import _FLUTTER_SKELETON

    if not _FLUTTER_SKELETON.is_dir():
        return GoldenCaptureResult(reason="flutter skeleton fixture missing")

    with tempfile.TemporaryDirectory(prefix="figma-flutter-golden-docker-") as tmp:
        capture_dir = Path(tmp) / "project"
        _copy_skeleton_project(capture_dir)
        _materialize_capture_workspace(
            capture_dir,
            planned,
            enable_backup=False,
            layout_tree=layout_tree,
            project_dir=project_dir,
        )
        _prepare_flutter_test_build_dir(capture_dir)
        golden_out = capture_dir / golden_png_relative_path(feature_name)
        env = os.environ.copy()
        env["FEATURE_NAME"] = feature_name
        env["UPDATE_GOLDENS"] = "1" if update_goldens else "0"
        try:
            result = run_subprocess(
                [
                    docker,
                    "compose",
                    "-f",
                    str(compose),
                    "run",
                    "--rm",
                    "-v",
                    f"{capture_dir}:/capture",
                    "golden-capture",
                ],
                cwd=compose.parent,
                label="docker compose golden-capture",
                timeout_sec=DOCKER_COMPOSE_TIMEOUT_SEC,
            )
        except subprocess.TimeoutExpired:
            return GoldenCaptureResult(
                reason=_clip_reason(
                    f"docker golden capture timed out after {DOCKER_COMPOSE_TIMEOUT_SEC:.0f}s"
                ),
            )
        if result.returncode != 0:
            _log_process_output(result, level="warning")
            return GoldenCaptureResult(reason=_first_process_line(result))
        if not golden_out.is_file():
            return GoldenCaptureResult(reason="golden PNG not written")
        png = golden_out.read_bytes()
        figma_key_rects = _read_figma_key_rects(capture_dir, feature_name)
        record_render_png(
            "flutter_render",
            png,
            extra={"featureName": feature_name, "runtime": "docker"},
        )
        return GoldenCaptureResult(png=png, figma_key_rects=figma_key_rects)


def _ensure_docker_golden_image(settings: Settings | None) -> GoldenCaptureResult | None:
    """Build or verify the golden-capture image before ``docker compose run``."""
    if not ensure_golden_capture_image(
        settings,
        build_if_missing=golden_docker_auto_build_enabled(),
        interactive=False,
        print_hint=False,
    ):
        return GoldenCaptureResult(
            reason="golden-capture Docker image missing (auto-build failed or disabled)",
        )
    return None
