"""Form and input field predicates."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

from .icons import (
    layout_fact_compact_icon_action_button,
    layout_fact_input_trailing_icon_button,
)
from .shared import (
    _INPUT_HINTS,
    _MAX_CONTROL_HEIGHT,
    _MAX_LOCAL_DEPTH,
    _label_matches_action_hint,
    _local_nodes,
)

_PASSWORD_DOT_CHARS = frozenset("•·●∙*·.")
_MAX_CHECKBOX_SIZE = 32.0
_MIN_CHECKBOX_SIZE = 12.0
_MIN_STROKED_GLYPH_CHECKBOX_SIZE = 10.0

_LINK_HINTS = (
    "forgot password",
    "sign up",
    "sign in",
    "log in",
    "register",
    "terms",
    "privacy",
    "learn more",
    "reset password",
    "no thanks",
)

_CONSENT_LABEL_HINTS = (
    "privacy",
    "terms",
    "policy",
    "consent",
    "agree",
    "subscribe",
    "read the",
    "i have read",
    "accept",
)

_INTERACTIVE_INPUT_CHILD_TYPES = frozenset(
    {
        NodeType.INPUT,
        NodeType.BUTTON,
        NodeType.CHECKBOX,
        NodeType.SWITCH,
        NodeType.RADIO,
        NodeType.RADIO_GROUP,
        NodeType.DROPDOWN,
        NodeType.DIALOG,
        NodeType.SLIDER,
    }
)

_PRESENTATIONAL_INPUT_CHILD_TYPES = frozenset(
    {
        NodeType.TEXT,
        NodeType.CONTAINER,
        NodeType.COLUMN,
        NodeType.ROW,
        NodeType.STACK,
        NodeType.IMAGE,
        NodeType.VECTOR,
        NodeType.WRAP,
        NodeType.GRID,
        NodeType.CARD,
    }
)


def layout_fact_password_field_stack(node: CleanDesignTreeNode) -> bool:
    """Gray rounded field whose content is obscured dots or an eye affordance."""
    if node.type != NodeType.STACK:
        return False
    height = node.sizing.height
    if height is not None and height > _MAX_CONTROL_HEIGHT:
        return False
    surfaces = [
        n
        for n in _local_nodes(node, _MAX_LOCAL_DEPTH)
        if n.type == NodeType.CONTAINER
        and (n.style.background_color is not None or n.style.border_radius is not None)
        and n.sizing.width
        and n.sizing.height
        and float(n.sizing.width) >= 200
    ]
    if not surfaces:
        return False
    local_nodes = _local_nodes(node, _MAX_LOCAL_DEPTH)
    dot_like = 0
    for item in local_nodes:
        if item.type != NodeType.CONTAINER:
            continue
        width = item.sizing.width
        height = item.sizing.height
        if width is None or height is None:
            continue
        if (
            width <= 14.0
            and height <= 14.0
            and (item.style.background_color is not None or item.vector_asset_key)
        ):
            dot_like += 1
    if dot_like >= 3:
        return True
    for item in local_nodes:
        key = (item.vector_asset_key or item.name or "").lower()
        if "eye" in key or "visibility" in key:
            return True
    for text_node in local_nodes:
        if text_node.type != NodeType.TEXT or not text_node.text:
            continue
        stripped = text_node.text.strip()
        if stripped and all(char in _PASSWORD_DOT_CHARS for char in stripped):
            return True
    return False


def layout_fact_consent_label_text(text: str | None) -> bool:
    """Return True when copy reads like a privacy/consent checkbox label."""
    lowered = (text or "").strip().lower()
    if not lowered:
        return False
    return any(hint in lowered for hint in _CONSENT_LABEL_HINTS)


def _hosts_decorative_icon_glyph(node: CleanDesignTreeNode) -> bool:
    """True when a compact square hosts a painted vector or image glyph."""
    for child in node.children:
        if child.type in {NodeType.VECTOR, NodeType.IMAGE} and (
            child.vector_asset_key or child.image_asset_key or child.style.has_stroke
        ):
            return True
        if (
            child.type in {NodeType.STACK, NodeType.CONTAINER}
            and child.children
            and _hosts_decorative_icon_glyph(child)
        ):
            return True
    return False


def _stroked_vector_is_checkbox_outline(vector: CleanDesignTreeNode) -> bool:
    return bool(vector.style.has_stroke) and not vector.style.background_color


def _stack_hosts_direction_badge_glyph(node: CleanDesignTreeNode) -> bool:
    """Return True for a bordered plate hosting an inset arrow or chevron vector."""
    if node.type not in {NodeType.STACK, NodeType.CONTAINER}:
        return False
    containers = [
        child
        for child in node.children
        if child.type == NodeType.CONTAINER
        and child.style.has_stroke
        and (child.style.border_width or 0.0) > 0.0
    ]
    vectors = [
        child
        for child in node.children
        if child.type == NodeType.VECTOR and child.style.has_stroke
    ]
    if len(containers) == 1 and vectors:
        plate = containers[0]
        plate_width = float(plate.sizing.width or 0.0)
        plate_height = float(plate.sizing.height or 0.0)
        if plate_width > 0.0 and plate_height > 0.0:
            for vector in vectors:
                vector_width = float(vector.sizing.width or 0.0)
                vector_height = float(vector.sizing.height or 0.0)
                if vector_width <= plate_width * 0.9 and vector_height <= plate_height * 0.9:
                    if vector_width < plate_width - 1.0 or vector_height < plate_height - 1.0:
                        return True
    if len(node.children) == 1:
        return _stack_hosts_direction_badge_glyph(node.children[0])
    return False


def _stroked_vector_fills_host_as_icon_glyph(
    host: CleanDesignTreeNode,
    vector: CleanDesignTreeNode,
) -> bool:
    """Return True when a stroked vector fills its host like a pictogram, not a checkbox frame."""
    host_width = float(host.sizing.width or 0.0)
    host_height = float(host.sizing.height or 0.0)
    vector_width = float(vector.sizing.width or 0.0)
    vector_height = float(vector.sizing.height or 0.0)
    if host_width <= 0.0 or host_height <= 0.0:
        return False
    if vector_width < host_width * 0.9 or vector_height < host_height * 0.9:
        return False
    return abs(host_width - host_height) > 2.0


def _vector_reads_as_checkbox_mark(
    vector: CleanDesignTreeNode,
    host: CleanDesignTreeNode,
) -> bool:
    """Return True when vector export metadata indicates a checkmark, not a pictogram."""
    path_count = vector.vector_svg_path_count
    if path_count is None:
        path_count = host.vector_svg_path_count
    return path_count is not None and path_count >= 2


def _stack_hosts_stroked_outline_checkbox_glyph(node: CleanDesignTreeNode) -> bool:
    """Square component icon with stroked hollow vectors (checkbox outline + optional mark)."""
    if node.type not in {NodeType.STACK, NodeType.CONTAINER}:
        return False
    if _stack_hosts_direction_badge_glyph(node):
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if not (
        _MIN_STROKED_GLYPH_CHECKBOX_SIZE <= width <= _MAX_CHECKBOX_SIZE
        and _MIN_STROKED_GLYPH_CHECKBOX_SIZE <= height <= _MAX_CHECKBOX_SIZE
        and abs(width - height) <= 4.0
    ):
        return False
    vectors = [child for child in node.children if child.type == NodeType.VECTOR]
    if len(vectors) == 1:
        vector = vectors[0]
        if not _stroked_vector_is_checkbox_outline(vector):
            return False
        if _stroked_vector_fills_host_as_icon_glyph(node, vector):
            return _vector_reads_as_checkbox_mark(vector, node)
        return True
    if len(vectors) == 2:
        outer, inner = sorted(
            vectors,
            key=lambda item: float(item.sizing.width or 0.0) * float(item.sizing.height or 0.0),
            reverse=True,
        )
        return _stroked_vector_is_checkbox_outline(outer) and _stroked_vector_is_checkbox_outline(
            inner
        )
    return False


def stack_hosts_decorative_metric_checkmark(stack: CleanDesignTreeNode) -> bool:
    """Return True when a checkbox-like stack is a static metric summary glyph."""
    if stack.type != NodeType.STACK:
        return False
    if not stack_hosts_checkbox_label_pair(stack):
        return False
    label_leaf: CleanDesignTreeNode | None = None
    for child in stack.children:
        host = checkbox_label_text_host(child)
        if host is not None:
            label_leaf = host
            break
    if label_leaf is None:
        return False
    text = (label_leaf.text or "").strip()
    if "%" not in text:
        return False
    return not layout_fact_consent_label_text(text)


def _parent_hosts_percent_metric_copy(parent: CleanDesignTreeNode) -> bool:
    """Return True when a layout host also carries short percent metric copy."""
    for child in parent.children:
        if child.type == NodeType.TEXT:
            text = (child.text or "").strip()
            if "%" in text and len(text) <= 64 and not layout_fact_consent_label_text(text):
                return True
        if child.type not in {NodeType.STACK, NodeType.ROW, NodeType.CONTAINER}:
            continue
        for descendant in child.children:
            if descendant.type != NodeType.TEXT:
                continue
            text = (descendant.text or "").strip()
            if "%" in text and len(text) <= 64 and not layout_fact_consent_label_text(text):
                return True
    return False


def layout_fact_decorative_metric_checkmark_glyph(
    node: CleanDesignTreeNode,
    *,
    parent_node: CleanDesignTreeNode | None = None,
) -> bool:
    """Return True when a compact stroked check glyph decorates a percent metric row."""
    if not _stack_hosts_stroked_outline_checkbox_glyph(node):
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if float(width) > 13.0 or float(height) > 13.0:
        return False
    if stack_hosts_checkbox_label_pair(node):
        return False
    if parent_node is None:
        return False
    return _parent_hosts_percent_metric_copy(parent_node)


def layout_fact_interactive_checkbox_control(
    node: CleanDesignTreeNode,
    *,
    parent_node: CleanDesignTreeNode | None = None,
) -> bool:
    """Return True when ``node`` should emit an interactive checkbox control."""
    if layout_fact_decorative_metric_checkmark_glyph(node, parent_node=parent_node):
        return False
    return layout_fact_checkbox_control(node)


def layout_fact_checkbox_control(node: CleanDesignTreeNode) -> bool:
    """Small square used as a consent, bonus, or list-tile checkbox control."""
    if node.type not in {NodeType.CONTAINER, NodeType.STACK, NodeType.INPUT}:
        return False
    if _stack_hosts_direction_badge_glyph(node):
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    stroked_glyph = _stack_hosts_stroked_outline_checkbox_glyph(node)
    min_size = _MIN_STROKED_GLYPH_CHECKBOX_SIZE if stroked_glyph else _MIN_CHECKBOX_SIZE
    if not (min_size <= width <= _MAX_CHECKBOX_SIZE and min_size <= height <= _MAX_CHECKBOX_SIZE):
        return False
    if abs(width - height) > 4.0:
        return False
    radius = node.style.border_radius
    if radius is not None and radius > 10.0:
        return False
    if node.style.background_color and (not node.style.border_color or not node.style.border_width):
        if _hosts_decorative_icon_glyph(node):
            return False
        if not node.children and node.type in {NodeType.CONTAINER, NodeType.STACK}:
            return False
        return True
    if not node.style.border_color or not node.style.border_width:
        if _stack_hosts_stroked_outline_checkbox_glyph(node):
            return True
        if _hosts_decorative_icon_glyph(node):
            return False
        return False
    return True


def layout_fact_hosts_compact_checkbox_control(node: CleanDesignTreeNode) -> bool:
    """Return True when ``node`` is (or only hosts) a compact checkbox square."""
    if layout_fact_checkbox_control(node):
        return True
    for child in node.children:
        if layout_fact_checkbox_control(child):
            return True
    return False


def compact_checkbox_leaf(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Return the compact checkbox node hosted by ``node``, if any."""
    if layout_fact_checkbox_control(node):
        return node
    for child in node.children:
        found = compact_checkbox_leaf(child)
        if found is not None:
            return found
    return None


def checkbox_label_text_host(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Return label ``TEXT`` beside a checkbox, including single-leaf STACK wrappers."""
    if node.type == NodeType.TEXT and (node.text or "").strip():
        return node
    if (
        node.type in {NodeType.STACK, NodeType.COLUMN, NodeType.CONTAINER}
        and len(node.children) == 1
    ):
        return checkbox_label_text_host(node.children[0])
    return None


def stack_hosts_checkbox_label_pair(stack: CleanDesignTreeNode) -> bool:
    """True when a ``Stack`` pairs a compact checkbox host with label copy."""
    if stack.type != NodeType.STACK or len(stack.children) < 2:
        return False
    checkbox_child: CleanDesignTreeNode | None = None
    label_leaf: CleanDesignTreeNode | None = None
    for child in stack.children:
        if layout_fact_hosts_compact_checkbox_control(child):
            if checkbox_child is not None:
                return False
            checkbox_child = child
            continue
        label_host = checkbox_label_text_host(child)
        if label_host is not None:
            if label_leaf is not None:
                return False
            label_leaf = label_host
            continue
        if child.type == NodeType.VECTOR:
            continue
        return False
    if checkbox_child is None or label_leaf is None:
        return False
    if is_link_text(label_leaf.text):
        return False
    return True


def row_hosts_checkbox_label_pair(row: CleanDesignTreeNode) -> bool:
    """True when a ``Row`` pairs a compact checkbox host with label copy."""
    if row.type != NodeType.ROW or len(row.children) != 2:
        return False
    checkbox_child: CleanDesignTreeNode | None = None
    label_leaf: CleanDesignTreeNode | None = None
    for child in row.children:
        if layout_fact_hosts_compact_checkbox_control(child):
            if checkbox_child is not None:
                return False
            checkbox_child = child
            continue
        label_host = checkbox_label_text_host(child)
        if label_host is not None:
            if label_leaf is not None:
                return False
            label_leaf = label_host
    if checkbox_child is None or label_leaf is None:
        return False
    if checkbox_child.type == NodeType.ROW and len(checkbox_child.children) == 2:
        nested_checkbox = any(
            layout_fact_hosts_compact_checkbox_control(grandchild)
            for grandchild in checkbox_child.children
        )
        nested_label = any(
            checkbox_label_text_host(grandchild) is not None
            for grandchild in checkbox_child.children
        )
        if nested_checkbox and nested_label:
            return False
    if is_link_text(label_leaf.text):
        return False
    return True


def row_bounded_inner_height(row: CleanDesignTreeNode) -> float | None:
    """Return the vertical span inside a flex row after top/bottom padding."""
    frame_height = row.sizing.height
    if frame_height is None or float(frame_height) <= 0:
        return None
    padding = row.padding
    if padding is None:
        return float(frame_height)
    vertical = float(padding.top or 0.0) + float(padding.bottom or 0.0)
    inner = float(frame_height) - vertical
    return inner if inner > 0 else None


def _hosts_single_line_text_leaf(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Return a single-line ``TEXT`` leaf hosted by ``node``, if any."""
    if node.type == NodeType.TEXT and (node.text or "").strip():
        return node
    if node.type == NodeType.COLUMN and len(node.children) == 1:
        child = node.children[0]
        if child.type == NodeType.TEXT and (child.text or "").strip():
            return child
    return None


def row_hosts_prefix_labeled_currency_input(row: CleanDesignTreeNode) -> bool:
    """Row with a short label, numeric ``INPUT``, and optional trailing currency glyph."""
    if row.type != NodeType.ROW or len(row.children) < 2:
        return False
    inputs = [child for child in row.children if child.type == NodeType.INPUT]
    if len(inputs) != 1:
        return False
    text_hosts = [
        leaf for child in row.children if (leaf := _hosts_single_line_text_leaf(child)) is not None
    ]
    if not text_hosts:
        return False
    currency_hosts = [leaf for leaf in text_hosts if "₽" in (leaf.text or "")]
    label_hosts = [leaf for leaf in text_hosts if leaf not in currency_hosts]
    if len(label_hosts) != 1:
        return False
    label_text = label_hosts[0].text or ""
    if any(char.isdigit() for char in label_text):
        return False
    return len(currency_hosts) <= 1


def text_is_payment_option_secondary(
    node: CleanDesignTreeNode,
    *,
    host_button: CleanDesignTreeNode | None = None,
) -> bool:
    """Muted single-line subtitle copy under payment option card titles."""
    from figma_flutter_agent.parser.interaction.selection import (
        button_is_payment_option_card,
    )

    if node.type != NodeType.TEXT:
        return False
    if node.style.font_size is not None and float(node.style.font_size) > 13.5:
        return False
    weight = (node.style.font_weight or "w400").lower()
    if any(token in weight for token in ("600", "700", "800")):
        return False
    if host_button is None:
        return False
    return button_is_payment_option_card(host_button)


def layout_fact_row_bounded_inline_control_row(row: CleanDesignTreeNode) -> bool:
    """Painted fixed-height row whose padded interior hosts compact checkbox+label."""
    if not row_hosts_checkbox_label_pair(row):
        return False
    if row_bounded_inner_height(row) is None:
        return False
    return bool(row.style.background_color)


def _name_matches_textarea(name: str) -> bool:
    """Return True when a Figma layer name denotes a multiline text area shell."""
    collapsed = (name or "").lower().replace(" ", "").replace("-", "").replace("_", "")
    return "textarea" in collapsed or collapsed == "textareafield"


_TALL_MULTILINE_INPUT_MIN_HEIGHT = 80.0


def layout_fact_tall_multiline_input_shell(
    host_node: CleanDesignTreeNode | None,
    *,
    field_height: float | None,
) -> bool:
    """True when an input host is a tall multiline comment shell, not a single-line field."""
    if (
        host_node is None
        or field_height is None
        or float(field_height) < _TALL_MULTILINE_INPUT_MIN_HEIGHT
    ):
        return False
    min_height = host_node.sizing.min_height
    if min_height is not None and float(min_height) >= _TALL_MULTILINE_INPUT_MIN_HEIGHT:
        return True
    host_height = host_node.sizing.height
    return host_height is not None and float(host_height) >= _TALL_MULTILINE_INPUT_MIN_HEIGHT


def layout_fact_textarea_field(node: CleanDesignTreeNode) -> bool:
    """Multiline comment field shell: named Textarea with a single copy line inside."""
    if not _name_matches_textarea(node.name):
        return False
    if node.type not in {NodeType.ROW, NodeType.CONTAINER, NodeType.COLUMN}:
        return False
    height = node.sizing.height or node.sizing.min_height
    if height is None or float(height) < 80.0:
        return False

    def first_text(item: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
        if item.type == NodeType.TEXT and (item.text or "").strip():
            return item
        for child in item.children:
            found = first_text(child)
            if found is not None:
                return found
        return None

    return first_text(node) is not None


def _is_input_decorative_control(node: CleanDesignTreeNode) -> bool:
    """Icon-only ``BUTTON`` chrome inside a flex ``INPUT`` (calendar, chevron)."""
    if node.type != NodeType.BUTTON:
        return False
    return layout_fact_input_trailing_icon_button(node) or layout_fact_compact_icon_action_button(
        node
    )


def _is_input_visibility_affordance(node: CleanDesignTreeNode) -> bool:
    """Eye / visibility toggle beside a single-line input value row."""
    if node.type == NodeType.INPUT:
        return False
    key = (node.name or node.vector_asset_key or "").lower()
    if "eye" in key or "visibility" in key:
        return True
    for desc in _local_nodes(node, _MAX_LOCAL_DEPTH):
        dkey = (desc.name or desc.vector_asset_key or "").lower()
        if "eye" in dkey or "visibility" in dkey:
            return True
    return False


def input_trailing_chrome_implies_obscure_text(node: CleanDesignTreeNode) -> bool:
    """Return True when trailing icon chrome is a password visibility toggle."""
    from .input_fields import input_trailing_chrome_nodes

    return any(
        _is_input_visibility_affordance(chrome) for chrome in input_trailing_chrome_nodes(node)
    )


def _is_nested_input_surface_host(node: CleanDesignTreeNode) -> bool:
    """Return True when a nested host only wraps the painted field surface.

    Figma decomposes flex form fields into an outer ``INPUT`` (label + spacing) and an
    inner painted surface row that hosts the bordered field chrome. The inner host is
    presentational chrome, not a second form control.
    """
    if node.type not in {NodeType.INPUT, NodeType.ROW}:
        return False
    from .inline_input_hosts import layout_fact_flex_painted_input_surface

    if node.type == NodeType.ROW and layout_fact_flex_painted_input_surface(node):
        return True
    if node.type != NodeType.INPUT:
        return False
    from .input_fields import input_surface_node

    if input_surface_node(node) is None:
        return False
    top_labels = [
        child
        for child in node.children
        if child.type == NodeType.TEXT and (child.text or "").strip()
    ]
    if top_labels:
        return False

    def walk(children: list[CleanDesignTreeNode]) -> bool:
        for child in children:
            if child.type in _INTERACTIVE_INPUT_CHILD_TYPES:
                if child.type == NodeType.INPUT:
                    return False
                if _is_input_decorative_control(child) or _is_input_visibility_affordance(child):
                    if child.children and not walk(child.children):
                        return False
                    continue
                return False
            if child.children and not walk(child.children):
                return False
        return True

    return walk(node.children)


def input_children_are_presentational(node: CleanDesignTreeNode) -> bool:
    """Return True when INPUT children are chrome (labels/surfaces), not nested controls.

    Flex-hug ``INPUT`` frames from Figma often decompose into a ``COLUMN`` plus value
    ``TEXT`` instead of a nested ``CONTAINER`` fill. Those should compile to one
    ``TextField``, not a ``Column`` of static text widgets.

    Args:
        node: Parsed ``INPUT`` node.

    Returns:
        ``True`` when every descendant is presentational (no nested form controls).
    """

    def walk(children: list[CleanDesignTreeNode]) -> bool:
        for child in children:
            if child.type in _INTERACTIVE_INPUT_CHILD_TYPES:
                if child.type == NodeType.INPUT and _is_nested_input_surface_host(child):
                    if child.children and not walk(child.children):
                        return False
                    continue
                if _is_input_decorative_control(child) or _is_input_visibility_affordance(child):
                    if child.children and not walk(child.children):
                        return False
                    continue
                return False
            if child.children and not walk(child.children):
                return False
        return True

    return bool(node.children) and walk(node.children)


def input_hint_implies_obscure_text(hint: str) -> bool:
    """Return True when placeholder copy implies a masked password field.

    Link labels such as ``Forgot Password`` must not enable ``obscureText``.
    """
    if not hint or is_link_text(hint):
        return False
    return "password" in hint.strip().lower()


def is_link_text(text: str | None) -> bool:
    """Return True when ``text`` looks like a tappable inline link label."""
    if not text:
        return False
    label = text.strip().lower()
    if len(label) > 64:
        return False
    if "already have" in label or "don't have an account" in label:
        return True
    if len(label.split()) >= 5:
        return False
    return any(hint in label for hint in _LINK_HINTS)


def _is_footer_link_text_node(text_node: CleanDesignTreeNode) -> bool:
    """True for secondary account-switch copy below a primary CTA."""
    label = (text_node.text or text_node.name or "").strip().lower()
    if not label:
        return False
    if "already have" in label or "don't have an account" in label:
        return True
    return is_link_text(text_node.text) and len(label) > 12


def _looks_like_form_field_stack(
    *,
    host_node: CleanDesignTreeNode | None = None,
    text_nodes: list[CleanDesignTreeNode],
    surfaces: list[CleanDesignTreeNode],
) -> bool:
    """Gray rounded field + single inset label (e.g. name prefilled as ``afsar``)."""
    if host_node is not None:
        from .icons import (
            layout_fact_stack_vertical_icon_label_chip_tile,
            layout_fact_upload_placeholder_tile,
        )

        if layout_fact_stack_vertical_icon_label_chip_tile(host_node):
            return False
        if layout_fact_upload_placeholder_tile(host_node):
            return False
    if len(text_nodes) != 1 or not surfaces:
        return False
    text_node = text_nodes[0]
    label = (text_node.text or text_node.name or "").strip().lower()
    if _label_matches_action_hint(label):
        return False
    if any(hint in label for hint in _INPUT_HINTS):
        return True
    placement = text_node.stack_placement
    if placement is None or placement.left is None or placement.left < 8:
        return False
    if host_node is not None and _caption_label_below_icon_band(host_node, text_node):
        return False
    surface = max(
        surfaces,
        key=lambda item: float(item.sizing.width or 0) * float(item.sizing.height or 0),
    )
    return surface.style.background_color is not None or surface.style.border_radius is not None


def _caption_label_below_icon_band(
    host_node: CleanDesignTreeNode,
    text_node: CleanDesignTreeNode,
) -> bool:
    """Caption sibling below an upper icon/plate band is not an inset field value."""
    height = host_node.sizing.height
    if height is None or float(height) <= 0:
        return False
    placement = text_node.stack_placement
    if placement is None:
        return False
    label_top = placement.top if placement.top is not None else 0.0
    if label_top < float(height) * 0.55:
        return False
    for child in host_node.children:
        if child.id == text_node.id:
            continue
        if child.type not in {NodeType.CONTAINER, NodeType.STACK, NodeType.VECTOR, NodeType.IMAGE}:
            continue
        child_placement = child.stack_placement
        child_top = float(child_placement.top or 0.0) if child_placement is not None else 0.0
        if child_top <= float(height) * 0.45:
            return True
    return False


def checkbox_option_stack_is_checked(stack: CleanDesignTreeNode) -> bool:
    """Return True when a checkbox option row carries an inline checkmark glyph."""
    from figma_flutter_agent.generator.variant.state import variant_is_checked

    if variant_is_checked(stack):
        return True
    for child in stack.children:
        if child.type != NodeType.VECTOR or not child.style.has_stroke:
            continue
        width = child.sizing.width or 0.0
        height = child.sizing.height or 0.0
        if 0.0 < float(width) <= 14.0 and 0.0 < float(height) <= 12.0:
            return True
    return False


def checkbox_option_border_container(
    stack: CleanDesignTreeNode,
) -> CleanDesignTreeNode | None:
    """Return the stroked square that frames a compact checkbox option."""
    for child in stack.children:
        if child.type != NodeType.CONTAINER:
            continue
        if not child.style.border_color or not child.style.border_width:
            continue
        width = child.sizing.width
        height = child.sizing.height
        if width is None or height is None:
            continue
        if (
            _MIN_CHECKBOX_SIZE <= float(width) <= _MAX_CHECKBOX_SIZE
            and _MIN_CHECKBOX_SIZE <= float(height) <= _MAX_CHECKBOX_SIZE
            and abs(float(width) - float(height)) <= 4.0
        ):
            return child
    return None


def checkbox_option_label_gap(stack: CleanDesignTreeNode) -> float | None:
    """Derive checkbox-to-label spacing from absolute placements when present."""
    box = checkbox_option_border_container(stack)
    label_leaf: CleanDesignTreeNode | None = None
    for child in stack.children:
        host = checkbox_label_text_host(child)
        if host is not None:
            label_leaf = host
            break
    if box is None or label_leaf is None:
        return None
    label_placement = label_leaf.stack_placement
    box_placement = box.stack_placement
    if label_placement is None or box_placement is None:
        return None
    label_left = label_placement.left
    if label_left is None:
        return None
    box_left = box_placement.left if box_placement.left is not None else 0.0
    box_width = box.sizing.width or box_placement.width or 0.0
    if float(box_width) <= 0:
        return None
    gap = float(label_left) - (float(box_left) + float(box_width))
    if gap >= 4.0:
        return gap
    return None


def _stack_spans_primary_button_and_footer_link(
    node: CleanDesignTreeNode,
    *,
    text_nodes: list[CleanDesignTreeNode],
) -> bool:
    """True when a stack pairs a CTA label with a separate footer link row."""
    from .input_fields import primary_surface_node

    stack_height = node.sizing.height
    if stack_height is not None and float(stack_height) > 120.0:
        return False
    action_nodes = [
        item
        for item in text_nodes
        if _label_matches_action_hint((item.text or item.name or "").strip().lower())
        and not _is_footer_link_text_node(item)
    ]
    footer_nodes = [item for item in text_nodes if _is_footer_link_text_node(item)]
    if not action_nodes or not footer_nodes:
        return False

    for action in action_nodes:
        action_placement = action.stack_placement
        action_top = (
            float(action_placement.top)
            if action_placement is not None and action_placement.top is not None
            else 0.0
        )
        for footer in footer_nodes:
            footer_placement = footer.stack_placement
            if footer_placement is None or footer_placement.top is None:
                continue
            if float(footer_placement.top) >= action_top + 12.0:
                return True

    surface = primary_surface_node(node)
    stack_height = node.sizing.height
    if surface is None or stack_height is None:
        return False
    surface_height = float(surface.sizing.height or 0)
    return stack_height > surface_height + 16.0


def interaction_surface_node(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Resolve the painted surface for a tap target or text field.

    Figma often places fill and corner radius on the ``BUTTON`` / ``INPUT`` frame
    itself rather than on a child ``CONTAINER``. ``primary_surface_node`` only
    inspects container descendants; this helper falls back to the host frame.

    Args:
        node: Parsed clean-tree node (``BUTTON``, ``INPUT``, or ``STACK``).

    Returns:
        The largest child container surface, or the host when it carries the fill.
    """
    from .input_fields import primary_surface_node

    surface = primary_surface_node(node)
    if surface is not None:
        return surface
    if node.type not in {
        NodeType.BUTTON,
        NodeType.INPUT,
        NodeType.STACK,
        NodeType.ROW,
        NodeType.COLUMN,
    }:
        return None
    if node.style.gradient is not None and node.sizing.width and node.sizing.height:
        return node
    if not (node.style.background_color or node.style.border_color):
        return None
    if not node.sizing.width or not node.sizing.height:
        return None
    return node


def layout_fact_bottom_docked_sheet(node: CleanDesignTreeNode) -> bool:
    """Bottom-anchored white sheet (save bar) with upward-rounded top edge."""
    if node.type != NodeType.COLUMN:
        return False
    placement = node.stack_placement
    if placement is None or placement.vertical != "BOTTOM":
        return False
    height = node.sizing.height
    if height is None or not (80.0 <= height <= 140.0):
        return False
    width = node.sizing.width
    if width is None or width < 320.0:
        return False
    return bool(node.style.background_color or node.style.effects)


def must_inline_extracted_widget_host(node: CleanDesignTreeNode) -> bool:
    """Return True when LLM ``extracted`` IR must not replace the host with a widget stub.

    Compact login/sign-up form fields compile inline via the deterministic layout
    engine (labels, surfaces, obscure text, suffix icons). Stubbing them as
    ``const FooWidget()`` drops Figma structure and breaks password/email parity.

    Args:
        node: Parsed clean-tree host node.

    Returns:
        ``True`` for ``INPUT`` hosts and password/input stacks.
    """
    if node.type == NodeType.INPUT:
        return True
    from figma_flutter_agent.parser.interaction.step import layout_fact_step_indicator_title_column

    if layout_fact_step_indicator_title_column(node):
        return True
    from figma_flutter_agent.parser.interaction.selection import (
        layout_fact_compact_trailing_selection_glyph,
    )
    from figma_flutter_agent.parser.interaction.step import (
        layout_fact_success_check_glyph_host,
    )

    if layout_fact_compact_trailing_selection_glyph(node):
        return True
    if layout_fact_success_check_glyph_host(node):
        return True
    from .enrichment import stack_interaction_kind

    if stack_interaction_kind(node) == "input":
        return True
    if layout_fact_password_field_stack(node):
        return True
    from figma_flutter_agent.parser.interaction.inline_input_hosts import (
        layout_fact_inline_labeled_input_field_host,
        layout_fact_phone_composite_field_host,
    )

    return layout_fact_inline_labeled_input_field_host(
        node
    ) or layout_fact_phone_composite_field_host(node)
