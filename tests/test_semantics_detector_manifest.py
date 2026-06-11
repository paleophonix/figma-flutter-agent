"""Detector manifest CI gate: new detector modules require negative traps."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "layouts" / "semantics"
MANIFEST_PATH = FIXTURE_ROOT / "manifest.yaml"
DETECTORS_DIR = REPO_ROOT / "src" / "figma_flutter_agent" / "parser" / "semantics" / "detectors"

_EXEMPT = frozenset({"__init__.py", "registry.py", "_base.py"})


def _detector_modules() -> list[str]:
    return sorted(
        path.name
        for path in DETECTORS_DIR.glob("*.py")
        if path.name not in _EXEMPT
    )


def test_detector_manifest_covers_all_modules() -> None:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    traps_by_module: dict[str, list[str]] = manifest.get("negative_traps") or {}
    for module_name in _detector_modules():
        assert module_name in traps_by_module, f"Missing manifest entry for {module_name}"
        assert traps_by_module[module_name], f"Empty trap list for {module_name}"


def test_manifest_trap_fixtures_exist() -> None:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    traps_by_module: dict[str, list[str]] = manifest.get("negative_traps") or {}
    for module_name, traps in traps_by_module.items():
        for rel_path in traps:
            fixture_path = FIXTURE_ROOT / rel_path
            assert fixture_path.is_file(), f"{module_name}: missing trap {rel_path}"
