"""Preview token and companion URL helpers."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

from control_panel.config.models import PreviewConfig


@dataclass(frozen=True)
class PreviewSession:
    """Issued preview credentials for one job."""

    token: str
    token_hash: str
    fixed_url: str
    adaptive_url: str
    expires_at: datetime
    static_port: int
    adaptive_port: int


def hash_preview_token(token: str) -> str:
    """Return a stable hash for storing preview tokens."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def allocate_preview_ports(*, job_id: str, config: PreviewConfig) -> tuple[int, int]:
    """Derive stable per-job TCP ports from configured bases.

    Args:
        job_id: Generation job identifier.
        config: Preview port bases from control panel YAML.

    Returns:
        ``(static_port, adaptive_port)`` within the ephemeral port range.
    """
    bucket = int(hashlib.sha256(job_id.encode("utf-8")).hexdigest()[:8], 16) % 2500
    static_port = min(config.static_port_base + bucket * 2, 65000)
    adaptive_port = min(config.adaptive_port_base + bucket * 2, 65001)
    if static_port == adaptive_port:
        adaptive_port = min(adaptive_port + 1, 65535)
    return static_port, adaptive_port


def build_preview_session(
    *,
    job_id: str,
    config: PreviewConfig,
) -> PreviewSession:
    """Create preview token and companion deep links."""
    token = secrets.token_urlsafe(24)
    token_hash = hash_preview_token(token)
    scheme = config.companion_scheme
    static_port, adaptive_port = allocate_preview_ports(job_id=job_id, config=config)
    fixed_url = (
        f"{scheme}://preview/{quote(job_id, safe='')}"
        f"?mode=fixed&token={quote(token, safe='')}"
    )
    adaptive_url = (
        f"{scheme}://preview/{quote(job_id, safe='')}"
        f"?mode=adaptive&token={quote(token, safe='')}"
    )
    expires_at = datetime.now(UTC) + timedelta(seconds=config.token_ttl_sec)
    return PreviewSession(
        token=token,
        token_hash=token_hash,
        fixed_url=fixed_url,
        adaptive_url=adaptive_url,
        expires_at=expires_at,
        static_port=static_port,
        adaptive_port=adaptive_port,
    )


def write_preview_sidecar(
    project_dir: Path,
    *,
    job_id: str,
    session: PreviewSession,
    feature_slug: str | None,
) -> Path:
    """Persist preview session metadata for the local companion."""
    import json

    meta_dir = project_dir / ".figma-flutter"
    meta_dir.mkdir(parents=True, exist_ok=True)
    path = meta_dir / "preview-session.json"
    payload: dict[str, Any] = {
        "jobId": job_id,
        "featureSlug": feature_slug,
        "tokenHash": session.token_hash,
        "staticPort": session.static_port,
        "adaptivePort": session.adaptive_port,
        "expiresAt": session.expires_at.isoformat(),
        "projectDir": project_dir.as_posix(),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
