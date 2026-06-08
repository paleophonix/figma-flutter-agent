import json
import os
from pathlib import Path

import pytest

from figma_flutter_agent.config import AgentYamlConfig, GenerationConfig, Settings
from figma_flutter_agent.generator.checks.validate import validate_generated_dart
from figma_flutter_agent.generator.planner import plan_from_figma_root
from figma_flutter_agent.parser.tree import build_clean_tree


def _golden_test_settings() -> Settings:
    """Isolate golden tests from repo-local ``.ai-figma-flutter.yml`` overrides."""
    settings = Settings()
    settings.agent = AgentYamlConfig(
        generation=GenerationConfig(),
    )
    return settings


def _normalize_dart(source: str) -> str:
    return "\n".join(line.rstrip() for line in source.strip().splitlines())


def _assert_matches_golden(
    planned_files: dict[str, str],
    golden_dir: Path,
    *,
    relative_paths: list[str],
) -> None:
    update = os.getenv("UPDATE_GOLDEN") == "1"
    for relative_path in relative_paths:
        golden_path = golden_dir / relative_path
        actual = _normalize_dart(planned_files[relative_path])
        if update:
            golden_path.parent.mkdir(parents=True, exist_ok=True)
            golden_path.write_text(actual + "\n", encoding="utf-8")
            continue
        expected = _normalize_dart(golden_path.read_text(encoding="utf-8"))
        if actual != expected:
            raise AssertionError(
                f"Golden mismatch for {relative_path}. "
                f"Run with UPDATE_GOLDEN=1 to refresh {golden_path}"
            )


@pytest.mark.parametrize(
    ("fixture_name", "golden_name"),
    [
        ("figma_node_sample.json", "onboarding"),
        ("figma_cards_sample.json", "catalog"),
    ],
)
def test_planned_output_matches_golden_files(fixture_name: str, golden_name: str) -> None:
    """E2E acceptance: Figma fixture JSON produces stable golden Dart outputs."""
    root = json.loads(Path(f"tests/fixtures/{fixture_name}").read_text(encoding="utf-8"))
    settings = _golden_test_settings()
    planned = plan_from_figma_root(root, settings, node_id=root["id"])
    golden_paths = [
        path
        for path in planned
        if path.startswith(("lib/generated/", "lib/features/", "lib/widgets/", "lib/theme/app_"))
    ]

    _assert_matches_golden(
        planned,
        Path(f"tests/fixtures/golden/{golden_name}"),
        relative_paths=golden_paths,
    )

    tree, _, _, _ = build_clean_tree(root)
    validate_generated_dart(
        planned,
        tree,
        responsive_enabled=settings.agent.responsive.enabled,
        avoid_fixed_sizes=settings.agent.layout.avoid_fixed_sizes,
    )


def test_catalog_fixture_enforces_cluster_widget_golden() -> None:
    root = json.loads(Path("tests/fixtures/figma_cards_sample.json").read_text(encoding="utf-8"))
    planned = plan_from_figma_root(root, _golden_test_settings(), node_id=root["id"])

    assert "lib/widgets/product_card_widget.dart" in planned
    layout = planned["lib/generated/catalog_screen_layout.dart"]
    assert layout.count("const ProductCardWidget()") == 3
