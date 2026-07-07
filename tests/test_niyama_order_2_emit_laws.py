"""Regression laws from niyama_order_2 batch repair (generic, not screen-patched)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from figma_flutter_agent.generator.ir.extracted import promote_screen_ir_extracted_hosts
from figma_flutter_agent.parser.boundaries.assets import (
    apply_semantic_image_manifest_bindings,
    discover_asset_path_for_node,
    discover_role_named_raster,
    lookup_asset_path_for_component_vector_family,
    resolve_discovered_vector_asset_keys,
    resolve_missing_image_asset_keys,
)
from figma_flutter_agent.parser.interaction.text_actions import (
    layout_fact_narrow_centered_figma_single_line_title,
    layout_fact_painted_cta_action_shell,
)
from figma_flutter_agent.parser.richtext import resolve_uniform_text_override_color
from figma_flutter_agent.pipeline.local_assets import (
    _stem_matches_labels,
    local_asset_manifest_from_project,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    ComponentVariant,
    NodeStyle,
    NodeType,
    ScreenIr,
    Sizing,
    WidgetIrKind,
    WidgetIrNode,
    WidgetIrRef,
)


def test_component_vector_family_skips_adjacent_icon_library_ids(tmp_path: Path) -> None:
    icons = tmp_path / "assets" / "icons"
    icons.mkdir(parents=True)
    (icons / "vector_1162_10106.svg").write_text("<svg></svg>", encoding="utf-8")
    asset_index = {"1162_10106": "assets/icons/vector_1162_10106.svg"}
    map_variant = "I3561:43011;1435:18098;1162:10099"
    assert lookup_asset_path_for_component_vector_family(asset_index, map_variant) is None
    assert discover_asset_path_for_node(tmp_path, map_variant) is None
    cutlery_variant = "I3561:42994;1406:12001;1162:10248"
    assert (
        lookup_asset_path_for_component_vector_family(
            asset_index,
            cutlery_variant,
            component_ref="3481:34993",
        )
        is None
    )
    assert (
        discover_asset_path_for_node(
            tmp_path,
            cutlery_variant,
            asset_index=asset_index,
            component_ref="3481:34993",
        )
        is None
    )


def test_discover_role_named_raster_maps_icon_component_to_png(tmp_path: Path) -> None:
    images = tmp_path / "assets" / "images"
    images.mkdir(parents=True)
    (images / "location.png").write_bytes(b"png")
    vector = CleanDesignTreeNode(
        id="1:map",
        name="Vector",
        type=NodeType.VECTOR,
        sizing=Sizing(width=28.0, height=28.0),
        variant=ComponentVariant(
            component_id="1435:18098",
            component_name="Icons/28/Map",
            variant_properties={"Icons": "28/Map"},
        ),
    )
    assert discover_role_named_raster(tmp_path, vector) == "assets/images/location.png"


def test_resolve_discovered_vector_prefers_role_raster_over_family_alias(tmp_path: Path) -> None:
    icons = tmp_path / "assets" / "icons"
    images = tmp_path / "assets" / "images"
    icons.mkdir(parents=True)
    images.mkdir(parents=True)
    (icons / "vector_1162_10106.svg").write_text("<svg></svg>", encoding="utf-8")
    (images / "tableware.png").write_bytes(b"png")
    vector = CleanDesignTreeNode(
        id="I3561:42994;1406:12001;1162:10248",
        name="Vector",
        type=NodeType.VECTOR,
        component_ref="3481:34993",
        sizing=Sizing(width=28.0, height=28.0),
        variant=ComponentVariant(
            component_id="1406:12001",
            component_name="Icons/28/Cutlery",
            variant_properties={"Icons": "28/Cutlery"},
        ),
    )
    resolve_discovered_vector_asset_keys(vector, tmp_path)
    assert vector.vector_asset_key is None
    assert vector.image_asset_key == "assets/images/tableware.png"


def test_semantic_raster_binds_product_thumbnail_by_title_word(tmp_path: Path) -> None:
    images = tmp_path / "assets" / "images"
    images.mkdir(parents=True)
    (images / "ramen-chicken.png").write_bytes(b"png")
    img = CleanDesignTreeNode(
        id="1:img",
        name="Img",
        type=NodeType.IMAGE,
        sizing=Sizing(width=76.0, height=76.0),
    )
    title = CleanDesignTreeNode(
        id="1:title",
        name="Title",
        type=NodeType.TEXT,
        text="Вок рамен с курицей\nв кисло-сладком соусе",
    )
    body = CleanDesignTreeNode(
        id="1:body",
        name="Body",
        type=NodeType.COLUMN,
        children=[title],
    )
    row = CleanDesignTreeNode(
        id="1:row",
        name="Card",
        type=NodeType.ROW,
        children=[img, body],
    )
    root = CleanDesignTreeNode(
        id="1:root",
        name="Order product",
        type=NodeType.STACK,
        variant=ComponentVariant(
            component_id="3481:34945",
            component_name="Order product",
            variant_properties={"Order product": "Inorder"},
        ),
        children=[row],
    )
    manifest = local_asset_manifest_from_project(tmp_path, clean_tree=root)
    image_entries = [entry for entry in manifest.entries if entry.kind == "image"]
    assert len(image_entries) == 1
    assert image_entries[0].node_id == "1:img"
    assert image_entries[0].asset_path == "assets/images/ramen-chicken.png"


def test_delivered_variant_binds_meal_raster(tmp_path: Path) -> None:
    images = tmp_path / "assets" / "images"
    images.mkdir(parents=True)
    (images / "meal.png").write_bytes(b"png")
    img = CleanDesignTreeNode(
        id="1:meal",
        name="Img",
        type=NodeType.IMAGE,
        sizing=Sizing(width=96.0, height=96.0),
        variant=ComponentVariant(
            component_id="1406:13315",
            component_name="Order status",
            variant_properties={"Order status": "Delivered"},
        ),
    )
    root = CleanDesignTreeNode(id="1:root", name="Header", type=NodeType.STACK, children=[img])
    manifest = local_asset_manifest_from_project(tmp_path, clean_tree=root)
    bound = {entry.node_id: entry.asset_path for entry in manifest.entries if entry.kind == "image"}
    assert bound.get("1:meal") == "assets/images/meal.png"


def test_layout_fact_painted_cta_action_shell_accepts_neutral_gray_container() -> None:
    shell = CleanDesignTreeNode(
        id="1:cta",
        name="Button",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=343.0, height=48.0),
        style=NodeStyle(background_color="0xFF3A3A3C"),
        children=[
            CleanDesignTreeNode(
                id="1:label",
                name="Label",
                type=NodeType.TEXT,
                text="Оставить отзыв",
            ),
        ],
    )
    assert layout_fact_painted_cta_action_shell(shell)


def test_layout_fact_painted_cta_action_shell_accepts_accent_secondary_container() -> None:
    shell = CleanDesignTreeNode(
        id="1:repeat",
        name="Button",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=168.0, height=50.0),
        style=NodeStyle(background_color="0x33ED9B33"),
        children=[
            CleanDesignTreeNode(
                id="1:label",
                name="Label",
                type=NodeType.TEXT,
                text="Повторить",
            ),
        ],
    )
    assert layout_fact_painted_cta_action_shell(shell)


def test_narrow_centered_title_uses_line_height_ratio_not_px() -> None:
    title = CleanDesignTreeNode(
        id="1:title",
        name="Title",
        type=NodeType.TEXT,
        text="Заказ выполнен",
        sizing=Sizing(width=171.0, height=28.0),
        style=NodeStyle(text_align="CENTER", font_size=22.0, line_height=1.27),
    )
    assert layout_fact_narrow_centered_figma_single_line_title(title, None)


def test_promote_screen_ir_extracted_hosts_upgrades_orphan_blueprints() -> None:
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id="1:root",
            kind=WidgetIrKind.AUTO,
            children=[
                WidgetIrNode(figma_id="1:map", kind=WidgetIrKind.STACK, children=[]),
            ],
        )
    )
    promoted = promote_screen_ir_extracted_hosts(
        screen_ir,
        figma_id_to_widget_name={"1:map": "MapIconWidget"},
    )
    child = promoted.root.children[0]
    assert child.kind == WidgetIrKind.EXTRACTED
    assert child.ref == WidgetIrRef(widget_name="MapIconWidget")
    assert child.children == []


def test_product_row_nested_title_enables_semantic_thumbnail_bind(tmp_path: Path) -> None:
    images = tmp_path / "assets" / "images"
    images.mkdir(parents=True)
    (images / "ramen-chicken.png").write_bytes(b"png")
    (images / "18chip.png").write_bytes(b"png")
    img = CleanDesignTreeNode(
        id="1:img",
        name="Img",
        type=NodeType.IMAGE,
        sizing=Sizing(width=76.0, height=76.0),
    )
    title = CleanDesignTreeNode(
        id="1:title",
        name="Title",
        type=NodeType.TEXT,
        text="Вок рамен с курицей\nв кисло-сладком соусе",
    )
    text_col = CleanDesignTreeNode(
        id="1:text-col",
        name="Text",
        type=NodeType.COLUMN,
        children=[
            CleanDesignTreeNode(
                id="1:head",
                name="Head",
                type=NodeType.ROW,
                children=[title],
            )
        ],
    )
    body = CleanDesignTreeNode(
        id="1:body",
        name="Body",
        type=NodeType.COLUMN,
        children=[text_col],
    )
    row = CleanDesignTreeNode(
        id="1:row",
        name="Card",
        type=NodeType.ROW,
        children=[img, body],
    )
    root = CleanDesignTreeNode(id="1:root", name="Order", type=NodeType.STACK, children=[row])
    manifest = local_asset_manifest_from_project(tmp_path, clean_tree=root)
    bound = {entry.node_id: entry.asset_path for entry in manifest.entries if entry.kind == "image"}
    assert bound["1:img"] == "assets/images/ramen-chicken.png"


def test_stem_match_rejects_numeric_prefix_false_positive() -> None:
    labels = ["1 x 359", "order product"]
    assert not _stem_matches_labels("18chip", labels)


def test_resolve_uniform_text_override_color_reads_single_override_id() -> None:
    node = {
        "type": "TEXT",
        "characters": "1 x 459 ₽",
        "characterStyleOverrides": [3, 3, 3, 3, 3, 3, 3, 3, 3],
        "styleOverrideTable": {
            "3": {
                "fills": [
                    {
                        "type": "SOLID",
                        "color": {"r": 0.556, "g": 0.556, "b": 0.576},
                        "opacity": 1.0,
                    }
                ]
            }
        },
    }
    color = resolve_uniform_text_override_color(node)
    assert color is not None
    assert color.upper().endswith("8E8E93")


@pytest.mark.parametrize(
    ("debug_root",),
    [(Path(".debug/screen/test/niyama_order_2"),)],
)
def test_offline_emit_laws_from_debug_bundle(debug_root: Path) -> None:
    """Integration smoke on frozen debug bundle when present and stable."""
    if not (debug_root / "processed.json").is_file():
        pytest.skip("niyama_order_2 debug bundle unavailable")
    proc = json.loads((debug_root / "processed.json").read_text(encoding="utf-8"))
    pre = json.loads((debug_root / "pre_emit.json").read_text(encoding="utf-8"))
    tree = CleanDesignTreeNode.model_validate(proc["cleanTree"])
    project = Path("apps/test")
    if not project.is_dir():
        pytest.skip("apps/test project unavailable")
    resolve_missing_image_asset_keys(tree, project)
    apply_semantic_image_manifest_bindings(tree, project)

    def find(node_id: str) -> CleanDesignTreeNode | None:
        stack = [tree]
        while stack:
            node = stack.pop()
            if node.id == node_id:
                return node
            stack.extend(node.children)
        return None

    title = find("3561:42981")
    if title is None:
        pytest.skip("title node missing from debug bundle")
    assert layout_fact_narrow_centered_figma_single_line_title(title, None)

    from figma_flutter_agent.generator.layout import render_layout_file
    from figma_flutter_agent.generator.normalize import normalize_clean_tree

    screen_ir = ScreenIr.model_validate(pre["screenIr"])
    norm = normalize_clean_tree(tree, screen_ir=screen_ir)
    layout = render_layout_file(
        norm,
        feature_name="niyama_order_2",
        uses_svg=True,
        screen_ir=screen_ir,
        package_name="test",
        de_archetype_pass=True,
        responsive_enabled=False,
    )["lib/generated/niyama_order_2_layout.dart"]
    assert "maxLines: 1" in layout
    assert "vector_1162_10106" not in layout
    assert layout.count("SizedBox.shrink()") <= 3
