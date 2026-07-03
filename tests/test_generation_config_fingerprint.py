"""Generation config fingerprint tests (Program 10 P0-1a)."""

from __future__ import annotations

import json

from figma_flutter_agent.compiler.generation_config_fingerprint import (
    generation_config_fingerprint,
    load_allowlist_paths,
    packaged_allowlist_path,
)
from figma_flutter_agent.config import Settings
from tests.fixtures.generation_config_fingerprint_allowlist import (
    TEST_ALLOWLIST_FIXTURE,
)


def test_runtime_allowlist_loads_from_package() -> None:
    version, paths = load_allowlist_paths()
    assert version == "1"
    assert packaged_allowlist_path().is_file()
    assert "generation.use_screen_ir" in paths


def test_test_fixture_matches_packaged_allowlist() -> None:
    runtime = json.loads(packaged_allowlist_path().read_text(encoding="utf-8"))
    fixture = json.loads(TEST_ALLOWLIST_FIXTURE.read_text(encoding="utf-8"))
    assert runtime == fixture


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
