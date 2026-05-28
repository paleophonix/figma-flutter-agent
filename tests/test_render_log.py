"""Combat render artifact logging under logs/renders/."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from figma_flutter_agent.render_log import (
    RENDER_LOG_DIR,
    bind_render_log_session,
    clear_render_log_session,
    record_render_png,
    render_artifacts_dir,
)


def _tiny_png() -> bytes:
    from io import BytesIO

    buffer = BytesIO()
    Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_record_render_png_writes_under_session_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    clear_render_log_session()
    bind_render_log_session(run_id="abc123", feature_name="sign_in", project_dir="../demo_app")
    out = record_render_png("figma_reference", _tiny_png())
    assert out is not None
    assert out.is_file()
    session_dir = render_artifacts_dir()
    assert session_dir is not None
    assert session_dir == RENDER_LOG_DIR / session_dir.name
    manifest = session_dir / "manifest.jsonl"
    assert manifest.is_file()
    assert "figma_reference" in manifest.read_text(encoding="utf-8")
    clear_render_log_session()


def test_record_render_png_without_session_is_noop(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    clear_render_log_session()
    assert record_render_png("orphan", _tiny_png()) is None
