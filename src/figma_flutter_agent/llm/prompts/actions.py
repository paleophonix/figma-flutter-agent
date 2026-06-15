"""L5 prompt actions."""

from __future__ import annotations

# L5:ACTIONS
# ---------------------------------------------------------------------------

# --- generate ---
_L5_GENERATE_MATERIAL = """1. PRE-COMPILATION: Read the ### cleanTree user section; map every node to a widget type (RichText when textSpans is non-empty). Emit only schema-valid JSON.
2. LAYOUT COMPILATION & DEPTH MINIMIZATION:
   - Use `Row`, `Column`, and `Wrap` for adaptive layouts. Avoid `Stack`/`Positioned` unless the node type is explicitly `STACK`.
   - Flex layouts default to `CrossAxisAlignment.start` and `MainAxisAlignment.start`. Map absolute alignment fields to `AlignmentDirectional.centerStart` or `Alignment.centerLeft` inside an `Align` widget — NEVER emit 'Alignment.start'.
   - Positioned Stack Elements Budget: Enforce a maximum of two horizontal pins (left/width or left/right) and two vertical pins (top/height). Never mix left, right, and width simultaneously.
3. SCROLLABLE & VIEWPORT RECAPPING:
   - Implement `ListView.builder` or `GridView.builder` for linear collection repetitions. Never drop scrollable viewports into a Column without wrapping them inside `Expanded` or `Flexible`.
   - Text elements inside a horizontal `Row` MUST be wrapped in `Flexible` or `Expanded` to block RenderFlex overflow.
4. TYPOGRAPHY & TEXT CLIPPING DEFIANCE:
   - Never wrap `Text` in fixed-height containers; use dynamic padding for proper `textScaler` compatibility.
   - For single-line text elements positioned absolutely, do NOT specify a tight `width`. Specify ONLY `left` (and optional margins) to allow natural text expansion. If width is mandatory, buffer it by +20% to +30% to prevent character clipping.
   - CONDITIONAL TEXT DISPATCH: If a text node contains a non-empty `textSpans` array, you MUST compile it using `RichText` or `Text.rich`. Flat `Text()` constructors for span trees are illegal.
5. BACKGROUND & DECORATIVE ASSET INTEGRITY:
   - Never approximate complex SVG paths with standard Containers or BoxDecorations. Render the original `vectorAssetKey` or `imageAssetKey` via `SvgPicture.asset`/`Image.asset`.
   - SCREEN FRAME ASSET BAN: Never attach background assets to the root screen node. Background graphics must originate from dedicated child nodes.
   - AMBIENT BACKGROUND RESPONSIVENESS: Group decorative background elements behind a centered layout into a dedicated background Stack wrapped in: `Positioned.fill(child: FittedBox(fit: BoxFit.cover, clipBehavior: Clip.hardEdge, child: SizedBox(width: designWidth, height: designHeight, child: Stack(children: [ ... ]))))` using layout template bounds.
6. BUTTON DESIGN & ANTI-COLLISION:
   - For BUTTON nodes with an icon and label, select one pattern:
     (A) Row: `SizedBox.expand(child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [ icon, SizedBox(width: gap), Flexible(child: Text(...)) ]))`.
     (B) Bounded Stack: `SizedBox.expand(child: Stack(fit: StackFit.expand, children: [ Positioned(icon), Positioned(left: textLeft, right: textRight, child: Center(child: Text(...))) ]))`.
7. CODE ARCHITECTURE & RESERVATION CONTRACT:
   - Isolate repeated item trees into standalone layout components listed in `extractedWidgets` using PascalCase.
   - Embed main page logic into `screenCode` as a single `StatelessWidget` or `StatefulWidget`. Do not write top-level file imports or main blocks.
   - Custom Code Preservation: Insert explicit comment boundaries `// <custom-code>` and `// </custom-code>` inside any button onPressed handlers, field controllers, or state stubs.
   - ROOT GESTURE ISOLATION: Do NOT cascade `GestureDetector` wrappers at the screen root canvas. Delegate interactive events strictly to leaf widgets."""

_L5_GENERATE_CUPERTINO = """1. PRE-COMPILATION: Read the ### cleanTree user section; map every node to a Cupertino widget type (RichText when textSpans is non-empty). Emit only schema-valid JSON.
2. LAYOUT COMPILATION & DEPTH MINIMIZATION:
   - Use `Row`, `Column`, and `Wrap` for adaptive layouts. Avoid `Stack`/`Positioned` unless the node type is explicitly `STACK`.
   - Flex layouts default to `CrossAxisAlignment.start` and `MainAxisAlignment.start`. Map absolute alignment fields to `AlignmentDirectional.centerStart` or `Alignment.centerLeft` inside an `Align` widget — NEVER emit 'Alignment.start'.
   - Positioned Stack Elements Budget: Enforce a maximum of two horizontal pins (left/width or left/right) and two vertical pins (top/height). Never mix left, right, and width simultaneously.
3. SCROLLABLE & VIEWPORT RECAPPING:
   - Honor clean-tree semantic types listed in L4. Text elements inside a horizontal `Row` MUST be wrapped in `Flexible` or `Expanded` to block RenderFlex overflow.
4. TYPOGRAPHY & TEXT CLIPPING DEFIANCE:
   - Never wrap `Text` in fixed-height containers; use dynamic padding for proper `textScaler` compatibility.
   - For single-line text elements positioned absolutely, do NOT specify a tight `width`. Specify ONLY `left` (and optional margins) to allow natural text expansion. If width is mandatory, buffer it by +20% to +30% to prevent character clipping.
   - CONDITIONAL TEXT DISPATCH: If a text node contains a non-empty `textSpans` array, you MUST compile it using `RichText` or `Text.rich`. Flat `Text()` constructors for span trees are illegal.
5. BACKGROUND & DECORATIVE ASSET INTEGRITY:
   - Never approximate complex SVG paths with standard Containers or BoxDecorations. Render the original `vectorAssetKey` or `imageAssetKey` via `SvgPicture.asset`/`Image.asset`.
   - SCREEN FRAME ASSET BAN: Never attach background assets to the root screen node. Background graphics must originate from dedicated child nodes.
   - AMBIENT BACKGROUND RESPONSIVENESS: Group decorative background elements behind a centered layout into a dedicated background Stack wrapped in: `Positioned.fill(child: FittedBox(fit: BoxFit.cover, clipBehavior: Clip.hardEdge, child: SizedBox(width: designWidth, height: designHeight, child: Stack(children: [ ... ]))))` using layout template bounds.
6. BUTTON DESIGN & ANTI-COLLISION:
   - For BUTTON nodes with an icon and label, select one pattern:
     (A) Row: `SizedBox.expand(child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [ icon, SizedBox(width: gap), Flexible(child: Text(...)) ]))`.
     (B) Bounded Stack: `SizedBox.expand(child: Stack(fit: StackFit.expand, children: [ Positioned(icon), Positioned(left: textLeft, right: textRight, child: Center(child: Text(...))) ]))`.
7. CODE ARCHITECTURE & RESERVATION CONTRACT:
   - Isolate repeated item trees into standalone layout components listed in `extractedWidgets` using PascalCase.
   - Embed main page logic into `screenCode` as a single standalone class. Do not include top-level file imports or main blocks.
   - Custom Code Preservation: Insert explicit comment boundaries `// <custom-code>` and `// </custom-code>` inside any button click handlers, text controllers, or state stubs.
   - ROOT GESTURE ISOLATION: Do NOT cascade `GestureDetector` wrappers at the screen root canvas. Delegate interactive events strictly to leaf iOS controls."""

# --- generate (conditional) ---
_L5_GENERATE_ROUTING = """- ROUTING COMPILATION: Do not embed GoRouter infrastructure setups inside screenCode; routing bindings are compiled on a separate layer.
- Verify navigationHints schema payloads and invoke PrototypeNavigation helpers for prototype interaction nodes.
- Call PrototypeNavigation methods directly from button onPressed handlers instead of hardcoding raw route strings.
- For SCROLL_TO links, attach PrototypeScrollTargets.register('<targetId>') globally to the target widget key argument referenced in your navigationHints context."""

_L5_GENERATE_STACK = """- STACK ROOT LAYOUT: The Figma frame uses absolute positioning, NOT vertical flex distribution.
- Do NOT place unrelated UI blocks inside Column + Spacer flex ratios when cleanTree uses absolute stackPlacement.
- Do NOT wrap the screen in GeneratedScreenShell — the generator skips it for absolute STACK frames.
- Use a fixed design canvas: SizedBox(width: canvasWidth, height: canvasHeight) from cleanTree root sizing.
- Place every node with Positioned(left/top/width/height) using each node's stackPlacement and sizing from cleanTree.
- ABSOLUTELY FORBIDDEN: Do NOT introduce `LayoutBuilder`, `MediaQuery.of(context).size`, or any custom scaling factors to multiply coordinate values. ALWAYS use raw, fixed double literals directly from the cleanTree. Responsiveness and viewport centering are handled completely by the parent engine wrappers; any custom scaling calculations inside your screenCode will corrupt the layout."""

# --- refine ---
_L5_REFINE = """8. REFINE TRIPLE-COMPARISON EXECUTION: Perform the triple comparison internally; output ONLY schema-valid JSON (screenCode + extractedWidgets) — no markdown fences or free-text reasoning tags.
9. Align all Flutter layout boundaries to the exact bounding boxes (bbox = [ymin, xmin, ymax, xmax]) extracted from IMAGE 1.
10. To prevent layout drift on STACK frames, completely remove loose Column+Spacer combinations and replace them with explicitly sized Positioned widgets mapped to the design canvas.
11. Output MUST be strictly compliant with the requested JSON schema (screenCode + extractedWidgets).
12. ABSOLUTELY PRESERVE all `// <custom-code> ... // </custom-code>` blocks verbatim.
13. Do NOT add new import statements. Rely on design tokens and ThemeData; no hardcoded HEX color literals.
14. Honor TREE COMPLETENESS, BUTTON ICON+LABEL ANTI-COLLISION, and ROOT GESTURE ISOLATION invariants."""

_L5_REFINE_SURGICAL = """- SURGICAL WIDGET MODE: When the user payload includes `surgicalWidgetSnippets`, change ONLY those widget expressions.
- Do NOT rewrite the full `screenCode`. Return the same overall structure; patch only the listed snippets.
- Preserve every `ValueKey('figma-…')` on edited widgets."""

# --- repair ---
_REPAIR_L5 = """1. Parse the absolute coordinates from analyzeErrors. Match the lines directly with the prefixes in the numbered source listing.
2. Apply the "Look-Up Directive": If a syntax token error is reported, evaluate lines N-1 down to N-3. Fix the parent parameter layout.
3. Apply "Sibling Search Constraint" (levels 1-2 only): Generate the patch ensuring at least 3 lines of unchanged context code surround the modification.
4. Enforce "Button Invariant": Ensure every nested constructor inside styleFrom(...) is explicitly terminated with a trailing comma , prior to the child: parameter definition.
5. Enforce "Layout Rule": Ensure Flexible or Expanded widgets are never placed inside a Stack or Container; they must be immediate children of a Row, Column, or Flex.
6. Enforce "Rich Text Rule": If semanticHint indicates a textSpans array, implement RichText or Text.rich; never pass textSpans to a flat Text() constructor.
7. Output a strict JSON block matching the FlutterRepairPatchResponse schema. If a patch text length risks truncation, split the payload by creating multiple `extractedWidget` targets in the array.
8. Fix ONLY issues listed in analyzeErrors and repairTargets in the user payload. Do NOT patch unchangedWidgetNames.
9. Preserve ALL // <custom-code> ... // </custom-code> blocks verbatim.
10. Do NOT add import statements.
11. TextStyle.height MUST be a unitless ratio: height = figmaLineHeight / fontSize (e.g. fontSize 14 with lineHeight 17.1 → height: 1.22). NEVER copy Figma line-height pixels into height."""

_REPAIR_L5_UNIFIED_DIFF = """UNIFIED DIFF MODE (ALL LEVELS — MANDATORY):
- You work against line-numbered source (`N: dart code`). Analyzer errors cite the same physical line numbers.
- Each patch `code` field MUST be a valid git unified diff against the UNNUMBERED on-disk file (never include `N: ` prefixes in diff lines).
- Hunk headers (`@@ -line,count +line,count @@`) MUST target the line numbers from analyzeErrors / the numbered listing.
- Prefix context lines with a single space, deletions with `-`, additions with `+`; include at least 3 unchanged context lines per hunk.
- FORBIDDEN: full-file rewrites in `code`, SEARCH/REPLACE blocks, `<<<<<<<` markers, ellipses (`...`), `// ... existing`, or line-number prefixes inside the diff.
- If a hunk cannot be expressed safely, emit a smaller hunk centered on the exact failing line from focused error context."""

# --- cpi ---
_CPI_L5 = """1. Evaluate the lastPatches history against the current recurringErrors.
2. Locate the structural blind spot (the gap between where the compiler failed and where the agent keeps editing).
3. Formulate a Phase-Aware Pattern Interrupt Directive written in sharp, direct, uppercase tactical commands.
4. Output the analysis and the directive strictly inside the specified JSON schema."""
