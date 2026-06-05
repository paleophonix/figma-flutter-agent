#!/usr/bin/env python3
"""Refresh planned Dart golden files under tests/fixtures/golden/ (no pytest)."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.config import AgentYamlConfig, GenerationConfig, Settings
from figma_flutter_agent.generator.planner import plan_from_figma_root

_REPO = Path(__file__).resolve().parents[1]
_CASES = (
    ("figma_node_sample.json", "onboarding"),
    ("figma_cards_sample.json", "catalog"),
)


def _refresh(fixture_name: str, golden_name: str) -> None:
    root = json.loads((_REPO / "tests" / "fixtures" / fixture_name).read_text(encoding="utf-8"))
    settings = Settings()
    settings.agent = AgentYamlConfig(
        generation=GenerationConfig(use_deterministic_screen=True),
    )
    planned = plan_from_figma_root(root, settings, node_id=root["id"])
    golden_dir = _REPO / "tests" / "fixtures" / "golden" / golden_name
    relative_paths = [
        path
        for path in planned
        if path.startswith(("lib/generated/", "lib/features/", "lib/widgets/", "lib/theme/app_"))
    ]
    for relative_path in relative_paths:
        target = golden_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(planned[relative_path].strip() + "\n", encoding="utf-8")
        print(f"updated {target.relative_to(_REPO)}")


def main() -> None:
    for fixture_name, golden_name in _CASES:
        _refresh(fixture_name, golden_name)


if __name__ == "__main__":
    main()
