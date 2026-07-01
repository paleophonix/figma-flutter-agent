"""Region-aware incremental sync (spec §16 widget / layout granularity)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from figma_flutter_agent.config import Settings
from figma_flutter_agent.generator.ir.version import EMITTER_VERSION
from figma_flutter_agent.generator.paths import screen_file_path
from figma_flutter_agent.generator.planner import plan_from_figma_root
from figma_flutter_agent.parser.tree import build_clean_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode, DesignTokens, NodeType
from figma_flutter_agent.sync.diff import select_files_for_sync
from figma_flutter_agent.sync.regions import (
    RegionSyncState,
    build_incremental_bindings,
)
from figma_flutter_agent.sync.snapshot import (
    GenerationSnapshot,
    hash_clean_tree,
    hash_file_contents,
    hash_tokens,
)


def _catalog_planned(
    root: dict[str, object],
) -> tuple[dict[str, str], RegionSyncState, str]:
    settings = Settings()
    tree, _, _, _ = build_clean_tree(root)
    planned = plan_from_figma_root(root, settings, node_id=str(root["id"]))
    region = RegionSyncState.from_tree(tree)
    feature = "catalog_screen"
    return planned, region, feature


def test_cluster_text_change_rewrites_widget_not_layout() -> None:
    root = json.loads(Path("tests/fixtures/figma_cards_sample.json").read_text(encoding="utf-8"))
    planned_v1, region_v1, feature = _catalog_planned(root)
    tree_v1, _, _, _ = build_clean_tree(root)
    tokens = DesignTokens(colors={"primary": "0xFF6750A4"})
    tree_hash = hash_clean_tree(tree_v1)
    colors_hash, typography_hash, spacing_hash = hash_tokens(tokens)

    snapshot = GenerationSnapshot(
        file_key="cards",
        node_id=str(root["id"]),
        feature_name=feature,
        tree_hash=tree_hash,
        colors_hash=colors_hash,
        typography_hash=typography_hash,
        spacing_hash=spacing_hash,
        file_hashes={path: hash_file_contents(content) for path, content in planned_v1.items()},
        layout_region_hash=region_v1.layout_region_hash,
        cluster_hashes=region_v1.cluster_hashes,
        emitter_version=EMITTER_VERSION,
    )

    root_v2 = copy.deepcopy(root)
    for card in root_v2["children"]:
        card["children"][0]["characters"] = "Updated title"

    tree_v2, _, _, cluster_summary_v2 = build_clean_tree(root_v2)
    planned_v2, region_v2, _ = _catalog_planned(root_v2)
    bindings = build_incremental_bindings(
        clean_tree=tree_v2,
        cluster_summary=cluster_summary_v2,
        feature_name=feature,
        planned_files=planned_v2,
        cluster_min_count=Settings().agent.generation.cluster_min_count,
        widget_suffix=Settings().agent.naming.widget_suffix,
        enforce_cluster_widgets=True,
    )

    selected = select_files_for_sync(
        snapshot,
        file_key="cards",
        node_id=str(root["id"]),
        tree_hash=hash_clean_tree(tree_v2),
        colors_hash=colors_hash,
        typography_hash=typography_hash,
        spacing_hash=spacing_hash,
        planned_files=planned_v2,
        region_state=region_v2,
        bindings=bindings,
    )

    assert "lib/widgets/product_card_widget.dart" in selected
    assert "lib/generated/catalog_screen_layout.dart" not in selected
    assert "lib/features/catalog_screen/catalog_screen_screen.dart" not in selected
    assert region_v1.layout_region_hash == region_v2.layout_region_hash


def test_non_cluster_change_rewrites_layout() -> None:
    root = json.loads(Path("tests/fixtures/figma_cards_sample.json").read_text(encoding="utf-8"))
    planned_v1, region_v1, feature = _catalog_planned(root)
    tree_v1, _, _, cluster_summary = build_clean_tree(root)

    root_v2 = copy.deepcopy(root)
    root_v2["itemSpacing"] = 24

    tree_v2, _, _, _ = build_clean_tree(root_v2)
    planned_v2, region_v2, _ = _catalog_planned(root_v2)
    bindings = build_incremental_bindings(
        clean_tree=tree_v2,
        cluster_summary=cluster_summary,
        feature_name=feature,
        planned_files=planned_v2,
        cluster_min_count=Settings().agent.generation.cluster_min_count,
        widget_suffix=Settings().agent.naming.widget_suffix,
        enforce_cluster_widgets=True,
    )

    tokens = DesignTokens(colors={"primary": "0xFF6750A4"})
    tree_hash_v1 = hash_clean_tree(tree_v1)
    colors_hash, typography_hash, spacing_hash = hash_tokens(tokens)

    snapshot = GenerationSnapshot(
        file_key="cards",
        node_id=str(root["id"]),
        feature_name=feature,
        tree_hash=tree_hash_v1,
        colors_hash=colors_hash,
        typography_hash=typography_hash,
        spacing_hash=spacing_hash,
        file_hashes={path: hash_file_contents(content) for path, content in planned_v1.items()},
        layout_region_hash=region_v1.layout_region_hash,
        cluster_hashes=region_v1.cluster_hashes,
        emitter_version=EMITTER_VERSION,
    )

    selected = select_files_for_sync(
        snapshot,
        file_key="cards",
        node_id=str(root["id"]),
        tree_hash=hash_clean_tree(tree_v2),
        colors_hash=colors_hash,
        typography_hash=typography_hash,
        spacing_hash=spacing_hash,
        planned_files=planned_v2,
        region_state=region_v2,
        bindings=bindings,
    )

    assert "lib/generated/catalog_screen_layout.dart" in selected


def test_screen_paths_use_planner_path_not_substring() -> None:
    """Feature ``user`` must not bind ``user_settings`` screen via token overlap."""
    minimal_tree = CleanDesignTreeNode(
        id="root",
        name="Root",
        type=NodeType.CONTAINER,
        children=[],
    )
    planned = {
        "lib/features/user/user_screen.dart": "// user",
        "lib/features/user_settings/user_settings_screen.dart": "// settings",
        "lib/generated/user_layout.dart": "// layout",
    }
    bindings = build_incremental_bindings(
        clean_tree=minimal_tree,
        cluster_summary={},
        feature_name="user",
        planned_files=planned,
        cluster_min_count=2,
        widget_suffix="Widget",
        enforce_cluster_widgets=False,
        architecture="feature_first",
    )
    expected = screen_file_path("user", architecture="feature_first")
    assert bindings.screen_paths == frozenset({expected})
    assert "lib/features/user_settings/user_settings_screen.dart" not in bindings.screen_paths


def test_screen_path_rewrites_when_content_changes_without_layout_delta() -> None:
    """LLM screen regen must not be skipped when layout region hash is unchanged."""
    minimal_tree = CleanDesignTreeNode(
        id="root",
        name="Root",
        type=NodeType.CONTAINER,
        children=[],
    )
    screen_path = screen_file_path("reminders", architecture="feature_first")
    planned_v1 = {
        screen_path: "class RemindersScreen { Widget build() => const RemindersLayout(); }",
        "lib/generated/reminders_layout.dart": "// layout v1",
    }
    planned_v2 = {
        screen_path: "class RemindersScreen { Widget build() => Column(children: [Text('LLM')]); }",
        "lib/generated/reminders_layout.dart": "// layout v1",
    }
    region = RegionSyncState.from_tree(minimal_tree)
    bindings = build_incremental_bindings(
        clean_tree=minimal_tree,
        cluster_summary={},
        feature_name="reminders",
        planned_files=planned_v2,
        cluster_min_count=2,
        widget_suffix="Widget",
        enforce_cluster_widgets=False,
    )
    tokens = DesignTokens()
    colors_hash, typography_hash, spacing_hash = hash_tokens(tokens)
    tree_hash = hash_clean_tree(minimal_tree)
    snapshot = GenerationSnapshot(
        file_key="abc",
        node_id="1:1",
        feature_name="reminders",
        tree_hash=tree_hash,
        colors_hash=colors_hash,
        typography_hash=typography_hash,
        spacing_hash=spacing_hash,
        file_hashes={path: hash_file_contents(content) for path, content in planned_v1.items()},
        layout_region_hash=region.layout_region_hash,
        cluster_hashes=region.cluster_hashes,
        emitter_version=EMITTER_VERSION,
    )

    selected = select_files_for_sync(
        snapshot,
        file_key="abc",
        node_id="1:1",
        tree_hash=tree_hash,
        colors_hash=colors_hash,
        typography_hash=typography_hash,
        spacing_hash=spacing_hash,
        planned_files=planned_v2,
        region_state=region,
        bindings=bindings,
    )

    assert screen_path in selected
    assert "lib/generated/reminders_layout.dart" not in selected


def test_layout_rewrites_when_planned_content_changes_without_region_delta() -> None:
    """Emitter-only layout changes must still write ``*_layout.dart``."""
    minimal_tree = CleanDesignTreeNode(
        id="root",
        name="Root",
        type=NodeType.CONTAINER,
        children=[],
    )
    layout_path = "lib/generated/reminders_layout.dart"
    screen_path = screen_file_path("reminders", architecture="feature_first")
    planned_v1 = {
        screen_path: "class RemindersScreen { Widget build() => const RemindersLayout(); }",
        layout_path: "// layout v1",
    }
    planned_v2 = {
        screen_path: planned_v1[screen_path],
        layout_path: "// layout v2 with chip row emit",
    }
    region = RegionSyncState.from_tree(minimal_tree)
    bindings = build_incremental_bindings(
        clean_tree=minimal_tree,
        cluster_summary={},
        feature_name="reminders",
        planned_files=planned_v2,
        cluster_min_count=2,
        widget_suffix="Widget",
        enforce_cluster_widgets=False,
    )
    tokens = DesignTokens()
    colors_hash, typography_hash, spacing_hash = hash_tokens(tokens)
    tree_hash = hash_clean_tree(minimal_tree)
    snapshot = GenerationSnapshot(
        file_key="abc",
        node_id="1:1",
        feature_name="reminders",
        tree_hash=tree_hash,
        colors_hash=colors_hash,
        typography_hash=typography_hash,
        spacing_hash=spacing_hash,
        file_hashes={path: hash_file_contents(content) for path, content in planned_v1.items()},
        layout_region_hash=region.layout_region_hash,
        cluster_hashes=region.cluster_hashes,
        emitter_version=EMITTER_VERSION,
    )

    selected = select_files_for_sync(
        snapshot,
        file_key="abc",
        node_id="1:1",
        tree_hash=tree_hash,
        colors_hash=colors_hash,
        typography_hash=typography_hash,
        spacing_hash=spacing_hash,
        planned_files=planned_v2,
        region_state=region,
        bindings=bindings,
    )

    assert layout_path in selected
    assert screen_path not in selected


def test_layout_rewrites_when_emitter_version_changes_without_content_delta() -> None:
    """Emitter semver bumps must rewrite layout even when planned hash is unchanged."""
    minimal_tree = CleanDesignTreeNode(
        id="root",
        name="Root",
        type=NodeType.CONTAINER,
        children=[],
    )
    layout_path = "lib/generated/reminders_layout.dart"
    screen_path = screen_file_path("reminders", architecture="feature_first")
    layout_body = "// layout v1"
    planned = {
        screen_path: "class RemindersScreen { Widget build() => const RemindersLayout(); }",
        layout_path: layout_body,
    }
    region = RegionSyncState.from_tree(minimal_tree)
    bindings = build_incremental_bindings(
        clean_tree=minimal_tree,
        cluster_summary={},
        feature_name="reminders",
        planned_files=planned,
        cluster_min_count=2,
        widget_suffix="Widget",
        enforce_cluster_widgets=False,
    )
    tokens = DesignTokens()
    colors_hash, typography_hash, spacing_hash = hash_tokens(tokens)
    tree_hash = hash_clean_tree(minimal_tree)
    snapshot = GenerationSnapshot(
        file_key="abc",
        node_id="1:1",
        feature_name="reminders",
        tree_hash=tree_hash,
        colors_hash=colors_hash,
        typography_hash=typography_hash,
        spacing_hash=spacing_hash,
        file_hashes={path: hash_file_contents(content) for path, content in planned.items()},
        layout_region_hash=region.layout_region_hash,
        cluster_hashes=region.cluster_hashes,
        emitter_version="2026.01.0",
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
        region_state=region,
        bindings=bindings,
    )

    assert layout_path in selected
    assert screen_path not in selected


def test_layout_rewrites_when_on_disk_content_drifts_from_planned(tmp_path: Path) -> None:
    """Stale on-disk layout fossils must rewrite even when snapshot matches planned."""
    minimal_tree = CleanDesignTreeNode(
        id="root",
        name="Root",
        type=NodeType.CONTAINER,
        children=[],
    )
    layout_path = "lib/generated/reminders_layout.dart"
    screen_path = screen_file_path("reminders", architecture="feature_first")
    planned_body = "// layout v2 emitter fix"
    planned = {
        screen_path: "class RemindersScreen { Widget build() => const RemindersLayout(); }",
        layout_path: planned_body,
    }
    region = RegionSyncState.from_tree(minimal_tree)
    bindings = build_incremental_bindings(
        clean_tree=minimal_tree,
        cluster_summary={},
        feature_name="reminders",
        planned_files=planned,
        cluster_min_count=2,
        widget_suffix="Widget",
        enforce_cluster_widgets=False,
    )
    tokens = DesignTokens()
    colors_hash, typography_hash, spacing_hash = hash_tokens(tokens)
    tree_hash = hash_clean_tree(minimal_tree)
    snapshot = GenerationSnapshot(
        file_key="abc",
        node_id="1:1",
        feature_name="reminders",
        tree_hash=tree_hash,
        colors_hash=colors_hash,
        typography_hash=typography_hash,
        spacing_hash=spacing_hash,
        file_hashes={path: hash_file_contents(content) for path, content in planned.items()},
        layout_region_hash=region.layout_region_hash,
        cluster_hashes=region.cluster_hashes,
        emitter_version=EMITTER_VERSION,
    )
    project_dir = tmp_path / "app"
    layout_disk = project_dir / layout_path
    layout_disk.parent.mkdir(parents=True)
    layout_disk.write_text("// stale fossil layout on disk", encoding="utf-8")

    selected = select_files_for_sync(
        snapshot,
        file_key="abc",
        node_id="1:1",
        tree_hash=tree_hash,
        colors_hash=colors_hash,
        typography_hash=typography_hash,
        spacing_hash=spacing_hash,
        planned_files=planned,
        region_state=region,
        bindings=bindings,
        project_dir=project_dir,
    )

    assert layout_path in selected
    assert selected[layout_path] == planned_body
