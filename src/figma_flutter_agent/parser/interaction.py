"""Heuristics for interactive groups (classic absolute Figma layouts)."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_INPUT_HINTS = ("email", "password", "phone", "username", "search", "name")
_ACTION_HINTS = (
    "continue with",
    "log in",
    "login",
    "sign up",
    "sign in",
    "submit",
    "get started",
    "register",
    "forgot password",
    "save",
    "no thanks",
)
_SINGLE_WORD_ACTION_LABELS = frozenset(
    {
        "start",
        "play",
        "ok",
        "go",
        "home",
        "music",
        "meditate",
        "sleep",
        "all",
        "my",
        "save",
    }
)
WEEKDAY_CHIP_ROW_NAME = "WeekdayChipRow"
_WEEKDAY_CHIP_LABELS = frozenset({"su", "m", "t", "w", "th", "f", "s"})
_WEEKDAY_CHIP_MIN_SIZE = 32.0
_WEEKDAY_CHIP_MAX_SIZE = 56.0
_MAX_CONTROL_HEIGHT = 120.0
_MAX_CONTROL_CHILDREN = 8
_MAX_LOCAL_DEPTH = 2
_BACK_NAV_DESCENDANT_DEPTH = 6
_INPUT_TRAILING_ICON_DESCENDANT_DEPTH = 6
_COMPACT_ICON_ACTION_MIN = 20.0
_COMPACT_ICON_ACTION_MAX = 43.0
_ICON_ACTION_NAME_HINTS = (
    "arrow",
    "back",
    "close",
    "chevron",
    "caret",
    "nav",
    "narrow",
)


def _label_matches_action_hint(label: str) -> bool:
    normalized = label.strip().lower()
    if not normalized:
        return False
    if normalized in _SINGLE_WORD_ACTION_LABELS:
        return True
    return any(hint in normalized for hint in _ACTION_HINTS)


def _local_nodes(node: CleanDesignTreeNode, max_depth: int) -> list[CleanDesignTreeNode]:
    """Collect descendants up to ``max_depth`` without crossing other stack groups."""
    nodes: list[CleanDesignTreeNode] = []

    def walk(current: CleanDesignTreeNode, depth: int) -> None:
        if depth > max_depth:
            return
        nodes.append(current)
        if depth == max_depth:
            return
        for child in current.children:
            walk(child, depth + 1)

    for child in node.children:
        walk(child, 1)
    return nodes


def _descendant_nodes(node: CleanDesignTreeNode, max_depth: int) -> list[CleanDesignTreeNode]:
    """Collect descendants up to ``max_depth`` levels below ``node`` (inclusive of ``node``)."""
    nodes: list[CleanDesignTreeNode] = [node]

    def walk(current: CleanDesignTreeNode, depth: int) -> None:
        if depth >= max_depth:
            return
        for child in current.children:
            nodes.append(child)
            walk(child, depth + 1)

    walk(node, 0)
    return nodes


def _is_structural_button_shell(child: CleanDesignTreeNode) -> bool:
    """Return True for inner layout stacks that only wrap one social-style button row."""
    if child.type != NodeType.STACK:
        return False
    local_nodes = _local_nodes(child, _MAX_LOCAL_DEPTH)
    has_surface = any(
        item.type == NodeType.CONTAINER
        and (item.style.background_color or item.style.border_color)
        for item in local_nodes
    )
    has_action_text = any(
        item.type == NodeType.TEXT
        and item.text
        and any(hint in item.text.lower() for hint in _ACTION_HINTS)
        for item in local_nodes
    )
    return has_surface and has_action_text


_PASSWORD_DOT_CHARS = frozenset("•·●∙*·.")
_MAX_CHECKBOX_SIZE = 32.0
_MIN_CHECKBOX_SIZE = 16.0


def looks_like_password_field_stack(node: CleanDesignTreeNode) -> bool:
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
        if width <= 14.0 and height <= 14.0 and (
            item.style.background_color is not None or item.vector_asset_key
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


def looks_like_checkbox_control(node: CleanDesignTreeNode) -> bool:
    """Small bordered square used as a consent or list-tile checkbox control."""
    if node.type not in {NodeType.CONTAINER, NodeType.STACK, NodeType.INPUT}:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if not (_MIN_CHECKBOX_SIZE <= width <= _MAX_CHECKBOX_SIZE and _MIN_CHECKBOX_SIZE <= height <= _MAX_CHECKBOX_SIZE):
        return False
    if abs(width - height) > 4.0:
        return False
    if not node.style.border_color or not node.style.border_width:
        return False
    radius = node.style.border_radius
    if radius is not None and radius > 10.0:
        return False
    return True


def hosts_compact_checkbox_control(node: CleanDesignTreeNode) -> bool:
    """Return True when ``node`` is (or only hosts) a compact checkbox square."""
    if looks_like_checkbox_control(node):
        return True
    if len(node.children) == 1 and looks_like_checkbox_control(node.children[0]):
        return True
    return False


def compact_checkbox_leaf(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Return the compact checkbox node hosted by ``node``, if any."""
    if looks_like_checkbox_control(node):
        return node
    for child in node.children:
        if looks_like_checkbox_control(child):
            return child
    return None


def row_hosts_checkbox_label_pair(row: CleanDesignTreeNode) -> bool:
    """True when a ``Row`` pairs a compact checkbox host with a label ``TEXT``."""
    if row.type != NodeType.ROW or len(row.children) != 2:
        return False
    checkbox_hosts = sum(
        1 for child in row.children if hosts_compact_checkbox_control(child)
    )
    text_hosts = sum(1 for child in row.children if child.type == NodeType.TEXT)
    return checkbox_hosts == 1 and text_hosts == 1


def looks_like_textarea_field(node: CleanDesignTreeNode) -> bool:
    """Multiline comment field shell: named Textarea with a single copy line inside."""
    if "textarea" not in (node.name or "").lower():
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


def textarea_hint_node(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """First non-empty ``TEXT`` descendant for a textarea shell."""

    def first_text(item: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
        if item.type == NodeType.TEXT and (item.text or "").strip():
            return item
        for child in item.children:
            found = first_text(child)
            if found is not None:
                return found
        return None

    return first_text(node)


def _has_circular_container(local_nodes: list[CleanDesignTreeNode]) -> bool:
    for item in local_nodes:
        if item.type != NodeType.CONTAINER:
            continue
        width = item.sizing.width
        height = item.sizing.height
        if width is None or height is None:
            continue
        w = float(width)
        h = float(height)
        if w < 44.0 or h < 44.0:
            continue
        if abs(w - h) <= 4.0 or (item.style.border_radius or 0) >= 20.0:
            return True
    return False


def _has_icon_action_name(node: CleanDesignTreeNode) -> bool:
    labels = [
        (node.name or "").lower(),
        (node.accessibility_label or "").lower(),
    ]
    if node.variant is not None and node.variant.component_name:
        labels.append(node.variant.component_name.lower())
    combined = " ".join(labels)
    return any(hint in combined for hint in _ICON_ACTION_NAME_HINTS)


def _stack_has_vector_icon(local_nodes: list[CleanDesignTreeNode]) -> bool:
    return any(
        item.vector_asset_key
        or item.type == NodeType.VECTOR
        or (item.name or "").lower().startswith("vector")
        for item in local_nodes
    )


def looks_like_compact_icon_action_stack(node: CleanDesignTreeNode) -> bool:
    """Small Figma icon components (e.g. 24x24 ``arrow-narrow-left``) used as back/close."""
    if node.type != NodeType.STACK:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if not (
        _COMPACT_ICON_ACTION_MIN <= width <= _COMPACT_ICON_ACTION_MAX
        and _COMPACT_ICON_ACTION_MIN <= height <= _COMPACT_ICON_ACTION_MAX
    ):
        return False
    local_nodes = _descendant_nodes(node, _BACK_NAV_DESCENDANT_DEPTH)
    if not _stack_has_vector_icon(local_nodes):
        return False
    return _has_icon_action_name(node) or node.component_ref is not None


def is_back_navigation_icon_stack(node: CleanDesignTreeNode) -> bool:
    """Return True for back/close affordances (not favorite/download/share)."""
    if not looks_like_back_nav_stack(node) and not looks_like_compact_icon_action_stack(node):
        return False
    labels = [
        (node.name or "").lower(),
        (node.accessibility_label or "").lower(),
    ]
    if node.variant is not None and node.variant.component_name:
        labels.append(node.variant.component_name.lower())
    combined = " ".join(labels)
    if any(token in combined for token in ("heart", "favorite", "download", "share")):
        return False
    if looks_like_compact_icon_action_stack(node):
        return True
    return any(
        token in combined
        for token in (
            "back",
            "close",
            "arrow-left",
            "arrow-narrow-left",
            "chevron-left",
            "x",
            "vector 13",
        )
    )


def looks_like_back_nav_stack(node: CleanDesignTreeNode) -> bool:
    """Circular or compact icon affordance (back, close, favorite, download)."""
    if looks_like_compact_icon_action_stack(node):
        return True
    if node.type != NodeType.STACK:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if not (44.0 <= width <= 64.0 and 44.0 <= height <= 64.0):
        return False
    local_nodes = _descendant_nodes(node, _BACK_NAV_DESCENDANT_DEPTH)
    return _has_circular_container(local_nodes) and _stack_has_vector_icon(local_nodes)


def looks_like_skip_control_stack(node: CleanDesignTreeNode) -> bool:
    """Small skip/rewind control with a numeric label (e.g. 15 seconds)."""
    if node.type != NodeType.STACK:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if not (28.0 <= width <= 56.0 and 28.0 <= height <= 56.0):
        return False
    for text_node in _descendant_nodes(node, _BACK_NAV_DESCENDANT_DEPTH):
        if text_node.type != NodeType.TEXT or not text_node.text:
            continue
        label = text_node.text.strip()
        if label.isdigit() and len(label) <= 2:
            return True
    if not node.children and node.cluster_id and _stack_has_vector_icon([node]):
        return True
    return False


def button_stack_has_left_icon(parent_node: CleanDesignTreeNode) -> bool:
    """True when a tap row has a brand/icon anchor in the left fifth of the button."""
    parent_width = parent_node.sizing.width
    if parent_width is None or parent_width <= 0:
        return False
    threshold = float(parent_width) * 0.22

    def _icon_on_left(node: CleanDesignTreeNode) -> bool:
        if node.type == NodeType.VECTOR and node.vector_asset_key:
            placement = node.stack_placement
            left = placement.left if placement is not None and placement.left is not None else 0.0
            return left < threshold
        return False

    for child in parent_node.children:
        if _icon_on_left(child):
            return True
        if child.type == NodeType.STACK and len(child.children) <= 4:
            if any(_icon_on_left(item) for item in child.children):
                return True
    return False


def skip_control_left_side_of_parent(
    node: CleanDesignTreeNode,
    *,
    parent_width: float | None = None,
) -> bool:
    """Infer rewind (left) vs forward (right) skip from absolute placement pins."""
    placement = node.stack_placement
    if placement is None:
        return False
    width = parent_width if parent_width is not None and parent_width > 0 else 374.0
    node_w = float(node.sizing.width or 0.0)
    threshold = float(width) * 0.35
    if placement.left is not None:
        return float(placement.left) < threshold
    if placement.right is not None:
        inferred_left = float(width) - float(placement.right) - node_w
        return inferred_left < threshold
    return False


def looks_like_play_pause_control_stack(node: CleanDesignTreeNode) -> bool:
    """Center play/pause cluster (circle + pause bars)."""
    if node.type != NodeType.STACK:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None or width < 70.0 or height < 70.0:
        return False
    if width > 150.0 or height > 150.0:
        return False
    if node.render_boundary and not node.children:
        flattened = node.flatten_figma_node_ids or ()
        return len(flattened) >= 4
    local_nodes = _local_nodes(node, _MAX_LOCAL_DEPTH)
    bars = 0
    cores = 0
    for item in local_nodes:
        if item.type != NodeType.CONTAINER:
            continue
        w = item.sizing.width
        h = item.sizing.height
        if w is None or h is None:
            continue
        wf = float(w)
        hf = float(h)
        if hf > wf * 1.4 and hf >= 18.0:
            bars += 1
        if abs(wf - hf) <= 6.0 and wf >= 50.0:
            cores += 1
    return bars >= 2 and cores >= 1


def looks_like_media_controls_stack(node: CleanDesignTreeNode) -> bool:
    """Player chrome: play/pause, skip, and a ``MM:SS`` timeline row."""
    if node.type != NodeType.STACK:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None or width < 280.0 or height < 120.0:
        return False
    local_nodes = _local_nodes(node, 5)
    has_timestamps = any(
        item.type == NodeType.TEXT
        and item.text
        and ":" in item.text
        and len(item.text.strip()) <= 8
        for item in local_nodes
    )
    has_play = looks_like_play_pause_control_stack(node) or any(
        looks_like_play_pause_control_stack(item)
        for item in local_nodes
        if item.type == NodeType.STACK
    )
    return has_timestamps and has_play


_METADATA_COLUMN_MAX_WIDTH = 140.0
_ROW_BODY_SEARCH_DEPTH = 8


_LIST_TILE_LEAD_MAX_WIDTH = 64.0
_LIST_TILE_TRAIL_MAX_WIDTH = 32.0
_LIST_TILE_TEXT_SEARCH_DEPTH = 8


def _subtree_text_node_count(node: CleanDesignTreeNode, depth: int = 0) -> int:
    if depth > _LIST_TILE_TEXT_SEARCH_DEPTH:
        return 0
    count = 1 if node.type == NodeType.TEXT and node.text else 0
    for child in node.children:
        count += _subtree_text_node_count(child, depth + 1)
    return count


def button_has_list_tile_row_body(node: CleanDesignTreeNode) -> bool:
    """Return True when a tappable frame is a horizontal icon + text + chevron row.

    Args:
        node: Parsed clean-tree button host.

    Returns:
        ``True`` when the node uses auto-layout spacing with a growing text block
        between compact leading/trailing chrome.
    """
    from figma_flutter_agent.schemas import SizingMode

    if node.type != NodeType.BUTTON or len(node.children) < 2 or node.spacing <= 0:
        return False
    has_fill = any(child.sizing.width_mode == SizingMode.FILL for child in node.children)
    if not has_fill and len(node.children) < 3:
        return False
    lead_width = node.children[0].sizing.width
    trail_width = node.children[-1].sizing.width if len(node.children) >= 3 else None
    compact_lead = lead_width is not None and float(lead_width) <= _LIST_TILE_LEAD_MAX_WIDTH
    compact_trail = (
        trail_width is not None and float(trail_width) <= _LIST_TILE_TRAIL_MAX_WIDTH
    )
    text_lines = sum(_subtree_text_node_count(child) for child in node.children)
    return text_lines >= 2 and (compact_lead or compact_trail)


def list_tile_leading_icon_slot(
    node: CleanDesignTreeNode,
    parent_node: CleanDesignTreeNode | None,
    *,
    parent_type: NodeType | None = None,
) -> bool:
    """Return True when ``node`` is the leading icon rail in a settings-style list row.

    Args:
        node: Candidate leading icon host.
        parent_node: Immediate parent clean-tree node.
        parent_type: Parent node type from the render pass.

    Returns:
        ``True`` for the first compact child of a list-tile ``Row`` body.
    """
    from figma_flutter_agent.schemas import SizingMode

    if parent_node is None:
        return False
    row_host = parent_node
    if parent_type == NodeType.BUTTON and button_has_list_tile_row_body(parent_node):
        row_host = parent_node
    elif parent_type != NodeType.ROW:
        return False
    if not row_host.children or row_host.children[0].id != node.id:
        return False
    if len(row_host.children) < 3:
        return False
    has_fill = any(
        child.sizing.width_mode == SizingMode.FILL for child in row_host.children
    )
    if not has_fill:
        return False
    lead_width = node.sizing.width
    if lead_width is not None and float(lead_width) > _LIST_TILE_LEAD_MAX_WIDTH:
        return False
    return True


def button_has_composite_row_body(node: CleanDesignTreeNode) -> bool:
    """Return True when a tappable frame hosts a list-card style row body.

    These bodies pair a growing text column with a fixed-width metadata column
    (timestamp, badge). They must keep intrinsic vertical sizing in Flutter:
    the Figma bbox is often shorter than ``StrutStyle`` layout metrics.

    Args:
        node: Parsed clean-tree button/stack host.

    Returns:
        ``True`` when the subtree contains a multi-child ``Row`` with a narrow
        metadata sibling.
    """
    if node.type not in {NodeType.BUTTON, NodeType.STACK}:
        return False

    def walk(current: CleanDesignTreeNode, depth: int) -> bool:
        if depth > _ROW_BODY_SEARCH_DEPTH:
            return False
        if current.type == NodeType.ROW and len(current.children) >= 2:
            has_primary = any(
                child.type in {NodeType.COLUMN, NodeType.CONTAINER, NodeType.STACK}
                for child in current.children
            )
            has_metadata = any(
                child.sizing.width is not None
                and 0 < float(child.sizing.width) <= _METADATA_COLUMN_MAX_WIDTH
                for child in current.children
            )
            if has_primary and has_metadata:
                return True
        return any(walk(child, depth + 1) for child in current.children)

    return walk(node, 0)


def stack_interaction_kind(node: CleanDesignTreeNode) -> str | None:
    """Classify absolute ``STACK`` groups as tap targets or text fields.

    Args:
        node: Parsed clean-tree node (typically ``STACK`` from a Figma ``GROUP``).

    Returns:
        ``"input"``, ``"button"``, or ``None``.
    """
    if node.type != NodeType.STACK:
        return None

    if looks_like_password_field_stack(node):
        return "input"

    if looks_like_skip_control_stack(node):
        return "button"

    height = node.sizing.height
    if height is not None and height > _MAX_CONTROL_HEIGHT:
        return None
    if len(node.children) > _MAX_CONTROL_CHILDREN:
        return None

    nested_kind = next(
        (
            kind
            for child in node.children
            if child.type == NodeType.STACK
            and not _is_structural_button_shell(child)
            and (kind := stack_interaction_kind(child)) is not None
        ),
        None,
    )
    if nested_kind is not None:
        return None

    local_nodes = _local_nodes(node, _MAX_LOCAL_DEPTH)
    text_nodes = [n for n in local_nodes if n.type == NodeType.TEXT and n.text]
    if not text_nodes:
        return None
    surfaces = [
        n
        for n in local_nodes
        if n.type == NodeType.CONTAINER
        and (
            n.style.background_color is not None
            or n.style.border_color is not None
            or n.style.border_radius is not None
        )
    ]
    if not surfaces:
        return None

    for text_node in text_nodes:
        label = (text_node.text or text_node.name or "").strip().lower()
        if any(hint in label for hint in _INPUT_HINTS) and len(label) < 48:
            return "input"

    for text_node in text_nodes:
        label = (text_node.text or text_node.name or "").strip().lower()
        if _label_matches_action_hint(label):
            if _stack_spans_primary_button_and_footer_link(node, text_nodes=text_nodes):
                return None
            return "button"

    if _looks_like_form_field_stack(text_nodes=text_nodes, surfaces=surfaces):
        return "input"

    return None


def _is_footer_link_text_node(text_node: CleanDesignTreeNode) -> bool:
    """True for secondary account-switch copy below a primary CTA."""
    label = (text_node.text or text_node.name or "").strip().lower()
    if not label:
        return False
    if "already have" in label or "don't have an account" in label:
        return True
    return is_link_text(text_node.text) and len(label) > 12


def _stack_spans_primary_button_and_footer_link(
    node: CleanDesignTreeNode,
    *,
    text_nodes: list[CleanDesignTreeNode],
) -> bool:
    """True when a stack pairs a CTA label with a separate footer link row."""
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


def input_hint_text(node: CleanDesignTreeNode) -> str:
    """Return placeholder label for an input-like stack group."""
    hint_node = input_hint_node(node)
    if hint_node is not None and hint_node.text:
        return hint_node.text.strip()
    return node.accessibility_label or node.name


def input_hint_node(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Return the placeholder ``TEXT`` node inside an input-like stack group."""
    for text_node in _local_nodes(node, _MAX_LOCAL_DEPTH):
        if text_node.type == NodeType.TEXT and text_node.text:
            return text_node
    return None


def _looks_like_form_field_stack(
    *,
    text_nodes: list[CleanDesignTreeNode],
    surfaces: list[CleanDesignTreeNode],
) -> bool:
    """Gray rounded field + single inset label (e.g. name prefilled as ``afsar``)."""
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
    surface = max(
        surfaces,
        key=lambda item: float(item.sizing.width or 0) * float(item.sizing.height or 0),
    )
    return surface.style.background_color is not None or surface.style.border_radius is not None


def primary_surface_node(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Pick the main RECTANGLE surface inside a group (largest area)."""
    surfaces = [
        n
        for n in _local_nodes(node, _MAX_LOCAL_DEPTH)
        if n.type == NodeType.CONTAINER
        and n.sizing.width
        and n.sizing.height
        and (n.style.background_color or n.style.border_color)
    ]
    if not surfaces:
        return None
    return max(surfaces, key=lambda n: float(n.sizing.width or 0) * float(n.sizing.height or 0))


def input_surface_node(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Resolve painted surface for flex/stack ``INPUT`` frames.

    Figma often applies fill and corner radius on the ``INPUT`` host rather than a
    child ``CONTAINER``. Falls back to the host when it carries field chrome.
    """
    surface = primary_surface_node(node)
    if surface is not None:
        return surface
    if node.type == NodeType.INPUT and (
        node.style.background_color is not None or node.style.border_radius is not None
    ):
        return node
    return None


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
                if _is_input_decorative_control(child):
                    if child.children and not walk(child.children):
                        return False
                    continue
                return False
            if child.children and not walk(child.children):
                return False
        return True

    return bool(node.children) and walk(node.children)


def _is_input_decorative_control(node: CleanDesignTreeNode) -> bool:
    """Icon-only ``BUTTON`` chrome inside a flex ``INPUT`` (calendar, chevron)."""
    if node.type != NodeType.BUTTON:
        return False
    return looks_like_input_trailing_icon_button(
        node
    ) or looks_like_compact_icon_action_button(node)


def input_value_style_node(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Return the prefilled value ``TEXT`` node inside a flex ``INPUT`` host."""
    chrome_ids = {id(item) for item in input_trailing_chrome_nodes(node)}
    hint = input_hint_node(node)
    hint_id = id(hint) if hint is not None else None
    candidates: list[CleanDesignTreeNode] = []

    def walk(children: list[CleanDesignTreeNode], skip: bool) -> None:
        for child in children:
            child_skip = skip or id(child) in chrome_ids
            if (
                child.type == NodeType.TEXT
                and not child_skip
                and child.text
                and id(child) != hint_id
            ):
                candidates.append(child)
            if child.children:
                walk(child.children, child_skip)

    walk(node.children, False)
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: len((item.text or "").strip()),
    )


def input_flex_value_text(node: CleanDesignTreeNode) -> str | None:
    """Concatenate value ``TEXT`` leaves inside a flex ``INPUT``, excluding icon chrome."""
    chrome_ids = {id(item) for item in input_trailing_chrome_nodes(node)}
    parts: list[str] = []

    def walk(children: list[CleanDesignTreeNode], skip: bool) -> None:
        for child in children:
            child_skip = skip or id(child) in chrome_ids
            if child.type == NodeType.TEXT and not child_skip and child.text:
                parts.append(child.text.strip())
            if child.children:
                walk(child.children, child_skip)

    walk(node.children, False)
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    return "".join(parts)


def input_trailing_chrome_nodes(node: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    """Return icon/vector subtrees that sit beside the value inside a flex ``INPUT``."""

    def collect(children: list[CleanDesignTreeNode]) -> None:
        for child in children:
            if child.type == NodeType.BUTTON and looks_like_input_trailing_icon_button(
                child
            ):
                chrome.append(child)
            elif child.type == NodeType.STACK and _stack_has_vector_icon(
                _descendant_nodes(child, _INPUT_TRAILING_ICON_DESCENDANT_DEPTH)
            ):
                chrome.append(child)
            elif child.type == NodeType.VECTOR and (
                child.vector_asset_key or child.style.has_stroke
            ):
                chrome.append(child)
            elif child.type in {NodeType.ROW, NodeType.COLUMN, NodeType.CONTAINER}:
                collect(child.children)

    chrome: list[CleanDesignTreeNode] = []
    collect(node.children)
    return chrome


def looks_like_input_trailing_icon_button(node: CleanDesignTreeNode) -> bool:
    """Small square icon ``BUTTON`` embedded at the end of a flex ``INPUT`` row."""
    if node.type != NodeType.BUTTON:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if not (14.0 <= width <= 28.0 and 14.0 <= height <= 28.0):
        return False
    return _stack_has_vector_icon(
        _descendant_nodes(node, _INPUT_TRAILING_ICON_DESCENDANT_DEPTH)
    )


def looks_like_compact_icon_action_button(node: CleanDesignTreeNode) -> bool:
    """Circular flex ``BUTTON`` frames that only host a chevron/close vector."""
    if node.type != NodeType.BUTTON:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if not (
        _COMPACT_ICON_ACTION_MIN <= width <= _COMPACT_ICON_ACTION_MAX + 28.0
        and _COMPACT_ICON_ACTION_MIN <= height <= _COMPACT_ICON_ACTION_MAX + 28.0
    ):
        return False
    return _stack_has_vector_icon(
        _descendant_nodes(node, _INPUT_TRAILING_ICON_DESCENDANT_DEPTH)
    )


_STROKE_AXIS_MIN_SPAN = 8.0
_STROKE_AXIS_MAX_THICKNESS = 2.5


def _vector_paint_span(node: CleanDesignTreeNode) -> tuple[float, float]:
    """Return stroke vector paint width/height, using paint bounds when layout size is zero."""
    width = float(node.sizing.width or 0.0)
    height = float(node.sizing.height or 0.0)
    frame = node.geometry_frame
    if frame is not None and frame.paint_rect is not None:
        if width <= 0:
            width = float(frame.paint_rect.width or 0.0)
        if height <= 0:
            height = float(frame.paint_rect.height or 0.0)
    return width, height


def looks_like_stroke_plus_icon(node: CleanDesignTreeNode) -> bool:
    """Return True when a square icon button hosts perpendicular stroke vectors (plus)."""
    if node.type != NodeType.BUTTON:
        return False
    vectors = [
        item
        for item in _descendant_nodes(node, _INPUT_TRAILING_ICON_DESCENDANT_DEPTH)
        if item.type == NodeType.VECTOR and item.style.has_stroke
    ]
    if len(vectors) < 2:
        return False
    horizontal = 0
    vertical = 0
    for vector in vectors:
        width, height = _vector_paint_span(vector)
        if height <= _STROKE_AXIS_MAX_THICKNESS and width >= _STROKE_AXIS_MIN_SPAN:
            horizontal += 1
        elif width <= _STROKE_AXIS_MAX_THICKNESS and height >= _STROKE_AXIS_MIN_SPAN:
            vertical += 1
    return horizontal >= 1 and vertical >= 1


def _stroke_icon_vectors(node: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    """Collect stroke vectors under a compact icon host."""
    return [
        item
        for item in _descendant_nodes(node, _INPUT_TRAILING_ICON_DESCENDANT_DEPTH)
        if item.type == NodeType.VECTOR and item.style.has_stroke
    ]


def _stroke_icon_size_expr(node: CleanDesignTreeNode) -> str:
    """Resolve Material icon size from a square icon button host."""
    from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal

    width = float(node.sizing.width or 0.0)
    height = float(node.sizing.height or 0.0)
    size = min(width, height) if width > 0 and height > 0 else 24.0
    size = max(min(size * 0.5, 24.0), 16.0)
    return format_geometry_literal(size)


def _stroke_icon_color_expr(
    vectors: list[CleanDesignTreeNode],
    *,
    host: CleanDesignTreeNode | None = None,
) -> str:
    from figma_flutter_agent.generator.layout.style import dart_color_expr

    if not vectors:
        return "Color(0xFF52525C)"
    for vector in vectors:
        color = dart_color_expr(
            vector.style,
            css_key="border-color",
            fallback="",
        )
        if "0xFFFFFFFF" in color.upper():
            return color
    if host is not None and host.style.background_color not in {
        None,
        "0xFFFFFFFF",
        "0xFFF6F6F2",
        "0xFFFCFBF8",
    }:
        return "Color(0xFFFFFFFF)"
    return dart_color_expr(
        vectors[0].style,
        css_key="border-color",
        fallback="0xFF52525C",
    )


def looks_like_stroke_minus_icon(node: CleanDesignTreeNode) -> bool:
    """Return True when an icon host contains a single horizontal stroke bar."""
    vectors = _stroke_icon_vectors(node)
    if len(vectors) != 1:
        return False
    width, height = _vector_paint_span(vectors[0])
    return height <= _STROKE_AXIS_MAX_THICKNESS and width >= _STROKE_AXIS_MIN_SPAN


def looks_like_stroke_close_icon(node: CleanDesignTreeNode) -> bool:
    """Return True when an icon host contains two small crossing stroke vectors."""
    vectors = _stroke_icon_vectors(node)
    if len(vectors) < 2:
        return False
    if looks_like_stroke_plus_icon(node):
        return False
    spans = [_vector_paint_span(vector) for vector in vectors]
    compact = [
        (width, height)
        for width, height in spans
        if width >= 5.0
        and height >= 5.0
        and width <= 16.0
        and height <= 16.0
    ]
    return len(compact) >= 2


def stroke_minus_icon_expr(node: CleanDesignTreeNode) -> str | None:
    """Material ``Icons.remove`` fallback for stroke-drawn minus affordances."""
    if not looks_like_stroke_minus_icon(node):
        return None
    vectors = _stroke_icon_vectors(node)
    color = _stroke_icon_color_expr(vectors, host=node)
    size = _stroke_icon_size_expr(node)
    return f"Icon(Icons.remove, color: {color}, size: {size})"


def stroke_close_icon_expr(node: CleanDesignTreeNode) -> str | None:
    """Material ``Icons.close`` fallback for stroke-drawn dismiss affordances."""
    if not looks_like_stroke_close_icon(node):
        return None
    vectors = _stroke_icon_vectors(node)
    color = _stroke_icon_color_expr(vectors, host=node)
    size = _stroke_icon_size_expr(node)
    return f"Icon(Icons.close, color: {color}, size: {size})"


def stroke_plus_icon_expr(node: CleanDesignTreeNode) -> str | None:
    """Material ``Icons.add`` fallback for stroke-drawn plus affordances."""
    if not looks_like_stroke_plus_icon(node):
        return None
    vectors = _stroke_icon_vectors(node)
    if not vectors:
        return None
    color = _stroke_icon_color_expr(vectors, host=node)
    size = _stroke_icon_size_expr(node)
    return f"Icon(Icons.add, color: {color}, size: {size})"


def looks_like_bottom_docked_sheet(node: CleanDesignTreeNode) -> bool:
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
    surface = primary_surface_node(node)
    if surface is not None:
        return surface
    if node.type not in {NodeType.BUTTON, NodeType.INPUT, NodeType.STACK}:
        return None
    if not (node.style.background_color or node.style.border_color):
        return None
    if not node.sizing.width or not node.sizing.height:
        return None
    return node


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


def is_link_text(text: str | None) -> bool:
    """Return True when ``text`` looks like a tappable inline link label."""
    if not text:
        return False
    label = text.strip().lower()
    if len(label) > 64:
        return False
    if "already have" in label or "don't have an account" in label:
        return True
    return any(hint in label for hint in _LINK_HINTS)


def looks_like_weekday_chip_stack(node: CleanDesignTreeNode) -> bool:
    """Return True for circular single-letter weekday selectors in a chip row."""
    if node.type != NodeType.STACK:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if not (_WEEKDAY_CHIP_MIN_SIZE <= float(width) <= _WEEKDAY_CHIP_MAX_SIZE):
        return False
    if not (_WEEKDAY_CHIP_MIN_SIZE <= float(height) <= _WEEKDAY_CHIP_MAX_SIZE):
        return False
    text_nodes = [item for item in _local_nodes(node, _MAX_LOCAL_DEPTH) if item.type == NodeType.TEXT]
    if len(text_nodes) != 1 or not text_nodes[0].text:
        return False
    label = text_nodes[0].text.strip().lower()
    return label in _WEEKDAY_CHIP_LABELS


def weekday_chip_label(node: CleanDesignTreeNode) -> str:
    """Return the weekday abbreviation shown on a chip stack."""
    for item in _local_nodes(node, _MAX_LOCAL_DEPTH):
        if item.type == NodeType.TEXT and item.text:
            return item.text.strip().upper()
    return ""


_TIME_WHEEL_PICKER_MIN_TEXT_COUNT = 8
_TIME_WHEEL_PICKER_MIN_HEIGHT = 120.0
_TIME_WHEEL_PICKER_MIN_WIDTH = 250.0


def looks_like_wheel_time_picker_stack(node: CleanDesignTreeNode) -> bool:
    """Return True when a stack subtree matches a scrollable hour/minute/period wheel."""
    if node.type != NodeType.STACK:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if float(width) < _TIME_WHEEL_PICKER_MIN_WIDTH or float(height) < _TIME_WHEEL_PICKER_MIN_HEIGHT:
        return False
    wheel_texts = _wheel_picker_text_nodes(node)
    return len(wheel_texts) >= _TIME_WHEEL_PICKER_MIN_TEXT_COUNT


def _wheel_picker_text_nodes(node: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    texts: list[CleanDesignTreeNode] = []
    for item in _descendant_nodes(node, 5):
        if item.type != NodeType.TEXT or not item.text:
            continue
        label = item.text.strip().upper()
        if label in {"AM", "PM"} or label.isdigit():
            texts.append(item)
    return texts


def weekday_chip_initially_selected(node: CleanDesignTreeNode) -> bool:
    """Infer selected state from dark fill on the chip surface."""
    for item in _local_nodes(node, _MAX_LOCAL_DEPTH):
        if item.type not in {NodeType.CONTAINER, NodeType.VECTOR}:
            continue
        color = item.style.background_color
        if color is not None and "3F414E" in color.upper():
            return True
    return False
