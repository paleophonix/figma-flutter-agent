"""Screen-name-agnostic emit contract audit (FID-26)."""

from __future__ import annotations

from dataclasses import dataclass

from figma_flutter_agent.generator.layout.style import should_emit_strut_style
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


@dataclass(frozen=True)
class EmitContractViolation:
    """One dropped or inverted emit contract."""

    code: str
    node_id: str
    detail: str


def _walk_nodes(root: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    out: list[CleanDesignTreeNode] = []

    def visit(node: CleanDesignTreeNode) -> None:
        out.append(node)
        for child in node.children:
            visit(child)

    visit(root)
    return out


def _figma_key_token(node_id: str) -> str:
    return f"figma-{node_id.replace(':', '_')}"


def _emit_snippet_for_node(emit_source: str, node_id: str, *, radius: int = 420) -> str:
    token = _figma_key_token(node_id)
    index = emit_source.find(token)
    if index < 0:
        return ""
    start = max(0, index - radius)
    end = min(len(emit_source), index + radius)
    return emit_source[start:end]


def _layer_blur_hosts_missing_backdrop(
    root: CleanDesignTreeNode,
    emit_source: str,
) -> list[EmitContractViolation]:
    violations: list[EmitContractViolation] = []
    for node in _walk_nodes(root):
        blur = _effective_backdrop_blur_radius(node)
        if blur is None:
            continue
        if node.type not in {NodeType.COLUMN, NodeType.ROW, NodeType.STACK, NodeType.CONTAINER}:
            continue
        snippet = _emit_snippet_for_node(emit_source, node.id)
        if snippet and "BackdropFilter" in snippet:
            continue
        violations.append(
            EmitContractViolation(
                code="layer_blur_missing_backdrop",
                node_id=node.id,
                detail=f"backdropBlur={blur} on flex/frame host without BackdropFilter in emit",
            )
        )
    return violations


def _effective_backdrop_blur_radius(node: CleanDesignTreeNode) -> float | None:
    if node.style.background_blur is not None and node.style.background_blur > 0:
        return node.style.background_blur
    if (
        node.style.layer_blur is not None
        and node.style.layer_blur > 0
        and node.type in {NodeType.COLUMN, NodeType.ROW, NodeType.STACK, NodeType.CONTAINER}
    ):
        return node.style.layer_blur
    return None


def _bottom_pins_using_top(
    root: CleanDesignTreeNode,
    emit_source: str,
    *,
    viewport_height: float | None,
) -> list[EmitContractViolation]:
    violations: list[EmitContractViolation] = []
    for node in _walk_nodes(root):
        placement = node.stack_placement
        if placement is None or placement.vertical != "BOTTOM":
            continue
        snippet = _emit_snippet_for_node(emit_source, node.id)
        if not snippet:
            continue
        if "bottom:" in snippet:
            continue
        if "top:" not in snippet:
            continue
        violations.append(
            EmitContractViolation(
                code="bottom_pin_used_top",
                node_id=node.id,
                detail=(
                    f"vertical=BOTTOM but emit uses top pin "
                    f"(viewport_height={viewport_height})"
                ),
            )
        )
    return violations


def _opacity_hosts_missing_wrapper(
    root: CleanDesignTreeNode,
    emit_source: str,
) -> list[EmitContractViolation]:
    violations: list[EmitContractViolation] = []
    for node in _walk_nodes(root):
        opacity = node.style.opacity
        if opacity is None or opacity >= 1.0 - 1e-6:
            continue
        snippet = _emit_snippet_for_node(emit_source, node.id)
        if not snippet:
            continue
        if "Opacity(" in snippet:
            continue
        violations.append(
            EmitContractViolation(
                code="opacity_missing_wrapper",
                node_id=node.id,
                detail=f"opacity={opacity} without Opacity() wrapper near node emit",
            )
        )
    return violations


def _text_missing_strut_style(
    root: CleanDesignTreeNode,
    emit_source: str,
) -> list[EmitContractViolation]:
    violations: list[EmitContractViolation] = []
    for node in _walk_nodes(root):
        if node.type != NodeType.TEXT:
            continue
        if not should_emit_strut_style(node.style):
            continue
        snippet = _emit_snippet_for_node(emit_source, node.id)
        if not snippet:
            continue
        if "StrutStyle" in snippet:
            continue
        violations.append(
            EmitContractViolation(
                code="line_height_missing_strut",
                node_id=node.id,
                detail="TEXT with line-box metrics without StrutStyle in emit snippet",
            )
        )
    return violations


def _vector_layer_blur_missing_image_filter(
    root: CleanDesignTreeNode,
    emit_source: str,
) -> list[EmitContractViolation]:
    violations: list[EmitContractViolation] = []
    for node in _walk_nodes(root):
        blur = node.style.layer_blur
        if blur is None or blur <= 0 or node.type != NodeType.VECTOR:
            continue
        snippet = _emit_snippet_for_node(emit_source, node.id)
        if not snippet:
            continue
        if "ImageFiltered" in snippet:
            continue
        violations.append(
            EmitContractViolation(
                code="vector_blur_missing_image_filter",
                node_id=node.id,
                detail=f"layer_blur={blur} on VECTOR without ImageFiltered in emit",
            )
        )
    return violations


def audit_emit_contracts(
    root: CleanDesignTreeNode,
    emit_source: str,
    *,
    viewport_height: float | None = None,
) -> list[EmitContractViolation]:
    """Return emit contract gaps for CI gates and design-coverage reports."""
    height = viewport_height
    if height is None:
        height = root.sizing.height
    violations: list[EmitContractViolation] = []
    violations.extend(_layer_blur_hosts_missing_backdrop(root, emit_source))
    violations.extend(_text_missing_strut_style(root, emit_source))
    violations.extend(_vector_layer_blur_missing_image_filter(root, emit_source))
    violations.extend(_bottom_pins_using_top(root, emit_source, viewport_height=height))
    violations.extend(_opacity_hosts_missing_wrapper(root, emit_source))
    return violations


def count_emit_contract_gaps(
    root: CleanDesignTreeNode,
    emit_source: str,
    *,
    viewport_height: float | None = None,
) -> dict[str, int]:
    """Aggregate violation counts by contract code (FID-26)."""
    counts: dict[str, int] = {}
    for item in audit_emit_contracts(
        root,
        emit_source,
        viewport_height=viewport_height,
    ):
        counts[item.code] = counts.get(item.code, 0) + 1
    return counts


def assert_emit_contracts_clean(
    root: CleanDesignTreeNode,
    emit_source: str,
    *,
    viewport_height: float | None = None,
) -> None:
    """Fail when any universal emit contract is violated."""
    violations = audit_emit_contracts(
        root,
        emit_source,
        viewport_height=viewport_height,
    )
    if not violations:
        return
    summary = "; ".join(f"{v.code}@{v.node_id}" for v in violations[:8])
    extra = len(violations) - 8
    suffix = f" (+{extra} more)" if extra > 0 else ""
    raise AssertionError(f"Emit contract gaps: {summary}{suffix}")
