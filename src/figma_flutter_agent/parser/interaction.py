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
    }
)
_MAX_CONTROL_HEIGHT = 120.0
_MAX_CONTROL_CHILDREN = 8
_MAX_LOCAL_DEPTH = 2


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
    """Small bordered square used as a consent checkbox in classic layouts."""
    if node.type not in {NodeType.CONTAINER, NodeType.STACK}:
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


def looks_like_back_nav_stack(node: CleanDesignTreeNode) -> bool:
    """Circular icon affordance (back, close, favorite, download)."""
    if node.type != NodeType.STACK:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if not (44.0 <= width <= 64.0 and 44.0 <= height <= 64.0):
        return False
    local_nodes = _local_nodes(node, _MAX_LOCAL_DEPTH)
    has_icon = any(
        item.vector_asset_key
        or item.type == NodeType.VECTOR
        or (item.name or "").lower().startswith("vector")
        for item in local_nodes
    )
    return _has_circular_container(local_nodes) and has_icon


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
    for text_node in _local_nodes(node, _MAX_LOCAL_DEPTH):
        if text_node.type != NodeType.TEXT or not text_node.text:
            continue
        label = text_node.text.strip()
        if label.isdigit() and len(label) <= 2:
            return True
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


def _stack_spans_primary_button_and_footer_link(
    node: CleanDesignTreeNode,
    *,
    text_nodes: list[CleanDesignTreeNode],
) -> bool:
    """True when a tall stack pairs a CTA surface with a separate footer link row."""
    surface = primary_surface_node(node)
    stack_height = node.sizing.height
    if surface is None or stack_height is None:
        return False
    surface_height = float(surface.sizing.height or 0)
    if stack_height <= surface_height + 16.0:
        return False
    has_action = any(
        any(hint in (item.text or "").lower() for hint in _ACTION_HINTS) for item in text_nodes
    )
    has_footer = any(
        is_link_text(item.text) or "already have" in (item.text or "").lower()
        for item in text_nodes
    )
    return has_action and has_footer and len(text_nodes) >= 2


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
)


def is_link_text(text: str | None) -> bool:
    """Return True when ``text`` looks like a tappable inline link label."""
    if not text:
        return False
    label = text.strip().lower()
    if len(label) > 64:
        return False
    return any(hint in label for hint in _LINK_HINTS)
