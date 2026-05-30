"""Run IR guardrails across offline screen fixtures (bulk AC-1/AC-2 gate)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.fixtures.screens_manifest import (
    ScreenFixtureEntry,
    load_layout_tree,
    load_screens_manifest,
)
from figma_flutter_agent.generator.ir_presence import ensure_presence_subtrees_in_screen_ir
from figma_flutter_agent.generator.ir_tree import default_screen_ir
from figma_flutter_agent.generator.ir_validate import apply_ir_guards, validate_screen_ir
from figma_flutter_agent.generator.subtree_widgets import (
    _should_insert_missing_subtree,
    collect_subtree_widget_specs,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, ScreenIr, WidgetIrNode


@dataclass(frozen=True)
class FixtureIrValidationResult:
    """Outcome of validating one manifest screen through the IR pipeline."""

    screen_id: str
    ok: bool
    error: str | None = None


def validate_fixture_screen_ir(
    entry: ScreenFixtureEntry,
    *,
    apply_guards: bool = True,
    validate: bool = True,
    tree: CleanDesignTreeNode | None = None,
) -> FixtureIrValidationResult:
    """Build default IR for a fixture layout and run guardrails + validation."""
    root = tree if tree is not None else load_layout_tree(entry)
    screen_ir = default_screen_ir(root)
    screen_ir = ensure_presence_subtrees_in_screen_ir(screen_ir, root)
    try:
        if apply_guards:
            apply_ir_guards(screen_ir, root)
        if validate:
            validate_screen_ir(
                screen_ir,
                root,
                apply_guards=False,
            )
        _validate_presence_subtrees_in_ir(screen_ir, root)
    except GenerationError as exc:
        return FixtureIrValidationResult(
            screen_id=entry.id,
            ok=False,
            error=str(exc),
        )
    return FixtureIrValidationResult(screen_id=entry.id, ok=True)


def _ir_figma_ids(root: WidgetIrNode) -> set[str]:
    ids: set[str] = set()

    def walk(node: WidgetIrNode) -> None:
        ids.add(node.figma_id)
        for child in node.children:
            walk(child)

    walk(root)
    return ids


def _validate_presence_subtrees_in_ir(screen_ir: ScreenIr, root: CleanDesignTreeNode) -> None:
    """Fail when a large deterministic subtree is absent from the default IR graph."""
    present = _ir_figma_ids(screen_ir.root)
    for spec in collect_subtree_widget_specs(root, widget_suffix="Widget"):
        if not _should_insert_missing_subtree(spec):
            continue
        if spec.node_id in present:
            continue
        raise GenerationError(
            f"fixture {root.id!r}: large subtree {spec.class_name} "
            f"(figmaId={spec.node_id}) missing from default screen IR after presence merge"
        )


def validate_all_fixture_screens(
    *,
    screen_ids: list[str] | None = None,
    apply_guards: bool = True,
    validate: bool = True,
    manifest_path: Path | None = None,
) -> list[FixtureIrValidationResult]:
    """Validate every (or selected) entry in ``tests/fixtures/screens.yaml``."""
    manifest = load_screens_manifest(manifest_path)
    entries = manifest.screens
    if screen_ids is not None:
        wanted = frozenset(screen_ids)
        entries = [entry for entry in entries if entry.id in wanted]
    return [
        validate_fixture_screen_ir(
            entry,
            apply_guards=apply_guards,
            validate=validate,
        )
        for entry in entries
    ]
