"""Design coverage metrics: Figma interactive nodes vs generated Dart bindings."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from loguru import logger

from figma_flutter_agent.generator.custom_code_zones import legacy_role_from_zone
from figma_flutter_agent.generator.figma_anchor import figma_key_token
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_INTERACTIVE_TYPES = frozenset(
    {
        NodeType.BUTTON,
        NodeType.INPUT,
        NodeType.CHECKBOX,
        NodeType.SWITCH,
        NodeType.RADIO,
        NodeType.SLIDER,
        NodeType.DROPDOWN,
        NodeType.BOTTOM_NAV,
        NodeType.TABS,
    }
)

_VALUE_KEY_RE = re.compile(r"ValueKey(?:<[^>]+>)?\(\s*['\"]figma-([^'\"]+)['\"]\s*\)")
_BLOCK_ZONE_RE = re.compile(
    r"//\s*<\s*custom-code:([\w.:+-]+)\s*>\s*\n(?P<body>.*?)//\s*</\s*custom-code:\1\s*>",
    re.DOTALL,
)
_INLINE_ZONE_RE = re.compile(r"/\*\s*<custom-code:([\w.:+-]+)>\s*\*/")


def _collect_interactive_nodes(root: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    nodes: list[CleanDesignTreeNode] = []

    def walk(node: CleanDesignTreeNode) -> None:
        if node.type in _INTERACTIVE_TYPES:
            nodes.append(node)
        for child in node.children:
            walk(child)

    walk(root)
    return nodes


def _dart_sources(planned_dart: Mapping[str, str]) -> str:
    return "\n".join(
        content for path, content in planned_dart.items() if path.endswith(".dart")
    )


def _figma_keys_in_dart(source: str) -> set[str]:
    return {figma_key_token(token.replace("_", ":")) for token in _VALUE_KEY_RE.findall(source)}


def _custom_code_zones(source: str) -> dict[str, str]:
    zones: dict[str, str] = {}
    for match in _BLOCK_ZONE_RE.finditer(source):
        zones[match.group(1)] = match.group("body").strip()
    for match in _INLINE_ZONE_RE.finditer(source):
        zones.setdefault(match.group(1), "")
    return zones


def build_design_coverage_report(
    clean_tree: CleanDesignTreeNode,
    planned_dart: Mapping[str, str],
) -> dict[str, Any]:
    """Build coverage metrics for interactive nodes and Dart bindings.

    Args:
        clean_tree: Parsed design tree.
        planned_dart: Project-relative planned Dart paths to contents.

    Returns:
        JSON-serializable coverage summary.
    """
    interactive = _collect_interactive_nodes(clean_tree)
    source = _dart_sources(planned_dart)
    keys = _figma_keys_in_dart(source)
    zones = _custom_code_zones(source)

    covered_by_key: list[str] = []
    uncovered_interactive: list[dict[str, str]] = []
    for node in interactive:
        token = figma_key_token(node.id)
        if token in keys:
            covered_by_key.append(node.id)
        else:
            uncovered_interactive.append({"id": node.id, "type": node.type.value})

    zones_with_body = [name for name, body in zones.items() if body.strip()]
    orphan_keys = sorted(key for key in keys if not any(figma_key_token(n.id) == key for n in interactive))

    legacy_zones = [name for name in zones if legacy_role_from_zone(name) and not name.startswith("figma-")]

    layout_source = ""
    for path, content in planned_dart.items():
        if path.replace("\\", "/").startswith("lib/generated/") and path.endswith("_layout.dart"):
            layout_source = content
            break
    emit_contract_gaps: dict[str, int] = {}
    geometry_invariant_soft: dict[str, int] = {}
    if layout_source.strip():
        from figma_flutter_agent.generator.emit_fidelity_audit import count_emit_contract_gaps
        from figma_flutter_agent.generator.geometry.invariants.reporting import (
            count_violations_by_code,
            partition_geometry_violations,
        )
        from figma_flutter_agent.generator.geometry.invariants.validate import (
            validate_geometry_invariants,
        )

        emit_contract_gaps = count_emit_contract_gaps(clean_tree, layout_source)
        violations = validate_geometry_invariants(
            clean_tree,
            layout_source=layout_source,
        )
        _, soft = partition_geometry_violations(violations)
        geometry_invariant_soft = count_violations_by_code(soft)

    return {
        "interactiveNodeCount": len(interactive),
        "valueKeyCount": len(keys),
        "interactiveWithValueKey": len(covered_by_key),
        "uncoveredInteractive": uncovered_interactive,
        "customCodeZoneCount": len(zones),
        "customCodeZonesWithBody": zones_with_body,
        "legacyRoleOnlyZones": legacy_zones,
        "orphanValueKeys": orphan_keys,
        "emitContractGaps": emit_contract_gaps,
        "geometryInvariantSoft": geometry_invariant_soft,
    }


def write_design_coverage_report(
    project_dir: Path,
    *,
    feature_slug: str,
    root: CleanDesignTreeNode,
    planned_dart: Mapping[str, str],
) -> Path | None:
    """Write design coverage JSON under ``.debug/reports``."""
    report_dir = project_dir / ".debug" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = build_design_coverage_report(root, planned_dart)
    path = report_dir / f"{feature_slug}_design_coverage.json"
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    logger.info("Wrote design coverage report to {}", path.as_posix())
    return path
