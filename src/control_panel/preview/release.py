"""Release web preview builds served as static files."""

from __future__ import annotations

import mimetypes
from pathlib import Path

from loguru import logger

from control_panel.config.models import PreviewConfig
from control_panel.preview.serve import ensure_flutter_web_support
from figma_flutter_agent.dev.flutter_sdk import require_flutter_executable
from figma_flutter_agent.dev.preview_size import chrome_preview_dart_defines, chrome_web_build_flags
from figma_flutter_agent.errors import FigmaFlutterError
from figma_flutter_agent.tools.process_run import run_subprocess

FLUTTER_WEB_BUILD_TIMEOUT_SEC = 900.0
_PREVIEW_RELEASE_DIRNAME = "preview-release"
_DEFAULT_ARTBOARD = (390, 844)


def release_preview_enabled(config: PreviewConfig) -> bool:
    """Return whether HTTP preview should use prebuilt release web assets."""
    return config.release_build


def release_output_root(project_dir: Path, mode: str) -> Path:
    """Return the on-disk root for one preview mode's release build."""
    return project_dir / ".figma-flutter" / _PREVIEW_RELEASE_DIRNAME / mode


def release_build_ready(project_dir: Path, mode: str) -> bool:
    """Return True when a release preview build exists for one mode."""
    return (release_output_root(project_dir, mode) / "index.html").is_file()


def _release_build_argv(
    flutter: str,
    *,
    job_id: str,
    mode: str,
    output_dir: Path,
) -> list[str]:
    width, height = _DEFAULT_ARTBOARD
    cmd = [
        flutter,
        "build",
        "web",
        "--release",
        "--no-pub",
        "--base-href",
        f"/preview/{job_id}/",
        "--output",
        output_dir.as_posix(),
        *chrome_web_build_flags(),
    ]
    if mode == "fixed":
        cmd.extend(chrome_preview_dart_defines(width, height))
    return cmd


def build_release_web_preview(
    *,
    project_dir: Path,
    job_id: str,
    mode: str,
) -> Path:
    """Build one release web preview bundle for fixed or adaptive mode.

    Args:
        project_dir: Flutter sandbox root.
        job_id: Preview job id embedded in ``--base-href``.
        mode: ``fixed`` or ``adaptive``.

    Returns:
        Output directory containing ``index.html``.

    Raises:
        FigmaFlutterError: When the Flutter build fails.
    """
    if mode not in {"fixed", "adaptive"}:
        msg = f"Unsupported preview mode {mode!r}; expected fixed or adaptive."
        raise FigmaFlutterError(msg)

    ensure_flutter_web_support(project_dir)
    output_dir = release_output_root(project_dir, mode)
    output_dir.parent.mkdir(parents=True, exist_ok=True)

    flutter = require_flutter_executable(sdk_root=None)
    argv = _release_build_argv(flutter, job_id=job_id, mode=mode, output_dir=output_dir)
    logger.info(
        "Building release web preview mode={} project={} output={}",
        mode,
        project_dir.as_posix(),
        output_dir.as_posix(),
    )
    result = run_subprocess(
        argv,
        cwd=project_dir,
        label=f"flutter build web ({mode})",
        timeout_sec=FLUTTER_WEB_BUILD_TIMEOUT_SEC,
        project_dir=project_dir,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        msg = f"flutter build web --release failed for mode={mode} (exit {result.returncode})" + (
            f": {detail[:500]}" if detail else ""
        )
        raise FigmaFlutterError(msg)
    if not release_build_ready(project_dir, mode):
        raise FigmaFlutterError(f"Release preview build missing index.html for mode={mode}")
    return output_dir


def build_release_previews(*, project_dir: Path, job_id: str) -> None:
    """Build fixed and adaptive release preview bundles when the flag is enabled."""
    for mode in ("fixed", "adaptive"):
        build_release_web_preview(project_dir=project_dir, job_id=job_id, mode=mode)


def resolve_release_asset_path(project_dir: Path, mode: str, path: str) -> Path | None:
    """Resolve a preview-relative URL path to an on-disk release asset."""
    root = release_output_root(project_dir, mode).resolve()
    if not root.is_dir():
        return None
    relative = path.lstrip("/") or "index.html"
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    if candidate.is_file():
        return candidate
    return None


def read_release_preview_file(
    project_dir: Path,
    mode: str,
    path: str,
) -> tuple[int, dict[str, str], bytes] | None:
    """Read one release preview asset when the build exists.

    Returns:
        ``(status, headers, body)`` or ``None`` when no release build is present.
    """
    asset = resolve_release_asset_path(project_dir, mode, path)
    if asset is None:
        if not release_build_ready(project_dir, mode):
            return None
        return 404, {"content-type": "text/plain"}, b"not_found"

    content = asset.read_bytes()
    content_type, _ = mimetypes.guess_type(asset.name)
    headers = {"content-type": content_type or "application/octet-stream"}
    return 200, headers, content
