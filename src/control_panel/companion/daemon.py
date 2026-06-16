"""Local preview companion for figma-flutter:// deep links."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from figma_flutter_agent.dev.flutter_launch import (
    _build_flutter_run_cmd,
    wait_for_tcp_listen,
)
from figma_flutter_agent.dev.flutter_sdk import require_flutter_executable
from figma_flutter_agent.dev.preview_size import CHROME_PREVIEW_WEB_HOST


def hash_token(token: str) -> str:
    """Hash preview token the same way as the control plane."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def load_sidecar(project_dir: Path) -> dict[str, object]:
    """Load preview session sidecar written by the job runner."""
    path = project_dir / ".figma-flutter" / "preview-session.json"
    if not path.is_file():
        msg = f"Preview session file not found: {path}"
        raise FileNotFoundError(msg)
    return json.loads(path.read_text(encoding="utf-8"))


def validate_session(
    *,
    project_dir: Path,
    token: str,
    mode: str,
) -> tuple[int, str]:
    """Validate token and return port + preview kind."""
    payload = load_sidecar(project_dir)
    expected_hash = str(payload.get("tokenHash") or "")
    if hash_token(token) != expected_hash:
        msg = "Invalid preview token"
        raise PermissionError(msg)
    if mode == "fixed":
        return int(payload.get("staticPort") or 17357), "static"
    return int(payload.get("adaptivePort") or 17358), "responsive"


def launch_preview(
    *,
    project_dir: Path,
    mode: str,
    token: str,
) -> int:
    """Launch Flutter web-server preview for one session."""
    port, preview_kind = validate_session(project_dir=project_dir, token=token, mode=mode)
    flutter = require_flutter_executable(sdk_root=None)
    run_cmd = _build_flutter_run_cmd(
        flutter,
        device_id="web-server",
        preview_size=(390, 844),
        preview_kind=preview_kind,  # type: ignore[arg-type]
        responsive=None,
        web_port=port,
    )
    proc = subprocess.Popen(
        run_cmd,
        cwd=project_dir,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    if wait_for_tcp_listen(CHROME_PREVIEW_WEB_HOST, port, proc=proc):
        print(f"Preview ready at http://{CHROME_PREVIEW_WEB_HOST}:{port}/")
        return 0
    return 1


def parse_companion_url(url: str) -> tuple[str, str, str]:
    """Parse ``figma-flutter://preview/{job_id}?mode=&token=``."""
    parsed = urlparse(url)
    if parsed.scheme != "figma-flutter":
        msg = f"Unsupported scheme: {parsed.scheme}"
        raise ValueError(msg)
    job_id = parsed.path.strip("/").split("/", 1)[-1]
    query = parse_qs(parsed.query)
    mode = (query.get("mode") or ["fixed"])[0]
    token = (query.get("token") or [""])[0]
    if not token:
        raise ValueError("Missing preview token")
    return job_id, mode, token


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for manual preview launches."""
    parser = argparse.ArgumentParser(description="figma-flutter preview companion")
    parser.add_argument("--url", help="figma-flutter:// preview URL")
    parser.add_argument("--project-dir", type=Path, help="Flutter project root")
    parser.add_argument("--mode", choices=["fixed", "adaptive"], default="fixed")
    parser.add_argument("--token", default="")
    args = parser.parse_args(argv)

    project_dir = args.project_dir
    mode = args.mode
    token = args.token
    if args.url:
        _job_id, mode, token = parse_companion_url(args.url)
    if project_dir is None:
        parser.error("--project-dir is required when --url is not used with sidecar")
    return launch_preview(project_dir=project_dir.expanduser().resolve(), mode=mode, token=token)


if __name__ == "__main__":
    sys.exit(main())
