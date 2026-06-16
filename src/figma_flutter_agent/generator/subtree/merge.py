"""Merging LLM widgets with subtrees."""

from __future__ import annotations

import re
from pathlib import Path

from figma_flutter_agent.generator.subtree.spec import SubtreeWidgetResult, SubtreeWidgetSpec
from figma_flutter_agent.schemas import CleanDesignTreeNode

_SVG_ASSET_PATH_RE = re.compile(r"SvgPicture\.asset\(\s*['\"](?P<path>assets/[^'\"]+)['\"]")
_IMAGE_ASSET_PATH_RE = re.compile(r"Image\.asset\(\s*['\"](?P<path>assets/[^'\"]+)['\"]")
_WIDGET_CLASS_RE = re.compile(
    r"class\s+(?P<name>\w+)\s+extends\s+(?:StatelessWidget|StatefulWidget)\b"
)


def _extract_asset_paths(source: str) -> frozenset[str]:
    paths = {match.group("path") for match in _SVG_ASSET_PATH_RE.finditer(source)}
    paths.update(match.group("path") for match in _IMAGE_ASSET_PATH_RE.finditer(source))
    return frozenset(paths)


def _primary_public_widget_class_name(source: str) -> str | None:
    """Return the exported widget class, ignoring private layout helper widgets."""
    public_names = [
        match.group("name")
        for match in _WIDGET_CLASS_RE.finditer(source)
        if not match.group("name").startswith("_")
    ]
    if not public_names:
        return None
    widget_names = [name for name in public_names if name.endswith("Widget")]
    if widget_names:
        return widget_names[-1]
    return public_names[-1]


def _extract_widget_class_name(source: str) -> str | None:
    return _primary_public_widget_class_name(source)


def _rename_widget_class(source: str, old_class: str, new_class: str) -> str:
    """Rename a widget class without rewriting sibling references inside ``build``."""
    if old_class == new_class:
        return source
    class_match = re.search(
        rf"class\s+{re.escape(old_class)}\s+extends\s+(?:StatelessWidget|StatefulWidget)\b",
        source,
    )
    if class_match is None:
        return re.sub(rf"\b{re.escape(old_class)}\b", new_class, source)
    build_match = re.search(
        r"@override\s+Widget\s+build\s*\(",
        source[class_match.end() :],
    )
    if build_match is None:
        return re.sub(rf"\b{re.escape(old_class)}\b", new_class, source)
    header_end = class_match.end() + build_match.start()
    header = source[:header_end]
    body = source[header_end:]
    return re.sub(rf"\b{re.escape(old_class)}\b", new_class, header) + body


def _collect_widget_class_names(
    planned_files: dict[str, str],
    *,
    exclude_paths: frozenset[str] | None = None,
) -> set[str]:
    excluded = exclude_paths or frozenset()
    names: set[str] = set()
    for path, content in planned_files.items():
        if path in excluded:
            continue
        if not path.startswith("lib/widgets/") or not path.endswith(".dart"):
            continue
        class_name = _extract_widget_class_name(content)
        if class_name is not None:
            names.add(class_name)
    return names


def _resolve_merged_widget_class_name(
    *,
    llm_class: str,
    subtree_class: str,
    spec_class: str | None,
    used_class_names: set[str],
) -> str:
    for candidate in (llm_class, spec_class or "", subtree_class):
        if candidate and candidate not in used_class_names:
            return candidate
    base = spec_class or llm_class or subtree_class
    suffix = 2
    while f"{base}{suffix}" in used_class_names:
        suffix += 1
    return f"{base}{suffix}"


def merge_thin_llm_widgets_with_subtrees(
    planned_files: dict[str, str],
    subtree_result: SubtreeWidgetResult,
) -> dict[str, str]:
    """Replace under-specified LLM extracted widgets with deterministic subtree bodies."""
    if not subtree_result.files:
        return planned_files

    updated = dict(planned_files)
    spec_by_path = {f"lib/widgets/{spec.file_name}.dart": spec for spec in subtree_result.specs}
    subtree_assets = {
        path: _extract_asset_paths(content) for path, content in subtree_result.files.items()
    }

    from figma_flutter_agent.generator.dart.llm_codegen import validate_dart_delimiters

    for path, llm_content in list(updated.items()):
        if not path.startswith("lib/widgets/") or not path.endswith(".dart"):
            continue

        llm_assets = _extract_asset_paths(llm_content)
        llm_syntax_broken = validate_dart_delimiters(llm_content) is not None
        if not llm_assets:
            continue

        best_path: str | None = None
        best_score = 0.0
        best_assets: frozenset[str] = frozenset()
        for subtree_path, assets in subtree_assets.items():
            if not assets:
                continue
            overlap = len(llm_assets & assets)
            if overlap == 0:
                continue
            score = overlap / len(llm_assets)
            if score > best_score:
                best_score = score
                best_path = subtree_path
                best_assets = assets

        if llm_syntax_broken and best_path is None:
            stem = Path(path).stem
            for candidate in (stem, f"{stem}_2", stem.removesuffix("_2")):
                candidate_path = f"lib/widgets/{candidate}.dart"
                if candidate_path in subtree_result.files:
                    best_path = candidate_path
                    best_assets = subtree_assets.get(candidate_path, frozenset())
                    best_score = 1.0
                    break

        if best_path is None or (best_score < 0.5 and not llm_syntax_broken):
            continue

        spec = spec_by_path.get(best_path)
        if not llm_syntax_broken and spec is not None and len(llm_assets) >= spec.vector_count:
            continue
        llm_assets_are_proper_subset = (
            not llm_syntax_broken
            and bool(best_assets)
            and bool(llm_assets)
            and llm_assets < best_assets
            and best_score >= 1.0
        )
        if (
            not llm_assets_are_proper_subset
            and not llm_syntax_broken
            and spec is None
            and len(llm_assets) >= len(best_assets) * 0.6
        ):
            continue

        llm_class = _extract_widget_class_name(llm_content)
        subtree_class = _extract_widget_class_name(subtree_result.files[best_path])
        if llm_class is None or subtree_class is None:
            continue

        spec = spec_by_path.get(best_path)
        target_class = _resolve_merged_widget_class_name(
            llm_class=llm_class,
            subtree_class=subtree_class,
            spec_class=spec.class_name if spec is not None else None,
            used_class_names=_collect_widget_class_names(updated, exclude_paths=frozenset({path})),
        )
        merged = _rename_widget_class(subtree_result.files[best_path], subtree_class, target_class)
        updated[path] = merged

    for subtree_path, subtree_content in subtree_result.files.items():
        if subtree_path not in updated:
            continue
        current = updated[subtree_path]
        if current == subtree_content:
            continue
        llm_class = _extract_widget_class_name(current)
        subtree_class = _extract_widget_class_name(subtree_content)
        if llm_class is None or subtree_class is None:
            updated[subtree_path] = subtree_content
            continue
        spec = spec_by_path.get(subtree_path)
        target_class = _resolve_merged_widget_class_name(
            llm_class=llm_class,
            subtree_class=subtree_class,
            spec_class=spec.class_name if spec is not None else None,
            used_class_names=_collect_widget_class_names(
                updated,
                exclude_paths=frozenset({subtree_path}),
            ),
        )
        updated[subtree_path] = _rename_widget_class(subtree_content, subtree_class, target_class)

    return updated


def replace_extracted_subtree_nodes_with_refs(
    root: CleanDesignTreeNode,
    specs: list[SubtreeWidgetSpec],
) -> None:
    """Swap extracted subtree roots for placement stubs consumed by layout codegen."""
    by_id = {spec.node_id: spec.class_name for spec in specs}
    if not by_id:
        return

    def stub_for(node: CleanDesignTreeNode, class_name: str) -> CleanDesignTreeNode:
        return node.model_copy(update={"extracted_widget_ref": class_name})

    from figma_flutter_agent.parser.interaction import must_inline_extracted_widget_host

    def walk(node: CleanDesignTreeNode) -> None:
        kept: list[CleanDesignTreeNode] = []
        for child in node.children:
            class_name = by_id.get(child.id)
            if class_name is not None and not must_inline_extracted_widget_host(child):
                kept.append(stub_for(child, class_name))
                continue
            walk(child)
            kept.append(child)
        node.children = kept

    walk(root)


def _planned_widget_specs(
    planned_files: dict[str, str],
) -> list[tuple[str, frozenset[str], int]]:
    specs: list[tuple[str, frozenset[str], int]] = []
    for path, content in planned_files.items():
        if not path.startswith("lib/widgets/") or not path.endswith(".dart"):
            continue
        class_name = _extract_widget_class_name(content)
        assets = _extract_asset_paths(content)
        if class_name is None or not assets:
            continue
        specs.append((class_name, assets, len(assets)))
    specs.sort(key=lambda item: item[2], reverse=True)
    return specs


def _collect_node_asset_keys(node: CleanDesignTreeNode) -> frozenset[str]:
    keys: set[str] = set()
    if node.vector_asset_key:
        keys.add(node.vector_asset_key)
    if node.image_asset_key:
        keys.add(node.image_asset_key)
    for child in node.children:
        keys.update(_collect_node_asset_keys(child))
    return frozenset(keys)


def _find_best_tree_node_for_assets(
    root: CleanDesignTreeNode,
    widget_assets: frozenset[str],
) -> CleanDesignTreeNode | None:
    """Return the clean-tree subtree that best matches a planned widget asset set."""
    if not widget_assets:
        return None
    ranked: list[tuple[float, CleanDesignTreeNode]] = []
    for node in _collect_all_nodes(root):
        node_assets = _collect_node_asset_keys(node)
        if not node_assets:
            continue
        overlap = len(node_assets & widget_assets)
        if overlap == 0:
            continue
        score = overlap / len(widget_assets)
        if score < 0.4:
            continue
        ranked.append((score, node))
    if not ranked:
        return None
    ranked.sort(key=lambda item: item[0], reverse=True)
    for _, node in ranked:
        if node.stack_placement is not None:
            return node
    return ranked[0][1]


def _collect_all_nodes(root: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    nodes = [root]
    for child in root.children:
        nodes.extend(_collect_all_nodes(child))
    return nodes
