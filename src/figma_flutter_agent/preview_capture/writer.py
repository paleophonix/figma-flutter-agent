"""Write preview scene workspaces for the static HTML renderer."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from figma_flutter_agent.config import agent_repo_root
from figma_flutter_agent.preview_capture.models import PreviewScene

_RENDERER_ROOT = agent_repo_root() / "tools" / "preview-renderer"
_RENDERER_FILES = ("index.html", "preview.js", "preview.css")
_PREVIEW_SCRIPT_TAG = '    <script src="preview.js"></script>'


def preview_renderer_root() -> Path:
    """Return the committed static preview renderer directory."""
    return _RENDERER_ROOT


def write_preview_workspace(
    scene: PreviewScene,
    workspace: Path,
) -> Path:
    """Materialize renderer assets and scene JSON into ``workspace``.

    Args:
        scene: Scene to serialize.
        workspace: Target directory (created when missing).

    Returns:
        Path to ``index.html`` inside the workspace.
    """
    workspace.mkdir(parents=True, exist_ok=True)
    for name in _RENDERER_FILES:
        shutil.copy2(_RENDERER_ROOT / name, workspace / name)
    scene_payload = scene.model_dump(mode="json")
    scene_path = workspace / "preview_scene.json"
    scene_path.write_text(
        json.dumps(scene_payload, indent=2),
        encoding="utf-8",
    )
    html_template = (_RENDERER_ROOT / "index.html").read_text(encoding="utf-8")
    embedded_scene = (
        '    <script id="figma-preview-scene" type="application/json">\n'
        f"{json.dumps(scene_payload, ensure_ascii=False)}\n"
        "    </script>\n"
    )
    html_path = workspace / "index.html"
    html_path.write_text(
        html_template.replace(_PREVIEW_SCRIPT_TAG, embedded_scene + _PREVIEW_SCRIPT_TAG),
        encoding="utf-8",
    )
    return html_path


def preview_page_url(html_path: Path) -> str:
    """Build a file URL for the preview page loading the default scene file."""
    return html_path.resolve().as_uri() + "?scene=preview_scene.json"
