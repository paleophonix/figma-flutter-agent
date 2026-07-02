"""L6 prompt environment templates."""

from __future__ import annotations

# L6:ENVIRONMENT
# ---------------------------------------------------------------------------

# --- generate ---
_L5_SCREEN_IR_ARCHITECTURE = """7. SCREEN IR ARCHITECTURE (replaces Dart screenCode emission):
   - Populate `screenIr.root` to mirror ### cleanTree structure: every included node needs `figmaId` + `children`.
   - Start from ### screenIrBlueprint when present; adjust children order, `omitFigmaIds`, `stateByFigmaId`, `adaptiveRules`, or `extracted` refs — do not invent ids.
   - Preserve `stateByFigmaId` entries from the blueprint (default/disabled/loading/selected/error). Use `adaptiveRules` only for viewport- or state-conditioned `overrides`/`wrap` on existing figmaIds.
   - Map ### widgetExtractionHints to `kind: "extracted"` nodes with `ref.widgetName` (PascalCase).
   - For each extracted widget, emit `extractedWidgets[]` with `widgetName` + `widgetIr` rooted at the subtree `figmaId` (see ### extractedWidgetBlueprints). No Dart in `code`.
   - The compiler emits Dart, flex wrappers, and Positioned pins — you supply structure only.
   - Leave `kind: "auto"` on nodes — the deterministic semantic classifier assigns widget kinds after layout passes.
   - Never set `screenIr.root.kind` to `nav_bottom_bar` when ### cleanTree root is a full-screen frame (height above ~160px or many children). Reserve `nav_bottom_bar` for compact dock hosts (`BOTTOM_NAV` or short bottom bars), not screen titles containing "navigation".
   - Optional grey-zone hints only: `classificationHint` with `suggestedKind` + `confidence` (0.5–0.8); never authoritative.
   - `classificationHint.suggestedKind` MUST use WidgetIrKind slugs (e.g. `chip_choice`, `input_rating`, `input_text_field`) — NEVER contractKind values such as `choice_chip_group` or `rating_input`.
   - Use ### interactionSignals for structure (chip rows, inputs, nav) without assigning semantic kinds yourself.
8. SEMANTIC ADJUDICATION (report-only, part of the same IR extraction call — not repair):
   - Use ### cleanTree as authoritative for semantic judgement; ### treeOutline, ### textInventory, ### componentInventory, and ### relationshipHints are navigation aids only.
   - Emit `screenIr.semanticSummary` and `screenIr.semanticVerdicts` alongside the normal IR graph. Do not invent text, geometry, colors, asset paths, component refs, or node ids.
   - Each `semanticVerdicts[]` entry must cite existing `nodeId`s from ### cleanTree. Prefer `contractKind: unknown` when uncertain.
   - Do NOT emit throwaway role-only labels. Each verdict must identify the future **control contract shape**: boundary/control nodes, label/placeholder/value/option/state node ids, `contractKind`, `contractTraits`, `proposedLayoutLaws`, and `proposedEffects`.
   - `contractKind` examples: text_input, textarea, password_input, search_input, button, choice_chip_group, rating_input, navigation_bar, system_chrome, unknown.
   - For text inputs: report boundary vs label vs placeholder vs value nodes; set traits such as `is_multiline`, `max_lines`, `obscureText` (password fields), `keyboard_intent`; propose layout laws (e.g. `single_line_input_vertical_center` vs `multiline_input_top_align`).
   - For social/auth buttons: set `contractTraits.socialProvider` (e.g. google, facebook) when the control is a branded provider button.
   - For ratings: set `contractTraits.rating_value` from component variant when visible; propose `rating_value_from_component_variant`.
   - For chip groups: list `optionNodeIds` / options; propose `selected_chip_state_preserved` when selection state is visible.
   - `proposedLayoutLaws` and `proposedEffects` are suggestions only — compiler/emitter ignore them in this pipeline."""

_L6_GENERATE_USER_CONTRACT = """Structured compiler input is supplied in the user message under labeled ### sections (not duplicated in this system prompt):
- ### featureName — target feature slug
- ### cleanTree — Figma UI clean intermediate representation (authoritative layout semantics)
- ### tokens — flat maps (colors/spacing/radii/elevations: name→value; typography: styleName→{fontSize, fontWeight})
- ### assetManifest — exported asset keys
- ### widgetExtractionHints — prebuilt subtree extraction targets (when present)
- ### navigationHints — prototype navigation bindings (when present)
- ### canvasSize / ### layoutAnchors — STACK-root canvas metadata (when present)
- ### responsiveLayoutEnabled — responsive shell flag (when present)
Read those sections as the only source of Figma matrices. Emit ONLY the API structured JSON schema (screenCode + extractedWidgets). No markdown fences or free-text reasoning tags."""

_L6_GENERATE_USER_CONTRACT_IR = """Structured compiler input is supplied in the user message under labeled ### sections (not duplicated in this system prompt):
- ### featureName — target feature slug
- ### cleanTree — slim authoritative Figma UI clean tree for layout and semantic judgement
- ### treeOutline — compact node outline (navigation aid only)
- ### textInventory — visible TEXT nodes in visual order (navigation aid only)
- ### componentInventory — component instance metadata (navigation aid only)
- ### relationshipHints — structural/spatial links only (navigation aid only)
- ### screenIrBlueprint — canonical screenIr skeleton keyed by figmaId (mirror or refine this graph)
- ### interactionSignals — parser geometry/name hints keyed by figmaId (when present)
- ### extractedWidgetBlueprints — optional per-hint widgetIr subtree skeletons (when present)
- ### tokens — flat maps (colors/spacing/radii/elevations: name→value; typography: styleName→{fontSize, fontWeight})
- ### assetManifest — exported asset keys
- ### widgetExtractionHints — prebuilt subtree extraction targets (when present)
- ### navigationHints — prototype navigation bindings (when present)
- ### canvasSize / ### layoutAnchors — STACK-root canvas metadata (when present)
Use ### cleanTree as authoritative for semantic annotations; compact inventory sections are navigation aids only. Do not generate Flutter/Dart code.
Emit ONLY the API structured JSON schema (screenIr with optional semanticSummary/semanticVerdicts + extractedWidgets with widgetIr, never screenCode or extractedWidgets.code). Semantic verdicts must be contract-oriented (control/boundary/label/placeholder/value/option node ids, contractKind, contractTraits, proposedLayoutLaws, proposedEffects) — not role-only labels. No markdown fences or free-text reasoning tags."""

# --- repair ---
_REPAIR_L6_TEMPLATE = """You operate on a line-numbered isolated Dart file context under the following runtime bindings:
- Active Analyzer Errors:
$analyzeErrors
- Line-Numbered Target Source Code:
$code
- Figma Structural Intent Metadata:
$semanticHint
- Execution Block History:
$failedAttemptsHistory
- Immutable Scope Boundaries:
$unchangedWidgetNames
- CPI Supervisor Pattern Interrupt (mandatory when not "(none)"):
$cpiSupervisorDirective
- Repair Loop Escalation (mandatory — obey before patching):
$repairEscalationBlock
- User-Labeled Repair Scope (repairTargets, featureName): supplied in the user message under ### sections."""

_ESCALATED_REPAIR_L6_EXTRA = """- Escalation Level: $escalationLevel / $loopAttempt
- Primary Target File: $targetFile
- Tactical Directive:
$tacticalDirective"""

# --- cpi ---
_CPI_L6_TEMPLATE = """You monitor the runtime trajectory of the repair cycle with access to the following historical metrics:
- Executed Repetitive Patches:
$lastPatches
- Recurrent Static Analysis Failures:
$recurringErrors
- Baseline Layout Component Contract:
$figmaNodeIntent"""
