"""Verbatica paywall emit-law regressions (hero raster, plan row flex, CTA padding)."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.generator.layout.flex_policy.alignment import (
    _flex_child_should_bind_fixed_height,
)
from figma_flutter_agent.generator.layout.flex_policy.buttons import (
    button_is_pill_with_label_column,
)
from figma_flutter_agent.generator.layout.flex_policy.extents import bind_row_cross_axis_height
from figma_flutter_agent.generator.layout.flex_policy.stack import (
    stack_should_emit_horizontal_inflow_row,
)
from figma_flutter_agent.generator.layout.flex_policy.wrap import (
    neutralize_parent_data_for_flex_child,
)
from figma_flutter_agent.generator.layout.scroll import _symmetric_pill_button_padding
from figma_flutter_agent.generator.layout.style.text_emit import text_style_expr
from figma_flutter_agent.generator.layout.widgets.positioned import _apply_layout_slot_wraps
from figma_flutter_agent.generator.layout.widgets.svg import _svg_fit_mode
from figma_flutter_agent.parser.boundaries.assets import (
    raster_asset_export_viable,
    resolve_pruned_cluster_instance_assets,
    resolve_render_boundary_asset_keys,
)
from figma_flutter_agent.pipeline.local_assets import local_asset_manifest_from_project
from figma_flutter_agent.schemas import (
    Alignment,
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Padding,
    Sizing,
    SizingMode,
    StackPlacement,
    TextMetricsFrame,
    WrapKind,
)
from figma_flutter_agent.schemas.style import ComponentVariant
from figma_flutter_agent.schemas.geometry import LayoutSlotIr


def _write_minimal_viable_png(path: Path) -> None:
    """Write an 8x8 RGBA PNG that passes ``raster_asset_export_viable``."""
    from PIL import Image

    Image.new("RGBA", (8, 8), (0, 0, 0, 0)).save(path)


def test_semantic_raster_binds_render_boundary_hero(tmp_path: Path) -> None:
    images = tmp_path / "assets" / "images"
    images.mkdir(parents=True)
    _write_minimal_viable_png(images / "portrait.png")
    (images / ".figma-bindings.json").write_text(
        '{"bindings": {"portrait.png": "2399:42779"}}',
        encoding="utf-8",
    )
    hero = CleanDesignTreeNode(
        id="2399:42779",
        name="Img",
        type=NodeType.STACK,
        render_boundary=True,
        flatten_figma_node_ids=["2399:42780", "2399:42781"],
        sizing=Sizing(width=393.0, height=454.0),
    )
    root = CleanDesignTreeNode(id="screen", name="Screen", type=NodeType.STACK, children=[hero])
    manifest = local_asset_manifest_from_project(tmp_path, clean_tree=root)
    bound = [entry for entry in manifest.entries if entry.node_id == hero.id]
    assert len(bound) == 1
    assert bound[0].asset_path == "assets/images/portrait.png"


def test_render_boundary_wallpaper_raster_uses_cover_fit() -> None:
    node = CleanDesignTreeNode(
        id="1:hero",
        name="Hero",
        type=NodeType.STACK,
        render_boundary=True,
        flatten_figma_node_ids=["1:photo"],
        image_asset_key="assets/images/portrait.png",
        sizing=Sizing(width=393.0, height=454.0),
    )
    assert _svg_fit_mode(node, 393.0, 454.0) == "BoxFit.cover"


def test_payment_plan_trailing_cluster_skips_layout_slot_width_pin() -> None:
    """Law: trailing price cluster must not receive rigid CONSTRAINED_BOX width pins."""
    trailing = CleanDesignTreeNode(
        id="1:trail",
        name="price cluster",
        type=NodeType.ROW,
        spacing=8.0,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=93.0, height=24.0),
        layout_slot=LayoutSlotIr(wraps=(WrapKind.CONSTRAINED_BOX, WrapKind.FLEXIBLE_LOOSE)),
        children=[
            CleanDesignTreeNode(
                id="1:body",
                name="Body",
                type=NodeType.COLUMN,
                children=[
                    CleanDesignTreeNode(
                        id="1:price",
                        name="39,99$",
                        type=NodeType.TEXT,
                        text="39,99$",
                        sizing=Sizing(width=61.0, height=24.0),
                    )
                ],
            ),
            CleanDesignTreeNode(
                id="1:radio",
                name="check_circle",
                type=NodeType.VECTOR,
                sizing=Sizing(width=24.0, height=24.0),
            ),
        ],
    )
    parent = CleanDesignTreeNode(
        id="1:row",
        name="plan row",
        type=NodeType.ROW,
        sizing=Sizing(width_mode=SizingMode.FILL, width=328.0, height=40.0),
        children=[trailing],
    )
    wrapped = _apply_layout_slot_wraps(
        trailing,
        "Row(children: [Text('39,99$')])",
        parent_type=NodeType.ROW,
        parent_node=parent,
    )
    assert "SizedBox(width: 93.0" not in wrapped.replace("\n", "")


def test_pill_button_padding_clamps_vertical_to_host_height() -> None:
    button = CleanDesignTreeNode(
        id="1:cta",
        name="Button",
        type=NodeType.BUTTON,
        sizing=Sizing(width=328.0, height=56.0),
        padding=Padding(top=14.0, bottom=14.0, left=20.0, right=20.0),
        style=NodeStyle(border_radius=20.0),
        children=[
            CleanDesignTreeNode(
                id="1:label",
                name="Subscribe",
                type=NodeType.TEXT,
                text="Subscribe",
                style=NodeStyle(font_size=16.0, line_height=1.19),
                text_metrics_frame=TextMetricsFrame(line_height_px=34.0),
            )
        ],
    )
    inset = _symmetric_pill_button_padding(button)
    assert inset is not None
    assert "vertical: 14.0" not in inset
    assert "11.0" in inset


def test_verbatica_processed_hero_has_no_wrong_vector_after_asset_passes() -> None:
    """Integration guard: fresh parse + assets must not bind check_circle onto hero."""
    from figma_flutter_agent.assets.screen_frame import build_screen_frame_exclude_ids
    from figma_flutter_agent.parser.boundaries.assets import (
        render_boundary_asset_path,
        resolve_missing_image_asset_keys,
        resolve_render_boundary_asset_keys,
    )
    from figma_flutter_agent.pipeline.dump import load_fetch_result_from_dump
    from figma_flutter_agent.stages import parse_figma_frame
    from figma_flutter_agent.stages.assets import finalize_screen_assets

    dump = Path("e:/@dev/figma-flutter-agent/.debug/screen/test/verbatica_paywall/raw.json")
    project = Path("e:/@dev/figma-flutter-agent/apps/test")
    if not dump.is_file():
        return
    fetch = load_fetch_result_from_dump(dump, file_key="dummy", node_id="2399:42778")
    parsed = parse_figma_frame(fetch)
    exclude = build_screen_frame_exclude_ids(fetch.node_id, set())
    manifest = local_asset_manifest_from_project(
        project,
        exclude_node_ids=exclude,
        clean_tree=parsed.clean_tree,
    )
    finalize_screen_assets(
        project_dir=project,
        clean_tree=parsed.clean_tree,
        destination_trees={},
        manifest=manifest,
        primary_node_id=fetch.node_id,
        destination_node_ids=set(),
    )
    resolve_render_boundary_asset_keys(
        parsed.clean_tree,
        project,
        manifest,
        strict=False,
    )
    resolve_missing_image_asset_keys(parsed.clean_tree, project)

    def hero(tree: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
        stack = [tree]
        while stack:
            node = stack.pop()
            if node.id == "2399:42779":
                return node
            stack.extend(node.children)
        return None

    node = hero(parsed.clean_tree)
    assert node is not None
    assert node.vector_asset_key != "assets/icons/vector_2399_42798.svg"
    assert node.vector_asset_key != render_boundary_asset_path(node.id)
    portrait_entries = [
        entry
        for entry in manifest.entries
        if entry.node_id == node.id and entry.asset_path.endswith(".png")
    ]
    if portrait_entries:
        assert node.image_asset_key == portrait_entries[0].asset_path
    elif (project / "assets" / "images" / "portrait.png").is_file():
        portrait_path = project / "assets" / "images" / "portrait.png"
        if raster_asset_export_viable(portrait_path):
            assert node.image_asset_key is not None
            assert node.image_asset_key.endswith("portrait.png")
        else:
            assert node.image_asset_key is None


def test_render_boundary_candidates_use_figma_bindings_for_flatten_ids(tmp_path: Path) -> None:
    images = tmp_path / "assets" / "images"
    images.mkdir(parents=True)
    _write_minimal_viable_png(images / "portrait.png")
    (images / ".figma-bindings.json").write_text(
        '{"bindings": {"portrait.png": "2399:42780"}}',
        encoding="utf-8",
    )
    hero = CleanDesignTreeNode(
        id="2399:42779",
        name="Img",
        type=NodeType.STACK,
        render_boundary=True,
        flatten_figma_node_ids=["2399:42780"],
        sizing=Sizing(width=393.0, height=454.0),
    )
    root = CleanDesignTreeNode(id="screen", name="Screen", type=NodeType.STACK, children=[hero])
    from figma_flutter_agent.parser.boundaries.assets import resolve_render_boundary_asset_keys

    resolve_render_boundary_asset_keys(root, tmp_path, None, strict=False)
    assert hero.image_asset_key == "assets/images/portrait.png"


def test_status_chrome_space_between_inflow_emits_horizontal_row() -> None:
    time_row = CleanDesignTreeNode(
        id="time",
        name="Time",
        type=NodeType.ROW,
        sizing=Sizing(width=128.0, height=40.0),
        children=[
            CleanDesignTreeNode(
                id="clock",
                name="9:30",
                type=NodeType.TEXT,
                text="9:30",
                sizing=Sizing(width=29.0, height=20.0),
            )
        ],
        geometry_frame=None,
    )
    icons_row = CleanDesignTreeNode(
        id="icons",
        name="Status Icons",
        type=NodeType.ROW,
        sizing=Sizing(width=46.0, height=52.0),
        children=[
            CleanDesignTreeNode(
                id="wifi",
                name="Wifi",
                type=NodeType.STACK,
                sizing=Sizing(width=16.0, height=16.0),
                children=[],
            )
        ],
    )
    notch = CleanDesignTreeNode(
        id="notch",
        name="Camera",
        type=NodeType.STACK,
        layout_positioning="ABSOLUTE",
        stack_placement=StackPlacement(left=168.0, top=8.0, width=24.0, height=24.0),
        sizing=Sizing(width=24.0, height=24.0),
        children=[],
    )
    status = CleanDesignTreeNode(
        id="status",
        name="Status",
        type=NodeType.STACK,
        alignment=Alignment(main="spaceBetween", cross="center"),
        sizing=Sizing(width=360.0, height=40.0),
        children=[time_row, icons_row, notch],
    )
    assert stack_should_emit_horizontal_inflow_row(status)


def test_horizontal_inflow_row_strips_positioned_parent_data() -> None:
    """Law: flex_parent_data_illegal_host — Row children must not carry Positioned."""
    positioned_clock = "Positioned(left: 16.0, top: 0.0, child: Text('9:30'))"
    stripped = neutralize_parent_data_for_flex_child(positioned_clock)
    assert "Positioned(" not in stripped
    assert "Text('9:30')" in stripped


def test_payment_plan_slot_shell_row_binds_fixed_height() -> None:
    """Law: fixed_height_slot_intrinsic_collapse — bordered Slot rows pin Figma height."""
    slot = CleanDesignTreeNode(
        id="slot",
        name="Slot",
        type=NodeType.ROW,
        padding=Padding(top=16.0, bottom=16.0, left=16.0, right=16.0),
        sizing=Sizing(
            width_mode=SizingMode.FILL,
            height_mode=SizingMode.FIXED,
            width=328.0,
            height=80.0,
        ),
        style=NodeStyle(
            border_radius=24.0,
            border_width=2.0,
            border_color="0xFF8459C9",
            has_stroke=True,
        ),
        children=[
            CleanDesignTreeNode(
                id="body",
                name="Body",
                type=NodeType.COLUMN,
                sizing=Sizing(width=203.0, height=40.0),
                children=[
                    CleanDesignTreeNode(
                        id="label",
                        name="12 months",
                        type=NodeType.TEXT,
                        text="12 months",
                        sizing=Sizing(width=189.0, height=24.0),
                    )
                ],
            )
        ],
    )
    assert _flex_child_should_bind_fixed_height(slot)


def test_payment_radio_glyph_host_skips_layout_slot_width_pin() -> None:
    """Law: row_list_glyph_svg_extent_mismatch — compact radio host keeps full glyph width."""
    radio = CleanDesignTreeNode(
        id="radio",
        name="check_circle",
        type=NodeType.ROW,
        cluster_id="cluster_0",
        padding=Padding(top=2.0, bottom=2.0, left=2.0, right=2.0),
        sizing=Sizing(width_mode=SizingMode.FIXED, width=24.0, height=24.0),
        layout_slot=LayoutSlotIr(wraps=(WrapKind.CONSTRAINED_BOX,)),
        children=[],
    )
    wrapped = _apply_layout_slot_wraps(
        radio,
        "SvgPicture.asset('assets/icons/vector_check.svg')",
        parent_type=NodeType.ROW,
        parent_node=CleanDesignTreeNode(
            id="trail",
            name="price cluster",
            type=NodeType.ROW,
            children=[radio],
        ),
    )
    assert "SizedBox(width: 20.0" not in wrapped.replace("\n", "")


def test_row_cross_axis_height_clamps_status_icon_cluster_row() -> None:
    icons = CleanDesignTreeNode(
        id="icons",
        name="Status Icons",
        type=NodeType.ROW,
        sizing=Sizing(width=46.0, height=52.0),
        children=[
            CleanDesignTreeNode(
                id="wifi",
                name="Wifi",
                type=NodeType.STACK,
                sizing=Sizing(width=16.0, height=16.0),
                children=[],
            ),
            CleanDesignTreeNode(
                id="battery",
                name="Battery",
                type=NodeType.ROW,
                sizing=Sizing(width=16.0, height=16.0),
                children=[],
            ),
        ],
    )
    wrapped = bind_row_cross_axis_height(icons, "Row(children: [])")
    assert "height: 52.0" not in wrapped
    assert "16.0" in wrapped


def test_bundled_secondary_font_family_emits_inline() -> None:
    node = CleanDesignTreeNode(
        id="price",
        name="39,99$",
        type=NodeType.TEXT,
        text="39,99$",
        style=NodeStyle(
            font_family="Nekst",
            font_size=20.0,
            font_weight="w400",
            text_color="0xFF000000",
        ),
    )
    expr = text_style_expr(
        node,
        bundled_font_families=frozenset({"SF Pro Text", "Nekst"}),
    )
    assert "fontFamily: 'Nekst'" in expr


def test_pruned_cluster_inherits_vector_from_populated_sibling() -> None:
    populated = CleanDesignTreeNode(
        id="radio-full",
        name="check_circle",
        type=NodeType.ROW,
        cluster_id="cluster_0",
        vector_asset_key="assets/icons/vector_check.svg",
        children=[
            CleanDesignTreeNode(
                id="glyph",
                name="Vector",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/vector_check.svg",
            )
        ],
    )
    pruned = CleanDesignTreeNode(
        id="radio-pruned",
        name="check_circle",
        type=NodeType.ROW,
        cluster_id="cluster_0",
        sizing=Sizing(width=24.0, height=24.0),
        children=[],
    )
    root = CleanDesignTreeNode(
        id="root",
        name="Root",
        type=NodeType.ROW,
        children=[populated, pruned],
    )
    resolve_pruned_cluster_instance_assets(root, Path("."))
    assert pruned.vector_asset_key == "assets/icons/vector_check.svg"


def test_pruned_cluster_inherits_vector_from_child_glyph_only() -> None:
    populated = CleanDesignTreeNode(
        id="radio-full",
        name="check_circle",
        type=NodeType.ROW,
        cluster_id="cluster_0",
        children=[
            CleanDesignTreeNode(
                id="glyph",
                name="Vector",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/vector_2399_42811.svg",
            )
        ],
    )
    pruned = CleanDesignTreeNode(
        id="radio-pruned",
        name="check_circle",
        type=NodeType.ROW,
        cluster_id="cluster_0",
        sizing=Sizing(width=24.0, height=24.0),
        children=[],
    )
    root = CleanDesignTreeNode(
        id="root",
        name="Root",
        type=NodeType.ROW,
        children=[populated, pruned],
    )
    resolve_pruned_cluster_instance_assets(root, Path("."))
    assert pruned.vector_asset_key == "assets/icons/vector_2399_42811.svg"


def test_degenerate_raster_stub_not_bound_to_render_boundary(tmp_path: Path) -> None:
    images = tmp_path / "assets" / "images"
    images.mkdir(parents=True)
    stub = images / "portrait.png"
    stub.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
        b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    (images / ".figma-bindings.json").write_text(
        '{"bindings": {"portrait.png": "2399:42780"}}',
        encoding="utf-8",
    )
    assert not raster_asset_export_viable(stub)
    hero = CleanDesignTreeNode(
        id="2399:42779",
        name="Img",
        type=NodeType.STACK,
        render_boundary=True,
        flatten_figma_node_ids=["2399:42780"],
        sizing=Sizing(width=393.0, height=454.0),
    )
    root = CleanDesignTreeNode(id="screen", name="Screen", type=NodeType.STACK, children=[hero])
    unresolved = resolve_render_boundary_asset_keys(root, tmp_path, None, strict=False)
    assert hero.image_asset_key is None
    assert "2399:42779" in unresolved


def test_home_indicator_skips_orientation_portrait_role_raster(tmp_path: Path) -> None:
    """Law: iOS chrome Orientation=Portrait must not bind hero portrait.png."""
    images = tmp_path / "assets" / "images"
    images.mkdir(parents=True)
    _write_minimal_viable_png(images / "portrait.png")
    from figma_flutter_agent.parser.boundaries.assets import discover_role_named_raster

    home_indicator = CleanDesignTreeNode(
        id="2399:42843",
        name="Home Indicator",
        type=NodeType.STACK,
        sizing=Sizing(width=393.0, height=21.0),
        variant=ComponentVariant(
            component_id="111:17496",
            component_name="Home Indicator",
            variant_properties={
                "Device": "iPhone",
                "Orientation": "Portrait",
                "Mode": "Light",
            },
        ),
        children=[],
    )
    assert discover_role_named_raster(tmp_path, home_indicator) is None


def test_promote_render_boundary_flatten_binding(tmp_path: Path) -> None:
    images = tmp_path / "assets" / "images"
    images.mkdir(parents=True)
    _write_minimal_viable_png(images / "portrait.png")
    (images / ".figma-bindings.json").write_text(
        '{"bindings": {"portrait.png": "2399:42780"}}',
        encoding="utf-8",
    )
    hero = CleanDesignTreeNode(
        id="2399:42779",
        name="Img",
        type=NodeType.STACK,
        render_boundary=True,
        flatten_figma_node_ids=["2399:42780"],
        sizing=Sizing(width=393.0, height=454.0),
    )
    root = CleanDesignTreeNode(id="screen", name="Screen", type=NodeType.STACK, children=[hero])
    from figma_flutter_agent.parser.boundaries.assets import (
        promote_render_boundary_flatten_bindings,
        resolve_missing_image_asset_keys,
    )
    from figma_flutter_agent.pipeline.local_assets import local_asset_manifest_from_project

    manifest = local_asset_manifest_from_project(tmp_path, clean_tree=root)
    bindings = {
        entry.node_id: entry.asset_path
        for entry in manifest.entries
        if entry.kind == "image"
    }
    resolve_missing_image_asset_keys(root, tmp_path)
    promote_render_boundary_flatten_bindings(root, tmp_path, bindings)
    assert hero.image_asset_key == "assets/images/portrait.png"


def test_hollow_cluster_vector_shell_inherits_sibling_asset() -> None:
    populated = CleanDesignTreeNode(
        id="radio-full",
        name="check_circle",
        type=NodeType.ROW,
        cluster_id="cluster_0",
        children=[
            CleanDesignTreeNode(
                id="glyph",
                name="Vector",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/vector_2399_42811.svg",
            )
        ],
    )
    hollow = CleanDesignTreeNode(
        id="radio-hollow",
        name="check_circle",
        type=NodeType.ROW,
        cluster_id="cluster_0",
        sizing=Sizing(width=24.0, height=24.0),
        children=[
            CleanDesignTreeNode(
                id="glyph-empty",
                name="Ellipse 697",
                type=NodeType.VECTOR,
                sizing=Sizing(width=24.0, height=24.0),
            )
        ],
    )
    root = CleanDesignTreeNode(
        id="root",
        name="Root",
        type=NodeType.ROW,
        children=[populated, hollow],
    )
    resolve_pruned_cluster_instance_assets(root, Path("."))
    assert hollow.vector_asset_key == "assets/icons/vector_2399_42811.svg"


def test_horizontal_inflow_row_preserves_document_child_order() -> None:
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        stack_flow_column_child_sort_key,
    )

    time_row = CleanDesignTreeNode(
        id="time",
        name="Time",
        type=NodeType.ROW,
        sizing=Sizing(width=128.0, height=40.0),
        stack_placement=StackPlacement(left=16.0, top=0.0, width=128.0, height=40.0),
        children=[],
    )
    icons_row = CleanDesignTreeNode(
        id="icons",
        name="Status Icons",
        type=NodeType.ROW,
        sizing=Sizing(width=46.0, height=52.0),
        stack_placement=StackPlacement(left=200.0, top=0.0, width=46.0, height=52.0),
        children=[],
    )
    # Document order: time before icons; vertical sort key would invert them.
    assert stack_flow_column_child_sort_key(time_row) > stack_flow_column_child_sort_key(
        icons_row
    )


def test_collapse_nested_positioned_fill_removes_competing_parent_data() -> None:
    from figma_flutter_agent.generator.layout.flex_policy.wrap import (
        collapse_nested_positioned_fill,
    )

    nested = (
        "Positioned(left: 1.3, width: 13.3, bottom: 1.3, height: 13.3, "
        "child: Positioned.fill(child: SvgPicture.asset('wifi.svg')))"
    )
    collapsed = collapse_nested_positioned_fill(nested)
    assert "Positioned.fill(" not in collapsed
    assert "SvgPicture.asset('wifi.svg')" in collapsed


def test_bounded_negative_gap_row_uses_stack_not_transform() -> None:
    from figma_flutter_agent.generator.layout.widgets.flex_sizing import flex_children_body

    wifi = CleanDesignTreeNode(
        id="wifi",
        name="Wifi",
        type=NodeType.STACK,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=16.0, height=16.0),
        children=[],
    )
    signal = CleanDesignTreeNode(
        id="signal",
        name="Signal",
        type=NodeType.STACK,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=16.0, height=16.0),
        children=[],
    )
    row = CleanDesignTreeNode(
        id="wifi-row",
        name="Wi-Fi Network",
        type=NodeType.ROW,
        spacing=-2.0,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=30.0, height=16.0),
        children=[wifi, signal],
    )
    body = flex_children_body(
        row,
        ["SizedBox(width: 16.0)", "SizedBox(width: 16.0)"],
        axis="horizontal",
    )
    assert "Transform.translate" not in body
    assert "Stack(" in body
    assert "width: 30.0" in body


    button = CleanDesignTreeNode(
        id="cta",
        name="Button",
        type=NodeType.BUTTON,
        sizing=Sizing(width=328.0, height=56.0),
        padding=Padding(top=14.0, bottom=14.0, left=20.0, right=20.0),
        style=NodeStyle(background_color="0xFF8459C9", border_radius=20.0),
        children=[
            CleanDesignTreeNode(
                id="labels",
                name=" ",
                type=NodeType.COLUMN,
                sizing=Sizing(width=241.0, height=34.0, height_mode=SizingMode.FIXED),
                children=[
                    CleanDesignTreeNode(
                        id="title",
                        name="Text",
                        type=NodeType.TEXT,
                        text="Subscribe",
                        style=NodeStyle(font_size=16.0, line_height=1.19),
                    ),
                    CleanDesignTreeNode(
                        id="subtitle",
                        name="Sub",
                        type=NodeType.TEXT,
                        text="7 days free",
                        style=NodeStyle(font_size=13.0, line_height=1.15),
                    ),
                ],
            )
        ],
    )
    assert button_is_pill_with_label_column(button)
    inset = _symmetric_pill_button_padding(button)
    assert inset is not None
    assert "vertical: 14.0" not in inset
    assert "11.0" in inset
