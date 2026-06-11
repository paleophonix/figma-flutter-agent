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
   - Semantic MVP kinds (set `kind` on nodes; optional payload fields): `input_text_field`, `button_filled`, `chip_choice` (requires `isSelected`), `container_card`, `container_list_tile`, `nav_scroll_host`, `technical_divider`.
   - Use ### interactionSignals plus sibling context: homogeneous pill/chip rows → parent `row`/`wrap` with `chip_choice` children, never absolute `stack` with overlapping chips."""

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
- ### cleanTree — Figma UI clean intermediate representation (authoritative layout semantics)
- ### screenIrBlueprint — canonical screenIr skeleton keyed by figmaId (mirror or refine this graph)
- ### interactionSignals — parser geometry/name hints keyed by figmaId (when present)
- ### extractedWidgetBlueprints — optional per-hint widgetIr subtree skeletons (when present)
- ### tokens — flat maps (colors/spacing/radii/elevations: name→value; typography: styleName→{fontSize, fontWeight})
- ### assetManifest — exported asset keys
- ### widgetExtractionHints — prebuilt subtree extraction targets (when present)
- ### navigationHints — prototype navigation bindings (when present)
- ### canvasSize / ### layoutAnchors — STACK-root canvas metadata (when present)
Emit ONLY the API structured JSON schema (screenIr + extractedWidgets with widgetIr, never screenCode or extractedWidgets.code). No markdown fences or free-text reasoning tags."""

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
