"""Generation-config fingerprint for IR cache identity (Program 10 P0-1a)."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from figma_flutter_agent.config import Settings

ALLOWLIST_FIXTURE = (
    Path(__file__).resolve().parents[3] / "tests/fixtures/generation_config_fingerprint_allowlist.json"
)

DEFAULT_FINGERPRINT_VERSION = "1"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def load_allowlist_paths(*, fixture_path: Path | None = None) -> tuple[str, tuple[str, ...]]:
    """Load canonical settings dot-paths included in generation config hash."""
    path = fixture_path or ALLOWLIST_FIXTURE
    payload = json.loads(path.read_text(encoding="utf-8"))
    version = str(payload.get("generationConfigFingerprintVersion", DEFAULT_FINGERPRINT_VERSION))
    paths = tuple(str(item) for item in payload.get("paths", []))
    return version, paths


def _resolve_dot_path(obj: Any, dot_path: str) -> Any:
    current = obj
    for part in dot_path.split("."):
        current = (
            current.get(part) if isinstance(current, dict) else getattr(current, part, None)
        )
        if current is None:
            return None
    return current


def _canonicalize(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _canonicalize(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_canonicalize(item) for item in value]
    return value


def generation_config_fingerprint(settings: Settings) -> tuple[str, str]:
    """Return (fingerprint_version, sha256_hex) for generation-relevant agent config."""
    version, paths = load_allowlist_paths()
    agent = settings.agent
    snapshot: dict[str, Any] = {}
    for dot_path in paths:
        snapshot[dot_path] = _canonicalize(_resolve_dot_path(agent, dot_path))
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return version, digest


@lru_cache(maxsize=1)
def default_generation_config_hash() -> tuple[str, str]:
    """Fingerprint for default Settings (tests)."""
    return generation_config_fingerprint(Settings())
