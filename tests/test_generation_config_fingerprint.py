"""Generation config fingerprint tests (Program 10 P0-1a)."""

from __future__ import annotations

import json

from figma_flutter_agent.compiler.generation_config_fingerprint import (
    generation_config_fingerprint,
    load_allowlist_paths,
)
from figma_flutter_agent.config import Settings


def test_allowlist_fixture_loads() -> None:
    version, paths = load_allowlist_paths()
    assert version == "1"
    assert "generation.use_screen_ir" in paths
    assert "semantics.strict_fidelity" in paths


def test_fingerprint_stable_for_default_settings() -> None:
    settings = Settings()
    v1, h1 = generation_config_fingerprint(settings)
    v2, h2 = generation_config_fingerprint(settings)
    assert v1 == v2 == "1"
    assert h1 == h2
    assert len(h1) == 64


def test_fingerprint_changes_when_semantics_toggle() -> None:
    base = Settings()
    toggled = Settings()
    toggled.agent.semantics.strict_fidelity = True
    _, base_hash = generation_config_fingerprint(base)
    _, toggled_hash = generation_config_fingerprint(toggled)
    assert base_hash != toggled_hash


def test_allowlist_paths_are_json_serializable_snapshot() -> None:
    settings = Settings()
    version, paths = load_allowlist_paths()
    agent = settings.agent
    snapshot = {}
    for dot_path in paths:
        parts = dot_path.split(".")
        current = agent
        for part in parts:
            current = getattr(current, part)
        if hasattr(current, "model_dump"):
            snapshot[dot_path] = current.model_dump(mode="json")
        else:
            snapshot[dot_path] = current
    encoded = json.dumps(snapshot, sort_keys=True)
    assert encoded
