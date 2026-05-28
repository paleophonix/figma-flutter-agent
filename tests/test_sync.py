from figma_flutter_agent.parser.navigation import build_feature_routes
from figma_flutter_agent.schemas import CleanDesignTreeNode, DesignTokens, NodeType
from figma_flutter_agent.sync.diff import select_files_for_sync
from figma_flutter_agent.sync.snapshot import (
    GenerationSnapshot,
    hash_clean_tree,
    hash_file_contents,
    hash_tokens,
)


def test_select_files_for_sync_returns_empty_when_unchanged() -> None:
    tree = CleanDesignTreeNode(id="1:1", name="Screen", type=NodeType.COLUMN)
    tokens = DesignTokens(colors={"primary": "0xFF6750A4"})
    tree_hash = hash_clean_tree(tree)
    colors_hash, typography_hash, spacing_hash = hash_tokens(tokens)
    planned = {"lib/theme/app_colors.dart": "colors"}
    snapshot = GenerationSnapshot(
        file_key="abc",
        node_id="1:1",
        feature_name="onboarding",
        tree_hash=tree_hash,
        colors_hash=colors_hash,
        typography_hash=typography_hash,
        spacing_hash=spacing_hash,
        file_hashes={"lib/theme/app_colors.dart": hash_file_contents("colors")},
    )

    selected = select_files_for_sync(
        snapshot,
        file_key="abc",
        node_id="1:1",
        tree_hash=tree_hash,
        colors_hash=colors_hash,
        typography_hash=typography_hash,
        spacing_hash=spacing_hash,
        planned_files=planned,
    )

    assert selected == {}


def test_select_files_for_sync_writes_changed_files_by_hash() -> None:
    tree = CleanDesignTreeNode(id="1:1", name="Screen", type=NodeType.COLUMN)
    old_tokens = DesignTokens(colors={"primary": "0xFF6750A4"})
    new_tokens = DesignTokens(colors={"primary": "0xFF000000"})
    tree_hash = hash_clean_tree(tree)
    old_colors_hash, typography_hash, spacing_hash = hash_tokens(old_tokens)
    new_colors_hash, _, _ = hash_tokens(new_tokens)
    planned = {
        "lib/theme/app_colors.dart": "colors-new",
        "lib/theme/app_theme.dart": "theme-new",
        "lib/features/onboarding/onboarding_screen.dart": "screen",
    }
    snapshot = GenerationSnapshot(
        file_key="abc",
        node_id="1:1",
        feature_name="onboarding",
        tree_hash=tree_hash,
        colors_hash=old_colors_hash,
        typography_hash=typography_hash,
        spacing_hash=spacing_hash,
        file_hashes={
            "lib/theme/app_colors.dart": hash_file_contents("colors-old"),
            "lib/theme/app_theme.dart": hash_file_contents("theme-old"),
            "lib/features/onboarding/onboarding_screen.dart": hash_file_contents("screen"),
        },
    )

    selected = select_files_for_sync(
        snapshot,
        file_key="abc",
        node_id="1:1",
        tree_hash=tree_hash,
        colors_hash=new_colors_hash,
        typography_hash=typography_hash,
        spacing_hash=spacing_hash,
        planned_files=planned,
    )

    assert set(selected.keys()) == {"lib/theme/app_colors.dart", "lib/theme/app_theme.dart"}


def test_select_files_for_sync_includes_theme_when_only_tokens_change() -> None:
    tree = CleanDesignTreeNode(id="1:1", name="Screen", type=NodeType.COLUMN)
    tokens_v1 = DesignTokens(colors={"primary": "0xFF6750A4"})
    tokens_v2 = DesignTokens(colors={"primary": "0xFF111111"})
    tree_hash = hash_clean_tree(tree)
    colors_v1, typography_hash, spacing_hash = hash_tokens(tokens_v1)
    colors_v2, _, _ = hash_tokens(tokens_v2)
    planned = {
        "lib/theme/app_colors.dart": "colors-v2",
        "lib/features/onboarding/onboarding_screen.dart": "screen-unchanged",
    }
    snapshot = GenerationSnapshot(
        file_key="abc",
        node_id="1:1",
        feature_name="onboarding",
        tree_hash=tree_hash,
        colors_hash=colors_v1,
        typography_hash=typography_hash,
        spacing_hash=spacing_hash,
        file_hashes={
            "lib/theme/app_colors.dart": hash_file_contents("colors-v1"),
            "lib/features/onboarding/onboarding_screen.dart": hash_file_contents(
                "screen-unchanged"
            ),
        },
    )

    selected = select_files_for_sync(
        snapshot,
        file_key="abc",
        node_id="1:1",
        tree_hash=tree_hash,
        colors_hash=colors_v2,
        typography_hash=typography_hash,
        spacing_hash=spacing_hash,
        planned_files=planned,
    )

    assert "lib/theme/app_colors.dart" in selected
    assert "lib/features/onboarding/onboarding_screen.dart" not in selected


def test_build_feature_routes_returns_go_router_metadata() -> None:
    routes = build_feature_routes("onboarding")

    assert routes[0].path == "/onboarding"
    assert routes[0].screen_class == "OnboardingScreen"
