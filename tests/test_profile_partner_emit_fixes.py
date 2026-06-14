"""Regression guards for profile-style metric pills, chips, nav, and icon rails."""

from pathlib import Path

from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.generator.layout.flex_policy import (
    button_hosts_status_pill,
    column_center_hug_child_wrap,
    horizontal_chip_button_should_hug_width,
)
from figma_flutter_agent.generator.layout.navigation.helpers import (
    bottom_nav_stateful_helpers,
    pill_nav_stateful_helpers,
)
from figma_flutter_agent.generator.layout.navigation.host import (
    bottom_nav_has_figma_chrome,
    compose_bottom_navigation_host,
)
from figma_flutter_agent.generator.layout.stack_chrome import is_bottom_docked_stack_child
from figma_flutter_agent.generator.layout.style import border_radius_expr
from figma_flutter_agent.generator.layout.widgets import render_node_body
from figma_flutter_agent.generator.renderer_theme import resolve_theme_font_family
from figma_flutter_agent.generator.subtree.plan import _bottom_nav_widget_needs_refresh
from figma_flutter_agent.parser.boundaries.assets import resolve_missing_image_asset_keys
from figma_flutter_agent.parser.interaction import list_tile_leading_icon_slot
from figma_flutter_agent.schemas import (
    Alignment,
    CleanDesignTreeNode,
    LayoutBackend,
    LayoutSlotIr,
    NodeStyle,
    NodeType,
    Sizing,
    SizingMode,
    StackPlacement,
    TextMetricsFrame,
    WrapKind,
)


def test_resolve_theme_font_family_prefers_branded_font_over_roboto() -> None:
    assert resolve_theme_font_family(["Golos Text", "Roboto"]) == "Golos Text"


def test_border_radius_expr_clamps_figma_pill_tokens() -> None:
    style = NodeStyle(border_radius=35_791_400.0)
    expr = border_radius_expr(style, frame_height=38.0)
    assert "19.0" in expr
    assert "35791400" not in expr


def test_centered_metric_label_uses_full_column_width() -> None:
    parent = CleanDesignTreeNode(
        id="1:col",
        name="Column",
        type=NodeType.COLUMN,
        sizing=Sizing(width_mode=SizingMode.FILL, width=100.0),
        alignment=Alignment(cross="center"),
    )
    child = CleanDesignTreeNode(
        id="1:label",
        name="Label",
        type=NodeType.COLUMN,
        sizing=Sizing(width=40.0, height=20.0),
        children=[
            CleanDesignTreeNode(
                id="1:text",
                name="Metric",
                type=NodeType.TEXT,
                text="Скидка",
                style=NodeStyle(text_align="CENTER", font_size=12.0),
            )
        ],
    )
    wrapped = column_center_hug_child_wrap(
        parent,
        child,
        "Text('Скидка', textAlign: TextAlign.center)",
    )
    assert "width: double.infinity" in wrapped
    assert "width: 40.0" not in wrapped


def test_bottom_nav_helpers_keep_bar_when_height_is_bounded() -> None:
    helpers = bottom_nav_stateful_helpers(node_id="1:nav")
    assert "constraints.maxHeight > 120.0" in helpers


def test_profile_header_row_does_not_trigger_list_tile_icon_slot() -> None:
    avatar = CleanDesignTreeNode(
        id="1:avatar",
        name="Avatar",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=64.0, height=64.0),
        style=NodeStyle(background_color="0xFFEEF9F0", border_radius=24.0),
        children=[
            CleanDesignTreeNode(
                id="1:initial",
                name="Initial",
                type=NodeType.TEXT,
                text="И",
                style=NodeStyle(text_align="CENTER", font_weight="w700"),
            )
        ],
    )
    header_row = CleanDesignTreeNode(
        id="1:row",
        name="Row",
        type=NodeType.ROW,
        children=[
            avatar,
            CleanDesignTreeNode(
                id="1:text",
                name="Copy",
                type=NodeType.COLUMN,
                sizing=Sizing(width_mode=SizingMode.FILL, width=200.0),
                children=[
                    CleanDesignTreeNode(
                        id="1:title",
                        name="Title",
                        type=NodeType.TEXT,
                        text="Иван Иванов",
                    )
                ],
            ),
        ],
    )
    assert not list_tile_leading_icon_slot(
        avatar, header_row, parent_type=NodeType.ROW
    )
    body = render_node_body(avatar, uses_svg=False, parent_type=NodeType.ROW)
    assert "Icons.circle_outlined" not in body
    assert "Text('И'" in body


def test_list_tile_leading_icon_slot_detects_first_row_child() -> None:
    icon = CleanDesignTreeNode(
        id="1:icon",
        name="Background",
        type=NodeType.ROW,
        sizing=Sizing(width=48.0, height=48.0),
    )
    row = CleanDesignTreeNode(
        id="1:row",
        name="Row",
        type=NodeType.ROW,
        children=[
            icon,
            CleanDesignTreeNode(
                id="1:text",
                name="Copy",
                type=NodeType.COLUMN,
                sizing=Sizing(width_mode=SizingMode.FILL, width=200.0),
                children=[
                    CleanDesignTreeNode(
                        id="1:title",
                        name="Title",
                        type=NodeType.TEXT,
                        text="Чаты",
                    ),
                    CleanDesignTreeNode(
                        id="1:sub",
                        name="Subtitle",
                        type=NodeType.TEXT,
                        text="Поддержка",
                    ),
                ],
            ),
            CleanDesignTreeNode(
                id="1:chev",
                name="Chevron",
                type=NodeType.STACK,
                sizing=Sizing(width=20.0, height=20.0),
            ),
        ],
    )
    assert list_tile_leading_icon_slot(icon, row, parent_type=NodeType.ROW)


def test_list_tile_leading_icon_slot_rejects_icon_stepper_row() -> None:
    from figma_flutter_agent.parser.interaction import looks_like_compact_icon_action_button

    minus = CleanDesignTreeNode(
        id="1:minus",
        name="Button",
        type=NodeType.BUTTON,
        sizing=Sizing(width=40.0, height=40.0),
        children=[
            CleanDesignTreeNode(
                id="1:vec",
                name="Vector",
                type=NodeType.VECTOR,
                sizing=Sizing(width=10.0, height=1.0),
                style=NodeStyle(has_stroke=True),
            )
        ],
    )
    plus = CleanDesignTreeNode(
        id="1:plus",
        name="Button",
        type=NodeType.BUTTON,
        sizing=Sizing(width=40.0, height=40.0),
        children=[
            CleanDesignTreeNode(
                id="1:v1",
                name="Vector",
                type=NodeType.VECTOR,
                sizing=Sizing(width=10.0, height=1.0),
                style=NodeStyle(has_stroke=True),
            ),
            CleanDesignTreeNode(
                id="1:v2",
                name="Vector",
                type=NodeType.VECTOR,
                sizing=Sizing(width=1.0, height=10.0),
                style=NodeStyle(has_stroke=True),
            ),
        ],
    )
    assert looks_like_compact_icon_action_button(minus)
    assert looks_like_compact_icon_action_button(plus)
    row = CleanDesignTreeNode(
        id="1:row",
        name="Stepper",
        type=NodeType.ROW,
        children=[
            minus,
            CleanDesignTreeNode(
                id="1:price",
                name="Price",
                type=NodeType.TEXT,
                text="86 ₽",
                sizing=Sizing(width_mode=SizingMode.FILL, width=120.0),
            ),
            plus,
        ],
    )
    assert not list_tile_leading_icon_slot(minus, row, parent_type=NodeType.ROW)


def test_pill_label_row_hugs_text_width() -> None:
    pill = CleanDesignTreeNode(
        id="1:pill",
        name="Badge",
        type=NodeType.ROW,
        padding={"left": 12.0, "right": 12.0, "top": 4.0, "bottom": 4.0},
        sizing=Sizing(width=168.0, height=25.0),
        style=NodeStyle(background_color="0xFFEEF9F0", border_radius=99.0),
        children=[
            CleanDesignTreeNode(
                id="1:label",
                name="Label",
                type=NodeType.TEXT,
                text="Личный кабинет партнера",
                style=NodeStyle(
                    text_color="0xFF2E7D32",
                    font_size=12.0,
                    font_weight="w600",
                ),
            )
        ],
    )
    body = render_node_body(pill, uses_svg=False, parent_type=NodeType.COLUMN)
    compact = body.replace("\n", "")
    assert "mainAxisSize: MainAxisSize.min" in compact
    assert "width: 168.0" not in compact


def test_list_tile_leading_without_asset_falls_back_to_material_icon() -> None:
    text_col = CleanDesignTreeNode(
        id="1:text",
        name="Copy",
        type=NodeType.COLUMN,
        sizing=Sizing(width_mode=SizingMode.FILL, width=200.0),
        children=[
            CleanDesignTreeNode(
                id="1:title",
                name="Title",
                type=NodeType.TEXT,
                text="Чаты",
            ),
            CleanDesignTreeNode(
                id="1:sub",
                name="Subtitle",
                type=NodeType.TEXT,
                text="Поддержка",
            ),
        ],
    )
    icon = CleanDesignTreeNode(
        id="1:icon",
        name="Background",
        type=NodeType.ROW,
        cluster_id="cluster-bg",
        sizing=Sizing(width=48.0, height=48.0),
    )
    button = CleanDesignTreeNode(
        id="1:btn",
        name="Button",
        type=NodeType.BUTTON,
        spacing=12.0,
        sizing=Sizing(width_mode=SizingMode.FILL, width=329.0, height=80.0),
        children=[
            icon,
            text_col,
            CleanDesignTreeNode(
                id="1:chev",
                name="Chevron",
                type=NodeType.STACK,
                sizing=Sizing(width=20.0, height=20.0),
            ),
        ],
    )
    body = render_node_body(
        icon,
        uses_svg=True,
        parent_type=NodeType.BUTTON,
        parent_node=button,
        cluster_classes={"cluster-bg": "BackgroundWidget"},
    )
    assert "BackgroundWidget" not in body
    assert "Icons.chat_bubble_outline" in body


def test_horizontal_chip_button_hugs_label_width() -> None:
    chip = CleanDesignTreeNode(
        id="1:chip",
        name="Button",
        type=NodeType.BUTTON,
        sizing=Sizing(width=52.0, height=38.0),
        style=NodeStyle(background_color="0xFFEEF9F0", border_radius=99.0),
        children=[
            CleanDesignTreeNode(
                id="1:label",
                name="Label",
                type=NodeType.TEXT,
                text="Телефон",
                style=NodeStyle(font_size=12.0, font_weight="w600", text_align="CENTER"),
            )
        ],
    )
    assert horizontal_chip_button_should_hug_width(chip)
    body = render_node_body(chip, uses_svg=False, parent_type=NodeType.WRAP)
    compact = body.replace("\n", "")
    assert "width: 52.0" not in compact
    assert "IntrinsicWidth" in compact
    assert "StackFit.loose" in compact
    assert "Телефон" in body


def test_status_pill_button_hugs_and_centers_in_column() -> None:
    pill_row = CleanDesignTreeNode(
        id="1:pill",
        name="Background",
        type=NodeType.ROW,
        padding={"left": 12.0, "right": 12.0, "top": 4.0, "bottom": 4.0},
        sizing=Sizing(width=168.0, height=25.0),
        style=NodeStyle(background_color="0xFFEEF9F0", border_radius=99.0),
        children=[
            CleanDesignTreeNode(
                id="1:label",
                name="Label",
                type=NodeType.TEXT,
                text="Личный кабинет партнера",
                style=NodeStyle(
                    text_color="0xFF2E7D32",
                    font_size=12.0,
                    font_weight="w600",
                ),
            )
        ],
    )
    button = CleanDesignTreeNode(
        id="1:btn",
        name="Button",
        type=NodeType.BUTTON,
        sizing=Sizing(width_mode=SizingMode.FILL, width=237.0, height=25.0),
        children=[pill_row],
    )
    assert button_hosts_status_pill(button)
    body = render_node_body(button, uses_svg=False, parent_type=NodeType.COLUMN)
    compact = body.replace("\n", "")
    assert "width: double.infinity" not in compact
    assert "IntrinsicWidth" in compact
    assert "Align(alignment: Alignment.center" in compact
    assert "mainAxisSize: MainAxisSize.min" in compact


def test_prefilled_date_input_renders_editable_text_field() -> None:
    from figma_flutter_agent.parser.interaction import input_hint_node

    value = CleanDesignTreeNode(
        id="1:value",
        name="Value",
        type=NodeType.TEXT,
        text="14.06.1995",
        style=NodeStyle(font_size=14.0, font_weight="w400"),
    )
    calendar = CleanDesignTreeNode(
        id="1:cal",
        name="Calendar",
        type=NodeType.BUTTON,
        sizing=Sizing(width=20.0, height=20.0),
        children=[
            CleanDesignTreeNode(
                id="1:icon",
                name="Icon",
                type=NodeType.VECTOR,
                sizing=Sizing(width=16.0, height=16.0),
                style=NodeStyle(has_stroke=True),
            )
        ],
    )
    input_node = CleanDesignTreeNode(
        id="1:input",
        name="Input",
        type=NodeType.INPUT,
        sizing=Sizing(width=237.0, height=52.0),
        style=NodeStyle(background_color="0xFFF6F6F2", border_radius=20.0),
        children=[value, calendar],
    )
    assert input_hint_node(input_node) is None or value.text
    body = render_node_body(input_node, uses_svg=False, parent_type=NodeType.COLUMN)
    compact = body.replace("\n", "")
    assert "TextFormField(" in compact
    assert "14.06.1995" in compact
    assert "textAlignVertical:" not in compact
    assert "isDense:" not in compact
    assert "contentPadding: EdgeInsets.fromLTRB(" in compact
    assert ", 19.0," in compact.split("contentPadding:")[1].split("border:")[0]
    assert "MainAxisAlignment.spaceBetween" not in compact


def test_bottom_nav_figma_chrome_detects_styled_bar() -> None:
    node = CleanDesignTreeNode(
        id="1:nav",
        name="BottomNavBar",
        type=NodeType.BOTTOM_NAV,
        style=NodeStyle(
            background_color="0xFFFFFFFF",
            border_radius_corners={
                "topLeft": 32.0,
                "topRight": 32.0,
                "bottomLeft": 0.0,
                "bottomRight": 0.0,
            },
            background_blur=20.0,
        ),
        children=[
            CleanDesignTreeNode(
                id="1:row",
                name="Container",
                type=NodeType.ROW,
                sizing=Sizing(width_mode=SizingMode.FILL, width=390.0, height=81.0),
            )
        ],
    )
    assert bottom_nav_has_figma_chrome(node)


def _compact_nav_tab(label: str, *, active: bool = False) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=f"1:{label}",
        name="Link",
        type=NodeType.COLUMN,
        padding={"top": 6.0, "bottom": 6.0, "left": 16.0, "right": 16.0},
        sizing=Sizing(width=80.0, height=49.0),
        style=NodeStyle(
            background_color="0xFFDCFCE7" if active else None,
            border_radius=10.0 if active else None,
        ),
        children=[
            CleanDesignTreeNode(
                id=f"1:{label}-text",
                name="Label",
                type=NodeType.TEXT,
                text=label,
                style=NodeStyle(
                    font_size=12.0,
                    text_color="0xFF166534" if active else "0xFF64748B",
                ),
            )
        ],
    )


def test_pill_bottom_nav_uses_background_highlight_and_profile_index() -> None:
    nav = CleanDesignTreeNode(
        id="1:nav",
        name="BottomNavBar",
        type=NodeType.BOTTOM_NAV,
        style=NodeStyle(
            background_color="0xFFFFFFFF",
            border_radius_corners={
                "topLeft": 32.0,
                "topRight": 32.0,
                "bottomLeft": 0.0,
                "bottomRight": 0.0,
            },
            background_blur=20.0,
        ),
        children=[
            CleanDesignTreeNode(
                id="1:row",
                name="Container",
                type=NodeType.ROW,
                sizing=Sizing(width_mode=SizingMode.FILL, width=390.0, height=81.0),
                children=[
                    _compact_nav_tab("Главная"),
                    _compact_nav_tab("Каталог"),
                    _compact_nav_tab("Корзина"),
                    _compact_nav_tab("Профиль", active=True),
                ],
            )
        ],
    )
    body = compose_bottom_navigation_host(nav, uses_svg=True)
    compact = body.replace("\n", "")
    assert "_LayoutPillNav(" in compact
    assert "initialIndex: 3" in compact
    assert "activeBackground: Color(0xFFDCFCE7)" in compact
    assert "activeForeground: Color(0xFF166534)" in compact
    assert "inactiveForeground: Color(0xFF64748B)" in compact
    assert "BottomNavigationBar(" not in compact
    assert "BackdropFilter(" in compact
    assert ".withOpacity(0.72)" in compact
    assert "decoration: BoxDecoration(color: Color(0xFFFFFFFF)), child:" not in compact


def test_pill_nav_helpers_emit_gesture_tabs_with_color_filter() -> None:
    helpers = pill_nav_stateful_helpers(node_id="1:nav")
    assert "class _LayoutPillNav extends StatefulWidget" in helpers
    assert "MainAxisAlignment.spaceAround" in helpers
    assert "ColorFilter.mode" in helpers
    assert "widget.activeBackground" in helpers


def test_single_item_bottom_chrome_does_not_emit_material_nav() -> None:
    chrome = CleanDesignTreeNode(
        id="1:chrome",
        name="System / TabBar / Display Down",
        type=NodeType.BOTTOM_NAV,
        sizing=Sizing(width=375.0, height=34.0),
        children=[
            CleanDesignTreeNode(
                id="1:handle",
                name="Rectangle 24",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=134.0, height=5.0),
                stack_placement=StackPlacement(left=120.5, top=20.0),
                style=NodeStyle(background_color="0xFFCACACA", border_radius=100.0),
            )
        ],
    )
    body = compose_bottom_navigation_host(chrome, uses_svg=True)
    compact = body.replace("\n", "")
    assert "BottomNavigationBar(" not in compact
    assert "_LayoutChromeNav(" not in compact
    assert "IgnorePointer(ignoring: true" in compact
    assert "Rectangle 24" not in compact
    assert "width: 134.0" in compact


def test_bottom_nav_helper_guards_single_item_runtime_assertion() -> None:
    helpers = bottom_nav_stateful_helpers(node_id="1:nav")
    assert "if (widget.items.length < 2)" in helpers
    assert "return const SizedBox.shrink();" in helpers


def test_nav_icon_prefers_extracted_figma_asset_over_generic_home_svg() -> None:
    from figma_flutter_agent.generator.layout.navigation.items import nav_icon_expr

    tab = CleanDesignTreeNode(
        id="1:home",
        name="Home",
        type=NodeType.COLUMN,
        children=[
            CleanDesignTreeNode(
                id="1:icon",
                name="Home icon",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/group_I104_3018;28_19368;188_23151.svg",
            ),
            CleanDesignTreeNode(
                id="1:label",
                name="Label",
                type=NodeType.TEXT,
                text="Home",
            ),
        ],
    )
    expr = nav_icon_expr(tab, uses_svg=True)
    assert "group_I104_3018;28_19368;188_23151.svg" in expr
    assert "assets/icons/home.svg" not in expr


def test_material_bottom_nav_in_figma_chrome_widget_is_stale() -> None:
    stale = (
        "ClipRRect(child: BackdropFilter(child: Container(child: "
        "_LayoutChromeNav(initialIndex: 0, items: [BottomNavigationBarItem("
        "icon: Icon(Icons.home_outlined), label: 'Home')]))))"
    )
    assert _bottom_nav_widget_needs_refresh(stale)


def test_absolute_composite_card_emits_overlay_stack_not_column() -> None:
    card = CleanDesignTreeNode(
        id="1:card",
        name="Card Bank / Multi",
        type=NodeType.CARD,
        sizing=Sizing(width=327.0, height=221.0),
        children=[
            CleanDesignTreeNode(
                id="1:shadow",
                name="Shadow plate",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=261.0, height=164.0),
                stack_placement=StackPlacement(left=16.0, top=40.0),
                style=NodeStyle(background_color="0xFF5655B9"),
            ),
            CleanDesignTreeNode(
                id="1:bg",
                name="Pink plate",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=287.0, height=178.0),
                stack_placement=StackPlacement(left=24.0, top=27.0),
                style=NodeStyle(background_color="0xFFFF4267"),
            ),
            CleanDesignTreeNode(
                id="1:face",
                name="Card face",
                type=NodeType.STACK,
                sizing=Sizing(width=327.0, height=204.0),
                stack_placement=StackPlacement(left=0.0, top=0.0),
                vector_asset_key="assets/illustrations/card_face.svg",
                render_boundary=True,
            ),
        ],
    )
    body = render_node_body(card, uses_svg=True, parent_type=NodeType.STACK)
    compact = body.replace("\n", "")
    assert "SizedBox(width: 327.0, height: 221.0, child: Stack(" in compact
    assert "Positioned(left: 16.0, top: 40.0" in compact
    assert "Positioned(left: 24.0, top: 27.0" in compact
    assert "child: Column(" not in compact


def test_avatar_stack_with_image_fill_renders_raster() -> None:
    avatar = CleanDesignTreeNode(
        id="1",
        name="Avatar",
        type=NodeType.STACK,
        sizing=Sizing(width=50.0, height=50.0),
        vector_asset_key="assets/icons/avatar.svg",
        render_boundary=True,
        children=[
            CleanDesignTreeNode(
                id="2",
                name="mask",
                type=NodeType.VECTOR,
                sizing=Sizing(width=50.0, height=50.0),
            ),
            CleanDesignTreeNode(
                id="3",
                name="photo",
                type=NodeType.IMAGE,
                sizing=Sizing(width=50.0, height=50.0),
                image_asset_key="assets/images/avatar_photo.png",
            ),
        ],
    )
    body = render_node_body(avatar, uses_svg=True)
    assert "Image.asset('assets/images/avatar_photo.png'" in body.replace(" ", "")
    assert "SvgPicture.asset('assets/icons/avatar.svg'" not in body.replace(" ", "")


def test_avatar_stack_hydrates_image_fill_from_disk(tmp_path: Path) -> None:
    images = tmp_path / "assets" / "images"
    images.mkdir(parents=True)
    (images / "avatar_3.png").write_bytes(b"png")
    photo = CleanDesignTreeNode(
        id="3",
        name="photo",
        type=NodeType.IMAGE,
        sizing=Sizing(width=50.0, height=50.0),
    )
    avatar = CleanDesignTreeNode(
        id="169:21534",
        name="Avatar",
        type=NodeType.STACK,
        sizing=Sizing(width=50.0, height=50.0),
        vector_asset_key="assets/icons/avatar.svg",
        render_boundary=True,
        children=[
            CleanDesignTreeNode(
                id="2",
                name="mask",
                type=NodeType.VECTOR,
                sizing=Sizing(width=50.0, height=50.0),
            ),
            photo,
        ],
    )
    resolve_missing_image_asset_keys(avatar, tmp_path)
    body = render_node_body(avatar, uses_svg=True)
    assert photo.image_asset_key == "assets/images/avatar_3.png"
    assert "Image.asset('assets/images/avatar_3.png'" in body.replace(" ", "")


def test_avatar_image_key_resolves_from_parent_stack_id(tmp_path: Path) -> None:
    images = tmp_path / "assets" / "images"
    images.mkdir(parents=True)
    (images / "avatar_169_21534.png").write_bytes(b"png")
    photo = CleanDesignTreeNode(
        id="I169:21534;150:2",
        name="Ellipse 15",
        type=NodeType.IMAGE,
        sizing=Sizing(width=50.0, height=50.0),
    )
    avatar = CleanDesignTreeNode(
        id="169:21534",
        name="Avatar",
        type=NodeType.STACK,
        sizing=Sizing(width=50.0, height=50.0),
        vector_asset_key="assets/icons/avatar_169_21534.svg",
        children=[photo],
    )
    resolve_missing_image_asset_keys(avatar, tmp_path)
    assert photo.image_asset_key == "assets/images/avatar_169_21534.png"


def test_svg_filter_with_png_fallback_emits_image() -> None:
    from figma_flutter_agent.generator.layout.widgets.svg import _render_exported_vector

    node = CleanDesignTreeNode(
        id="1",
        name="Card art",
        type=NodeType.STACK,
        sizing=Sizing(width=327.0, height=204.0),
        vector_asset_key="assets/illustrations/card_face.svg",
        image_asset_key="assets/illustrations/card_face.png",
        vector_svg_has_filter=True,
        render_boundary=True,
    )
    exported = _render_exported_vector(node, uses_svg=True)
    assert exported is not None
    assert "Image.asset" in exported
    assert "SvgPicture.asset" not in exported


def test_numeric_counter_badge_centers_label() -> None:
    badge = CleanDesignTreeNode(
        id="1",
        name="Badge",
        type=NodeType.ROW,
        sizing=Sizing(width=26.0, height=28.0),
        style=NodeStyle(background_color="0xFFFF4267", border_radius=14.0),
        children=[
            CleanDesignTreeNode(
                id="2",
                name="Count",
                type=NodeType.TEXT,
                text="3",
                style=NodeStyle(font_size=12.0),
            )
        ],
    )
    body = render_node_body(badge, uses_svg=False)
    assert "Center(" in body or "MainAxisAlignment.center" in body


def test_notification_badge_stack_emits_positioned_overlay() -> None:
    host = CleanDesignTreeNode(
        id="1",
        name="Bell",
        type=NodeType.STACK,
        sizing=Sizing(width=40.0, height=40.0),
        vector_asset_key="assets/icons/bell.svg",
        children=[
            CleanDesignTreeNode(
                id="2",
                name="Icon",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/bell.svg",
                sizing=Sizing(width=24.0, height=24.0),
            ),
            CleanDesignTreeNode(
                id="3",
                name="Badge",
                type=NodeType.ROW,
                layout_positioning="ABSOLUTE",
                stack_placement=StackPlacement(right=0.0, top=0.0, width=18.0, height=18.0),
                sizing=Sizing(width=18.0, height=18.0),
                style=NodeStyle(background_color="0xFFFF4267", border_radius=9.0),
                children=[
                    CleanDesignTreeNode(
                        id="4",
                        name="Count",
                        type=NodeType.TEXT,
                        text="3",
                        style=NodeStyle(font_size=10.0),
                    )
                ],
            ),
        ],
    )
    body = render_node_body(host, uses_svg=True)
    assert "Stack(" in body
    assert "Positioned.fill" in body or body.count("Positioned(") >= 2
    assert "SvgPicture.asset('assets/icons/bell.svg'" in body
    assert "Text('3'" in body
    assert "forceStrutHeight" not in body


def test_numeric_glyph_overlay_badge_omits_forced_strut() -> None:
    badge_stack = CleanDesignTreeNode(
        id="badge",
        name="BadgeOverlay",
        type=NodeType.STACK,
        sizing=Sizing(width=16.0, height=18.0),
        children=[
            CleanDesignTreeNode(
                id="oval",
                name="Oval",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/oval.svg",
                sizing=Sizing(width=16.0, height=16.0),
                stack_placement=StackPlacement(left=0.0, bottom=2.0, width=16.0, height=16.0),
            ),
            CleanDesignTreeNode(
                id="count",
                name="Count",
                type=NodeType.TEXT,
                text="3",
                style=NodeStyle(font_size=10.0, line_height=1.7),
                sizing=Sizing(width=6.0, height=17.0),
                stack_placement=StackPlacement(left=5.0, top=3.0, width=6.0, height=17.0),
            ),
        ],
    )
    body = render_node_body(badge_stack, uses_svg=True)
    assert "Text('3'" in body
    assert "forceStrutHeight" not in body
    assert "StrutStyle(height: 1.7" not in body
    assert "textHeightBehavior" in body


def test_nav_icon_without_verified_asset_uses_material_icon() -> None:
    from figma_flutter_agent.generator.layout.navigation.items import nav_icon_expr

    tab = CleanDesignTreeNode(
        id="1",
        name="Home",
        type=NodeType.COLUMN,
        children=[
            CleanDesignTreeNode(
                id="2",
                name="Label",
                type=NodeType.TEXT,
                text="Home",
            ),
        ],
    )
    expr = nav_icon_expr(tab, uses_svg=True, project_dir=None)
    assert "Icons.home_outlined" in expr
    assert "home.svg" not in expr


def test_avatar_stack_prefers_raster_photo_over_root_vector_export() -> None:
    avatar = CleanDesignTreeNode(
        id="avatar",
        name="Avatar",
        type=NodeType.STACK,
        sizing=Sizing(width=50.0, height=50.0),
        vector_asset_key="assets/icons/avatar.svg",
        children=[
            CleanDesignTreeNode(
                id="ring",
                name="Ellipse 35",
                type=NodeType.VECTOR,
                sizing=Sizing(width=50.0, height=50.0),
            ),
            CleanDesignTreeNode(
                id="photo",
                name="Ellipse 15",
                type=NodeType.IMAGE,
                sizing=Sizing(width=50.0, height=50.0),
                image_asset_key="assets/images/avatar_photo.png",
            ),
        ],
    )
    body = render_node_body(avatar, uses_svg=True)
    assert "Image.asset('assets/images/avatar_photo.png'" in body
    assert "width: 50.0" in body
    assert "height: 50.0" in body
    assert body.count("SvgPicture.asset('assets/icons/avatar.svg'") == 0


def test_avatar_stack_with_image_fill_without_key_uses_host_vector() -> None:
    avatar = CleanDesignTreeNode(
        id="1",
        name="Avatar",
        type=NodeType.STACK,
        sizing=Sizing(width=50.0, height=50.0),
        vector_asset_key="assets/icons/avatar_ring.svg",
        children=[
            CleanDesignTreeNode(
                id="2",
                name="Ellipse 35",
                type=NodeType.VECTOR,
                sizing=Sizing(width=50.0, height=50.0),
            ),
            CleanDesignTreeNode(
                id="3",
                name="Ellipse 15",
                type=NodeType.IMAGE,
                sizing=Sizing(width=50.0, height=50.0),
            ),
        ],
    )
    body = render_node_body(avatar, uses_svg=True)
    assert "ClipOval" in body
    assert "assets/icons/avatar_ring.svg" in body
    assert "SizedBox.shrink()" not in body
    assert "Text('15'" not in body


def test_pruned_avatar_cluster_emits_raster_not_skip_numeral() -> None:
    from figma_flutter_agent.parser.dedup.prune import prune_duplicated_cluster_subtrees

    first = CleanDesignTreeNode(
        id="1",
        name="Avatar",
        type=NodeType.STACK,
        cluster_id="cluster_avatar",
        sizing=Sizing(width=50.0, height=50.0),
        vector_asset_key="assets/icons/avatar_ring.svg",
        children=[
            CleanDesignTreeNode(
                id="2",
                name="Photo",
                type=NodeType.IMAGE,
                sizing=Sizing(width=50.0, height=50.0),
                image_asset_key="assets/images/avatar_photo.png",
            ),
        ],
    )
    duplicate = CleanDesignTreeNode(
        id="3",
        name="Avatar",
        type=NodeType.STACK,
        cluster_id="cluster_avatar",
        sizing=Sizing(width=50.0, height=50.0),
        children=[
            CleanDesignTreeNode(
                id="4",
                name="Photo",
                type=NodeType.IMAGE,
                sizing=Sizing(width=50.0, height=50.0),
                image_asset_key="assets/images/avatar_photo.png",
            ),
        ],
    )
    root = CleanDesignTreeNode(
        id="root",
        name="Header",
        type=NodeType.STACK,
        children=[first, duplicate],
    )
    prune_duplicated_cluster_subtrees(root)
    assert duplicate.children == []
    assert duplicate.image_asset_key == "assets/images/avatar_photo.png"
    body = render_node_body(duplicate, uses_svg=True)
    assert "Image.asset('assets/images/avatar_photo.png'" in body.replace(" ", "")
    assert "Text('15'" not in body
    assert "CircleBorder" not in body


def test_compact_nav_tab_wraps_with_fitted_box() -> None:
    from figma_flutter_agent.generator.layout.navigation.items import (
        column_is_compact_nav_tab,
    )

    tab = CleanDesignTreeNode(
        id="1:tab",
        name="Link",
        type=NodeType.COLUMN,
        padding={"top": 6.0, "bottom": 6.0, "left": 16.0, "right": 16.0},
        sizing=Sizing(width=80.0, height=49.0),
        children=[
            CleanDesignTreeNode(
                id="1:label",
                name="Label",
                type=NodeType.TEXT,
                text="Профиль",
                style=NodeStyle(font_size=12.0),
            )
        ],
    )
    assert column_is_compact_nav_tab(tab)
    body = render_node_body(tab, uses_svg=False, parent_type=NodeType.ROW)
    assert "FittedBox" in body
    assert "ClipRect" in body


def test_profile_partner_avatar_dump_omits_strut_and_height_pin() -> None:
    """Regression: processed dump avatar must not pin Figma line-box height."""
    import json
    from pathlib import Path

    from figma_flutter_agent.schemas import CleanDesignTreeNode

    dump = Path(
        r"E:/@dev/flutter-demo-project/ataev/.debug/processed/profile_partner_layout.json"
    )
    if not dump.is_file():
        return
    payload = json.loads(dump.read_text(encoding="utf-8"))
    tree = CleanDesignTreeNode.model_validate(payload["cleanTree"])

    def _find(node: CleanDesignTreeNode, node_id: str) -> CleanDesignTreeNode | None:
        if node.id == node_id:
            return node
        for child in node.children:
            found = _find(child, node_id)
            if found is not None:
                return found
        return None

    avatar = _find(tree, "281:13260")
    assert avatar is not None
    body = render_node_body(avatar, uses_svg=False, parent_type=NodeType.ROW)
    assert "strutStyle" not in body
    assert "SizedBox(height: 42.0" not in body


def test_centered_avatar_glyph_skips_delta_top_padding() -> None:
    text = CleanDesignTreeNode(
        id="1:glyph",
        name="И",
        type=NodeType.TEXT,
        text="И",
        style=NodeStyle(
            text_align="CENTER",
            font_size=28.0,
            font_weight="w700",
        ),
        text_metrics_frame=TextMetricsFrame(
            font_size=28.0,
            delta_top=1.5,
            strut_height_ratio=1.5,
        ),
        layout_slot=LayoutSlotIr(
            backend=LayoutBackend.FLEX,
            wraps=(WrapKind.DELTA_TOP_PADDING,),
        ),
    )
    row = CleanDesignTreeNode(
        id="1:avatar",
        name="Background",
        type=NodeType.ROW,
        sizing=Sizing(width=64.0, height=64.0),
        style=NodeStyle(background_color="0xFFEEF9F0", border_radius=24.0),
        children=[text],
    )
    body = render_node_body(row, uses_svg=False, parent_type=NodeType.ROW)
    assert "EdgeInsets.only(top: 1.5)" not in body
    assert "strutStyle" not in body
    assert "Center(child:" in body


def test_bottom_nav_stub_widget_is_marked_stale() -> None:
    stub = (
        "class BottomnavbarWidget extends StatelessWidget {\n"
        "  Widget build(BuildContext context) {\n"
        "    return IgnorePointer(ignoring: true, child: const SizedBox.shrink());\n"
        "  }\n"
        "}\n"
    )
    assert _bottom_nav_widget_needs_refresh(stub)


def test_bottom_nav_figma_chrome_with_duplicate_active_fill_is_stale() -> None:
    stale = (
        "ClipRRect(child: BackdropFilter(child: Row(children: ["
        "Container(width: 80.0, decoration: BoxDecoration(color: Color(0xFFDCFCE7)), "
        "child: FittedBox(alignment: Alignment.centerRight, child: Text('A'))), "
        "Container(width: 80.0, decoration: BoxDecoration(color: Color(0xFFDCFCE7)), "
        "child: Icon(Icons.calendar_today_outlined)), "
        "Container(width: 80.0, child: Icon(Icons.calendar_today_outlined)), "
        "])))"
    )
    assert _bottom_nav_widget_needs_refresh(stale)


def test_equal_metric_cards_row_is_scroll_safe_under_column() -> None:
    card = CleanDesignTreeNode(
        id="1:card",
        name="Background",
        type=NodeType.COLUMN,
        padding={"top": 12.0, "bottom": 12.0, "left": 16.0, "right": 16.0},
        spacing=4.0,
        sizing=Sizing(
            width_mode=SizingMode.FILL,
            height_mode=SizingMode.FILL,
            width=97.7,
            height=71.0,
        ),
        alignment=Alignment(cross="stretch"),
        style=NodeStyle(background_color="0xFFF6F6F2", border_radius=22.0),
        children=[
            CleanDesignTreeNode(
                id="1:value",
                name="15%",
                type=NodeType.TEXT,
                text="15%",
                style=NodeStyle(text_align="CENTER", font_size=16.0, font_weight="w700"),
            ),
            CleanDesignTreeNode(
                id="1:label",
                name="Label",
                type=NodeType.TEXT,
                text="Скидка",
                style=NodeStyle(text_align="CENTER", font_size=12.0),
            ),
        ],
    )
    row = CleanDesignTreeNode(
        id="1:row",
        name="Container",
        type=NodeType.ROW,
        padding={"top": 4.0},
        spacing=12.0,
        sizing=Sizing(width_mode=SizingMode.FILL, width=317.0, height=75.0),
        alignment=Alignment(main="center", cross="stretch"),
        children=[card, card, card],
    )
    body = render_node_body(row, uses_svg=False, parent_type=NodeType.COLUMN)
    assert "CrossAxisAlignment.center" in body
    assert "CrossAxisAlignment.stretch, spacing: 12.0" not in body
    assert "SizedBox(height: 75.0" in body
    assert body.count("Expanded(child:") >= 3


def test_square_icon_rail_svg_clamps_to_glyph_size() -> None:
    vector = CleanDesignTreeNode(
        id="1:vector",
        name="Vector",
        type=NodeType.VECTOR,
        sizing=Sizing(width=48.0, height=48.0),
        vector_asset_key="assets/icons/profile_contact.svg",
    )
    body = render_node_body(vector, uses_svg=True, parent_type=NodeType.ROW)
    assert "width: 20.0" in body
    assert "width: 48.0" not in body.split("SvgPicture.asset")[1][:120]


def test_status_pill_row_hugs_without_fixed_height() -> None:
    pill_row = CleanDesignTreeNode(
        id="1:pill",
        name="Background",
        type=NodeType.ROW,
        padding={"left": 12.0, "right": 12.0, "top": 4.0, "bottom": 4.0},
        sizing=Sizing(width=168.0, height=25.0),
        style=NodeStyle(background_color="0xFFEEF9F0", border_radius=99.0),
        children=[
            CleanDesignTreeNode(
                id="1:label",
                name="Label",
                type=NodeType.TEXT,
                text="Личный кабинет партнера",
                style=NodeStyle(
                    text_color="0xFF2E7D32",
                    font_size=12.0,
                    font_weight="w600",
                ),
            )
        ],
    )
    body = render_node_body(pill_row, uses_svg=False, parent_type=NodeType.COLUMN)
    compact = body.replace("\n", "")
    assert "height: 25.0" not in compact
    assert "mainAxisSize: MainAxisSize.min" in compact
    assert "Flexible(" not in compact


def test_nav_tab_label_is_not_card_metadata_rail() -> None:
    from figma_flutter_agent.generator.layout.flex_policy import (
        column_is_card_metadata_slot,
        text_in_card_metadata_rail,
    )

    label_col = CleanDesignTreeNode(
        id="1:label-col",
        name="Container",
        type=NodeType.COLUMN,
        sizing=Sizing(width=42.0, height=17.0),
        alignment=Alignment(cross="stretch"),
        children=[
            CleanDesignTreeNode(
                id="1:label",
                name="Главная",
                type=NodeType.TEXT,
                text="Главная",
                sizing=Sizing(width=42.0, height=17.0),
                style=NodeStyle(font_size=12.0, font_weight="w500"),
            )
        ],
    )
    assert not column_is_card_metadata_slot(label_col)
    assert not text_in_card_metadata_rail(
        label_col.children[0],
        label_col,
        parent_type=NodeType.COLUMN,
    )


def test_compact_nav_tab_strips_duplicate_active_fill() -> None:
    from figma_flutter_agent.generator.layout.navigation.items import (
        compact_nav_tab_should_paint_background,
    )

    def _tab(label: str, *, active: bool, bg: str | None) -> CleanDesignTreeNode:
        text_color = "0xFF166534" if active else "0xFF64748B"
        style = NodeStyle(border_radius=8.0)
        if bg is not None:
            style.background_color = bg
        return CleanDesignTreeNode(
            id=f"1:{label}",
            name="Link",
            type=NodeType.COLUMN,
            padding={"top": 6.0, "bottom": 6.0, "left": 16.0, "right": 16.0},
            sizing=Sizing(width=80.0, height=49.0),
            alignment=Alignment(main="center", cross="center"),
            style=style,
            children=[
                CleanDesignTreeNode(
                    id=f"1:{label}-text",
                    name=label,
                    type=NodeType.TEXT,
                    text=label,
                    style=NodeStyle(font_size=12.0, text_color=text_color),
                )
            ],
        )

    row = CleanDesignTreeNode(
        id="1:row",
        name="Frame",
        type=NodeType.ROW,
        sizing=Sizing(width=320.0, height=49.0),
        children=[
            _tab("Главная", active=False, bg="0xFFDCFCE7"),
            _tab("Каталог", active=False, bg=None),
            _tab("Профиль", active=True, bg="0xFFDCFCE7"),
        ],
    )
    assert not compact_nav_tab_should_paint_background(row.children[0], parent_row=row)
    assert compact_nav_tab_should_paint_background(row.children[2], parent_row=row)


def test_stack_child_with_bottom_inset_is_not_bottom_chrome() -> None:
    """Figma stretch pins set bottom without docking content as nav chrome."""
    content = CleanDesignTreeNode(
        id="1:content",
        name="Container",
        type=NodeType.COLUMN,
        stack_placement=StackPlacement(
            horizontal="LEFT_RIGHT",
            vertical="TOP",
            top=0.5,
            bottom=93.5,
            width=390.0,
            height=1358.0,
        ),
    )
    nav = CleanDesignTreeNode(
        id="1:nav",
        name="Bottom Nav",
        type=NodeType.BOTTOM_NAV,
        stack_placement=StackPlacement(vertical="BOTTOM", height=81.0),
    )
    assert is_bottom_docked_stack_child(content) is False
    assert is_bottom_docked_stack_child(nav) is True


def test_profile_partner_layout_wraps_content_in_scroll_host() -> None:
    """Regression: tall stack content must scroll under docked bottom navigation."""
    import json
    from pathlib import Path

    dump = Path(
        r"E:/@dev/flutter-demo-project/ataev/.debug/processed/profile_partner_layout.json"
    )
    if not dump.is_file():
        return
    payload = json.loads(dump.read_text(encoding="utf-8"))
    tree = CleanDesignTreeNode.model_validate(payload["cleanTree"])
    layout = render_layout_file(
        tree,
        feature_name="profile_partner",
        uses_svg=True,
        responsive_enabled=True,
    )["lib/generated/profile_partner_layout.dart"]
    assert "Positioned.fill(child: SingleChildScrollView" in layout
    assert "children: [_buildContainer(context), _buildBottomnavbar(context)]" not in layout
