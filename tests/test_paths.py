"""Tests for architecture-aware project paths."""

from figma_flutter_agent.config import AgentYamlConfig, FlutterConfig, Settings
from figma_flutter_agent.generator.paths import (
    dart_relative_import_prefix,
    screen_file_path,
    screen_import_path,
    state_file_path,
)
from figma_flutter_agent.generator.planner import GenerationPlanContext, plan_generation_files
from figma_flutter_agent.schemas import CleanDesignTreeNode, DesignTokens, NodeType


def test_layer_first_screen_paths() -> None:
    feature_path = screen_file_path("catalog", architecture="layer_first")
    assert feature_path == "lib/presentation/screens/catalog_screen.dart"
    assert dart_relative_import_prefix(feature_path) == "../../"
    assert screen_import_path("catalog", architecture="layer_first") == (
        "presentation/screens/catalog_screen.dart"
    )
    assert state_file_path("catalog", architecture="layer_first") == (
        "lib/presentation/state/catalog_state.dart"
    )


def test_feature_first_screen_import_prefix() -> None:
    feature_path = screen_file_path("catalog", architecture="feature_first")
    assert dart_relative_import_prefix(feature_path) == "../../"


def test_planner_emits_layer_first_screen() -> None:
    settings = Settings(
        agent=AgentYamlConfig(
            flutter=FlutterConfig(architecture="layer_first"),
        )
    )
    context = GenerationPlanContext(
        settings=settings,
        clean_tree=CleanDesignTreeNode(id="1", name="Catalog", type=NodeType.COLUMN),
        tokens=DesignTokens(),
        resolved_feature="catalog",
        node_id="1:1",
        cluster_summary={},
    )
    files = plan_generation_files(context)

    assert "lib/presentation/screens/catalog_screen.dart" in files
    assert (
        "import 'package:demo_app/presentation/screens/catalog_screen.dart';"
        in files["lib/main.dart"]
    )
