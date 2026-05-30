"""LLM system prompts for codegen, analyze repair, and visual refine.

Public builders:
    - ``build_system_prompt`` — screen generation (Material 3 or Cupertino).
    - ``build_repair_system_prompt`` — dart-analyze APR patches.
    - ``build_visual_refine_system_prompt`` — pixel-diff refinement.

Multimodal user-message labels (``REFERENCE_USER_PREAMBLE``, etc.) are not system prompts.

``SYSTEMIC_BUG_RULES`` in this module is the canonical registry of short NEVER/MUST guardrails
for recurring LLM defects; extend it when fixing pipeline-wide bugs (see
``.cursor/rules/universal-codegen.mdc``).
"""

from __future__ import annotations

from dataclasses import dataclass
from string import Template

from figma_flutter_agent.llm.repair_scope import RepairEnvironmentContext

# Pipeline order in this module: generate → refine → repair → cpi.
# Within each ACDP level (L1–L6), blocks are grouped by pipeline stage.
# XML layer tags are applied only at assembly time via ``_acdp_layer``.


def _join_sections(*sections: str) -> str:
    """Join prompt sections with a blank line between each non-empty part."""
    return "\n\n".join(section for section in sections if section)


# ---------------------------------------------------------------------------
# L1:PURPOSE
# ---------------------------------------------------------------------------

# --- generate (greenfield codegen) ---
_L1_GENERATE_MATERIAL = (
    "The global objective is to operate strictly as a deterministic, production-grade "
    "layout-to-code compiler backend, translating dense Figma JSON trees into 100% complete, "
    "responsive, and compile-ready Material 3 UIs serialized within a strict JSON structure."
)

_L1_GENERATE_CUPERTINO = (
    "The global objective is to operate strictly as a deterministic, production-grade "
    "layout-to-code compiler backend, translating dense Figma JSON trees into 100% complete, "
    "responsive, and compile-ready Cupertino UIs serialized within a strict JSON structure."
)

# --- refine (visual delta; replaces generate L1 when refining) ---
_L1_REFINE = (
    "You operate as an Elite Multi-Modal UI Refinement Compiler with Visual Delta Feedback. "
    "Your sole objective is to eliminate visual and behavioral gaps between the current Flutter "
    "code and the target design."
)

# --- repair (APR) ---
_REPAIR_L1 = (
    "The global objective is to translate raw static analysis diagnostics into absolute, "
    "drift-immune, and compile-ready Dart/Flutter code patches, restoring the project code "
    "to a 0-error state."
)

# --- cpi (repair-loop supervisor) ---
_CPI_L1 = (
    "The global objective is to break trajectory fixation, prevent ideological lock-in, and "
    "terminate infinite repair loops by intercepting repetitive, non-progressing actions of the "
    "primary repair generation tier."
)

# ---------------------------------------------------------------------------
# L2:ROLE
# ---------------------------------------------------------------------------

# --- generate ---
_L2_GENERATE_MATERIAL = (
    "You are an expert Flutter/Material 3 compiler engine. You emit zero conversational "
    "narrative and strictly adhere to target design tokens, fluid layout mechanics, and "
    "structural completeness laws."
)

_L2_GENERATE_CUPERTINO = (
    "You are an expert Flutter/Cupertino compiler engine. You emit zero conversational "
    "narrative and strictly adhere to target iOS human interface guidelines, design tokens, "
    "and structural completeness laws."
)

# --- repair ---
_REPAIR_L2 = (
    "You are an elite, deterministic Automated Program Repair (APR) engine and syntax compiler. "
    "You operate without heuristic ambiguity and emit output strictly mapping to the requested "
    "AST modification schema."
)

# --- cpi ---
_CPI_L2 = (
    "You are an external Metacognitive Code-Review Supervisor operating recursively above the "
    "primary repair generation tier. You monitor execution velocity, risk indices, and structural "
    "stagnation."
)

# ---------------------------------------------------------------------------
# L3:PRINCIPLES
# ---------------------------------------------------------------------------

# --- generate + refine (shared structural invariants) ---
_L3_SHARED_JSON_SCHEMA = """- JSON SCHEMA GRAMMAR CONTROL: Your output MUST strictly comply with the requested JSON Schema.
- The generated Dart code MUST be serialized as a single, raw JSON-compliant string inside the "screenCode" property field.
- You MUST double-escape all string literals and special characters inside the Dart code: replace " with \\", \\ with \\\\, and represent newlines as \\n.
- DO NOT wrap the Dart code in Markdown code blocks (e.g., ```dart ... ```). Any inclusion of code fences or markdown preambles inside JSON string fields is a fatal structural violation that breaks schema validation."""

_L3_SHARED_SCREEN_IR = """- SCREEN IR GRAMMAR CONTROL: Your output MUST strictly comply with the requested JSON Schema.
- Emit `screenIr` (a JSON widget tree). Do NOT emit `screenCode` Dart source.
- Each IR node requires `figmaId` copied exactly from ### cleanTree. Default `kind` is `"auto"` (compiler reads layout from cleanTree).
- `children` lists nested IR nodes only — NEVER Dart syntax, widgets, parentheses, imports, or theme calls inside IR.
- Use `kind: "extracted"` with `ref.widgetName` for ### widgetExtractionHints targets; define each hint in `extractedWidgets[]` via `widgetIr` (subtree IR) — do NOT emit `extractedWidgets[].code` Dart.
- Optional `omitFigmaIds` drops nodes; `stackChildOrder` lists STACK child `figmaId`s in **paint order** (index 0 = bottom/backdrop, last = top/interactive) — reverse Figma's top-to-bottom layer list so VECTOR/IMAGE backdrops precede BUTTON/INPUT.
- Sparse `overrides` may set `text`, `accessibilityLabel`, and token-backed `textColor` / `backgroundColor` / `fontSize` only — values must exist in ### tokens."""

_L3_SHARED_INTERACTIVE = """- INTERACTIVE COMPILER INVARIANT (screenshots are NOT sufficient): PNG references show pixels only — they cannot prove taps, scroll, drag, text entry, selection, or navigation. Implement real Flutter interaction from cleanTree semantics, component variants, and navigationHints. Never emit decorative-only controls where Figma marks interactivity.
- Mandatory wiring:
  * BUTTON / tappable frames / icon controls: Material buttons (FilledButton, TextButton, IconButton), InkWell, or CupertinoButton with onPressed/onTap. Unknown logic goes inside // <custom-code> ... // </custom-code> — never omit the handler.
  * TOGGLE / CHECKBOX / SWITCH / RADIO: StatefulWidget or explicit value + onChanged; map variantProperties (State, Checked, Disabled) to both visuals AND callbacks.
  * SLIDER: Slider / CupertinoSlider with value + onChanged — never a static track/thumb decoration.
  * TEXT INPUT nodes: TextField / CupertinoTextField with controller or onChanged; respect keyboard/obscure flags from metadata when present.
  * SCROLL / LIST / GRID / CAROUSEL: ListView.builder, GridView.builder, PageView with scrollDirection from cleanTree — never a non-scrollable Column mimicking a list.
  * TABS / BOTTOM NAV: TabController + TabBarView or BottomNavigationBar with selectedIndex state and onTap/onChanged.
  * Prototype / navigation nodes: wire onPressed to PrototypeNavigation helpers from navigationHints when routing is enabled.
  * Disabled / loading / pressed variants: use MaterialStateProperty (or Cupertino equivalent) AND disable interaction (null onPressed/onChanged) when State=Disabled.
- Reject outputs that render interactive Figma nodes as passive Icon, Text, Container, or Stack-only decorations.
- NEVER wrap the entire screen body in nested GestureDetector layers; attach handlers only to the specific interactive leaf from cleanTree."""

_L3_CUSTOM_WIDGET_NAMED_PARAMS = (
    "- CUSTOM WIDGET CALL CONTRACT: NEVER pass positional arguments to custom widgets "
    "(any user-defined or extracted PascalCase widget such as `SignInMainContent`, "
    "`CleanInputField`, or `*Widget` classes from extractedWidgets). "
    "ALWAYS use named parameters only: `SignInMainContent(onTap: handler, emailController: c)`. "
    "Positional arguments on Flutter SDK primitives (`Text`, `Container`, `Padding`) remain valid."
)

_L3_DART_DEFAULT_VALUE_SYNTAX = (
    "CRITICAL DART CONSTRAINT: Always use the '=' operator for parameter default values "
    "(e.g., `this.text = \"value\"`, `this.onPressed = callback`). NEVER use archaic pre-Dart 2.0 "
    "colon syntax for defaults (e.g., `this.text : \"value\"`, `void onPressed: () {}`). "
    "Constructor fields use `required this.onPressed` or `this.onPressed = callback` inside "
    "`{}`; optional initializer lists use `: super(key: key)` only after the closing `)`."
)

_L3_SHARED_BOUNDED_POSITIONED_STACK = (
    "- BOUNDED POSITIONED MANDATE: Every `Positioned` widget wrapping a `BUTTON`, `INPUT`, or "
    "`CONTAINER` node that contains a nested `Stack` MUST explicitly declare BOTH horizontal "
    "parameters (`left` and `width`) AND BOTH vertical parameters (`top` and `height`) fetched "
    "from the cleanTree sizing metadata. Leaving dimensions implicit or emitting a standard "
    "un-sized `SizedBox` or loose `Stack` inside unconstrained layouts is a fatal architectural "
    "violation that crashes the rendering library."
)

# ---------------------------------------------------------------------------
# L3: SYSTEMIC BUG REGISTRY — short LLM guardrails for pipeline-wide defects.
# Add a new rule here whenever we fix a recurring LLM bug (do not rely on Python
# sanitizers alone). See `.cursor/rules/universal-codegen.mdc`.
# ---------------------------------------------------------------------------

SYSTEMIC_BUG_RULES: tuple[str, ...] = (
    "NEVER declare `Key? key = null` or `Key key` when the constructor already passes `super.key` — use `super.key` only once.",
    "NEVER emit duplicate named parameters (`child: child:`, `onPressed: onPressed:`) or stutter like `child: key:` / `child: onPressed:` before real named args.",
    "NEVER pass `fontSize`, `fontWeight`, `fontFamily`, `fontFamilyFallback`, `color`, `height`, or `letterSpacing` as direct `Text(...)` parameters — only inside `style: TextStyle(...)`.",
    "NEVER prefix `const` on `AppTypography.*` or `AppTypography.*.copyWith(...)` — those tokens are already `TextStyle` values, not constructors.",
    "NEVER nest chained `.copyWith(...).copyWith(...)` on `TextStyle` / theme typography — merge into a single `copyWith` or use one `textTheme` slot.",
    "NEVER reference the same typography token identifier recursively in a static/final `TextStyle` initializer (e.g. `headlineLarge = headlineLarge.copyWith(...)`) — that causes StackOverflowError / InitializerCycleError; inherit from `ThemeData` / `textTheme` or raw literals instead.",
    "NEVER emit orphan `fontFamilyFallback: [...]` list shards as standalone lines outside a `TextStyle(` constructor.",
    "NEVER set `TextStyle.height` to Figma line-height pixels — use unitless ratio `lineHeight / fontSize` (e.g. 17.1 / 14 → `height: 1.22`).",
    "NEVER use `Flex(fit: …)` for row/column children — `Flex` has no `fit` parameter; use `Flexible(fit: FlexFit.loose, child: …)` or `Expanded`.",
    "NEVER place a `TextField` or `TextFormField` directly inside a `Row` — `InputDecorator` needs bounded width; wrap inputs in `Expanded` or `Flexible`.",
    "NEVER place scrollable widgets (`ListView`, `GridView`, `SingleChildScrollView`) directly inside an unconstrained `Column` or `Row`; wrap them in `Expanded` or `Flexible` so bounded `BoxConstraints` reach the scrollable.",
    "Avoid `shrinkWrap: true` on scrollables to paper over layout crashes — route constraints with `Expanded` / `Flexible` instead of disabling lazy layout.",
    "NEVER emit `stackPlacement` without bounded width and height (explicit size or LEFT_RIGHT/TOP_BOTTOM pins); scroll hosts under Column/Row need `wrap: expanded` — IR validation rejects these before codegen.",
    "NEVER nest vertical scroll inside another vertical scroll without `nestedScrollConstraints`; put `wrap: flexibleLoose` on TEXT inside ROW — IR validation auto-fixes or fails.",
    "Figma layers are ordered top-to-bottom (top overlaps bottom). Flutter `Stack` paints children in array order (index 0 = bottom). You MUST reverse child order when building a `Stack`: decorative VECTOR/IMAGE backdrops at index 0, interactive BUTTON/INPUT last; otherwise hit tests fail and controls are unclickable. Use `stackChildOrder` in screenIr when needed.",
    "`Positioned` widgets may ONLY be direct children of a `Stack` — never nest `Positioned` inside a `Container`, `Column`, or other wrapper that itself sits in a `Stack`.",
    "NEVER reference `assets/...` paths that are not exported to disk — IR validation checks files when `project_dir` is available.",
    "NEVER duplicate `figmaId` values or create cyclic IR parent/child links — each id appears once in screenIr.",
    "NEVER place flex-layout INPUT fields in the lower half of the screen without a scroll ancestor — IR validation sets `scrollAxis: vertical` on the nearest COLUMN or fails.",
    "If the screen contains any text input (`TextField` / INPUT nodes), NEVER hardcode absolute fixed parent heights (e.g. `Container(height: 844)`) — the software keyboard shrinks the viewport and causes bottom overflow; use scrollable or flexible constraints.",
    "Interactive hit targets (buttons, icon taps, links) MUST be at least 44×44 logical pixels; when Figma frames are smaller (e.g. 24×24 close icons), add transparent padding or `minTouchTarget` / `SizedBox` constraints — IR validation may auto-fix.",
    "NEVER output raw `Color(0xFF…)` literals or ad-hoc border radii unless explicitly forced — map fills and radii to ### tokens / `Theme.of(context)` / `AppColors` / `AppTypography`; IR `overrides` only accept registered token colors and typography sizes.",
    "NEVER place `Flexible`, `Expanded`, or unbounded `Row`/`Column` children directly inside a `Stack` — flex children belong under `Row`/`Column` only.",
    "NEVER emit `Positioned` inside a `Stack` without explicit bounds from cleanTree: provide both horizontal pins (`left` and `width`, or `left` and `right`) AND both vertical pins (`top` and `height`, or `top` and `bottom`) for BUTTON, INPUT, and CONTAINER nodes that host nested stacks.",
    "NEVER output interactive or text widgets inside a `Stack` without verifying width and height (or equivalent pin pairs) exist in cleanTree sizing — implicit loose stacks crash layout.",
    "NEVER hardcode `color: Color(0xFF000000)` on button labels over saturated or purple `backgroundColor` fills — use `Theme.of(context).colorScheme.onPrimary` or token contrast from ### tokens.",
    "NEVER upscale the fixed Figma canvas with `FittedBox(fit: BoxFit.contain)` on full-screen backgrounds — prefer `BoxFit.scaleDown` or the template `BoxFit.cover` shell so typography does not stretch.",
    "NEVER mark a widget `const` when its subtree uses `MediaQuery.textScalerOf(context)`, `Theme.of(context)`, or other runtime `context` lookups.",
    "NEVER introduce `LayoutBuilder`, `MediaQuery.of(context).size`, or manual scale factors on coordinate literals — the engine wrappers own responsiveness.",
    "NEVER emit stray closing-bracket lines (`])))}}`) or semicolon-only lines — they break `dart format` and analyzer passes.",
    "NEVER emit layouts that never reach layout idle (infinite flex/stack relayout) — golden capture uses `pumpAndSettle` with a 20s cap and will fail refine without `flutter_render.png`.",
    "NEVER use `Alignment.start` — map to `AlignmentDirectional.centerStart`, `Alignment.centerLeft`, or `Align(alignment: ...)` per flex/stack context.",
    "NEVER use `Image.network` for static Figma assets — use `Image.asset` / `SvgPicture.asset` paths from ### assetManifest.",
    "NEVER declare helper `*Widget` classes at the end of screenCode — prebuilt subtree widgets already live in separate files; reference them only with `const WidgetName()` (imports are wired by the generator).",
    "NEVER emit `SizedBox.shrink()` placeholder widget classes — they hide real assets and break golden capture.",
)


def build_systemic_bug_registry_l3() -> str:
    """Return the L3 systemic bug registry block injected into generate/repair/refine prompts."""
    bullets = "\n".join(f"- {rule}" for rule in SYSTEMIC_BUG_RULES)
    return (
        "SYSTEMIC BUG REGISTRY (mandatory guardrails; extend `SYSTEMIC_BUG_RULES` in "
        "llm/prompts.py when fixing a new pipeline-wide LLM defect):\n"
        f"{bullets}"
    )


_L3_SYSTEMIC_BUG_REGISTRY = build_systemic_bug_registry_l3()

# --- generate (theme + conditional) ---
_L3_GENERATE_INVARIANTS_MATERIAL = """- 1:1 NODE PARITY LAW (PRIMACY REGION): Every single node present in the input JSON tree MUST become a real, functional, compiled Flutter widget with an assigned `key: ValueKey('figma-<nodeId>')` anchor. Replacing layout nodes with comment placeholders (e.g., `// Back button`, `// Ambient Background`) is a fatal compiler violation.
- ZERO LAZY PLACEHOLDERS: You are strictly forbidden from emitting ellipses (`...`), partial method stubs, or pseudocode. Every class, widget, and callback must be fully written out.
- BOUNDARY SYNTAX ANCHORS: When customizing buttons via `styleFrom(...)`, you MUST insert a trailing comma `,` immediately after the closing parenthesis of `styleFrom` and right before the `child:` property to prevent syntax boundary collapse.
- CONTROLLER LIFECYCLE SANITY: If an INPUT node is isolated into an `extractedWidget`, it MUST remain stateless and accept its `TextEditingController` as a required, immutable constructor parameter from the parent StatefulWidget. Instantiating controllers inside extracted sub-widgets without lifecycle management is strictly prohibited.
- FONT METRIC DEFENCE: Never hardcode custom `fontFamily` layout string literals (e.g., 'Helvetica Neue') inside widget styles unless explicitly appending `fontFamilyFallback: const ['Roboto', 'Arial', 'sans-serif']`. Rely exclusively on global inherited `Theme.of(context).textTheme` parameters to avoid CanvasKit rendering exceptions."""

_L3_GENERATE_INVARIANTS_CUPERTINO = """- 1:1 NODE PARITY LAW (PRIMACY REGION): Every single node present in the input JSON tree MUST become a real, functional, compiled Flutter widget with an assigned `key: ValueKey('figma-<nodeId>')` anchor. Replacing layout nodes with comment placeholders (e.g., `// Back button`) is a fatal compiler violation.
- ZERO LAZY PLACEHOLDERS: You are strictly forbidden from emitting ellipses (`...`), partial method stubs, or pseudocode. Every class, widget, and callback must be fully written out.
- BOUNDARY SYNTAX ANCHORS: When configuring nested Cupertino controls or layout shells, ensure all constructor properties are separated from child fields by a trailing comma `,` to prevent syntax collapse at the parameter boundary.
- CONTROLLER LIFECYCLE SANITY: If an INPUT node is isolated into an `extractedWidget`, it MUST remain stateless and accept its `TextEditingController` as a required, immutable constructor parameter from the parent StatefulWidget. Instantiating controllers inside extracted sub-widgets without lifecycle management is strictly prohibited.
- FONT METRIC DEFENCE: Never hardcode custom `fontFamily` layout string literals (e.g., 'Helvetica Neue') inside widget styles unless explicitly appending `fontFamilyFallback: const ['Roboto', 'Arial', 'sans-serif']`. Rely exclusively on global inherited layout parameters to avoid CanvasKit rendering exceptions."""

_L3_GENERATE_ROUTING_OFF = (
    "- ROUTING OUTPUT BAN: Do not generate routing metadata, Router, Navigator, or "
    "GoRouter setup block declarations inside screenCode."
)

# --- refine (L3 extensions injected into generate base) ---
_L3_REFINE_VISUAL_GOLD = """- VISUAL GOLD STANDARD: An attached PNG screenshot is the authoritative Figma export of the target screen frame. Match layout, spacing, typography, colors, hierarchy, icon placement, and component structure as closely as Flutter constraints allow.
- When JSON clean-tree data conflicts with the screenshot on visual appearance, prefer the screenshot unless doing so would break the compiler invariants.
- Behavioral/interaction requirements still come from cleanTree semantics and navigationHints."""

_L3_REFINE_MULTIMODAL = """- INPUT IMAGES SPECIFICATION: You receive THREE PNG images in a FIXED order. NEVER SWAP THEIR ROLES:
  * IMAGE 1 (figma_reference): The TARGET golden-standard design. Absolute truth for appearance.
  * IMAGE 2 (flutter_render): The CURRENT UI output from generated code.
  * IMAGE 3 (visual_diff_heatmap): Pixel-level delta map. Mismatched pixels vs IMAGE 1 are highlighted in RED on the Figma layout. Treat red zones as a direct error log.
- ANTI-SEMANTIC DRIFT GUARD: Avoid "Semantic-Preservation Drift". Match the EXACT text tokens, states, and iconography visible in IMAGE 1. Zero tolerance for structural or textual hallucinations.
- TRIPLE COMPARISON MANDATE: Apply the three-lens verification framework before outputting code:
  1. IMAGE 3 (Visual Diff) → CODE: Inspect RED zones in IMAGE 3. Locate the widgets responsible for geometry, padding, typography, or missing assets.
  2. IMAGE 1 ↔ IMAGE 2: Cross-check remaining gaps not obvious in IMAGE 3.
  3. IMAGE 1 ↔ CURRENT CODE ↔ CLEAN_TREE SEMANTICS: Ensure every control exists with correct properties and interactive handlers."""

_REPAIR_L3_IR_PATCHES = """- SCREEN IR REPAIR: When `currentScreenIr` is present you MAY emit `irPatches` for structural fixes (child order, omit/replace subtrees, text overrides) without Dart. Each `irPatch` uses `figmaId` from currentScreenIr. Prefer unified-diff `patches` for analyzer syntax/type errors on planned Dart excerpts.
- IR patch fields: `replaceSubtree` (full WidgetIrNode), `overrides` (`text` / `accessibilityLabel` only), `reorderChildren` (figma id list). Never put Dart, widgets, or theme calls inside IR JSON."""

# --- repair ---
_REPAIR_L3 = """- CUSTOM WIDGET CALL CONTRACT: NEVER pass positional arguments to custom widgets in screenCode or extractedWidgets. ALWAYS use named parameters: `WidgetName(param: value)`.
- CRITICAL DART CONSTRAINT: Always use the '=' operator for parameter default values (e.g., `this.text = "value"`, `this.onPressed = callback`). NEVER use archaic pre-Dart 2.0 colon syntax for defaults (e.g., `this.text : "value"`, `void onPressed: () {}`).
- TOKEN DEFICIT MITIGATION (THE DECOMPOSITION LAW): To prevent JSON string truncation caused by model output token limits, you must avoid emitting massive full-class definitions in `screenCode`. If the corrected class body exceeds 150 lines, you MUST aggressively extract the failing sub-tree into a standalone, modular `extractedWidget` target. Keep `screenCode` as lean as possible.
- EXTRACTED WIDGET IDENTIFIER SYNC: When analyzeErrors mention a name "isn't a class" or undefined_method for `_Foo` / `_FooBar`, align `screenCode` with the public PascalCase class in `extractedWidgets` (`widgetName` → `FooBar()`, never `_FooBar()`). Do not rename extracted widget classes to lowercase mashups.
- UPSTREAM RESOLUTION: Native compilers halt at line N only when reaching an irreconcilable grammar state. The root cause (e.g., missing commas, unclosed blocks) is always upstream in the interval [N-3, N-1]. You must scan vertically upward from the error site.
- TRAJECTORY INVARIANCE: You are strictly forbidden from repeating code shapes or structural patterns that have already failed in previous execution turns.
- ANTI-COLLISION: Every modification must preserve surrounding structural anchors to avoid code corruption during patching.
- ZERO NARRATIVE: You emit only valid JSON. No conversational padding, no markdown explanations outside the code array."""

# --- cpi ---
_CPI_L3 = """- ANTI-PATTERN INERTIA: Circular "Try-Again" workflows without logical deviation must be forcefully interrupted.
- DEDUCTIVE ESCALATION: When an agent is blind to a missing upstream token, the supervisor must forcefully re-center the agent's focus window using high-priority negative constraints.
- TOKEN CONTEXT ECONOMY: Interruptions must be precise and concise to avoid polluting the active window."""

def _generate_l3_core(theme_variant: str, *, use_screen_ir: bool) -> str:
    json_block = _L3_SHARED_SCREEN_IR if use_screen_ir else _L3_SHARED_JSON_SCHEMA
    invariants = (
        _L3_GENERATE_INVARIANTS_CUPERTINO
        if theme_variant == "cupertino"
        else _L3_GENERATE_INVARIANTS_MATERIAL
    )
    return _join_sections(
        invariants,
        json_block,
        _L3_SHARED_INTERACTIVE,
        _L3_CUSTOM_WIDGET_NAMED_PARAMS,
        _L3_DART_DEFAULT_VALUE_SYNTAX,
        _L3_SHARED_BOUNDED_POSITIONED_STACK,
        _L3_SYSTEMIC_BUG_REGISTRY,
    )


_L3_GENERATE_MATERIAL_CORE = _generate_l3_core("material_3", use_screen_ir=False)
_L3_GENERATE_CUPERTINO_CORE = _generate_l3_core("cupertino", use_screen_ir=False)

# ---------------------------------------------------------------------------
# L4:CAPABILITIES
# ---------------------------------------------------------------------------

# --- generate ---
_L4_GENERATE_MATERIAL = """- Advanced execution of Material 3 design tokens (`Theme.of(context).colorScheme`, `textTheme`) without hardcoded literal injection.
- Structural constraints resolution (`Flexible`/`Expanded` positioning invariants inside horizontal containers).
- Error-free compilation of conditional typographical structures (RichText vs standard Text).
- Semantic mapping: GRID→GridView.builder, scrollAxis→ListView.builder, TABS→TabBar/TabBarView, BOTTOM_NAV→BottomNavigationBar, CAROUSEL→PageView, DIALOG→AlertDialog, CARD→Card.
- [STATEFUL VARIANT MAPPING]: Map variantProperties with MaterialStateProperty, switch expressions, or native widget APIs."""

_L4_GENERATE_CUPERTINO = """- Advanced implementation of Cupertino styling controls (`CupertinoButton`, `CupertinoTextField`, `CupertinoPageScaffold`, `CupertinoNavigationBar`).
- Material Theme Bridge logic resolution only when explicitly sharing global tokens.
- Error-free compilation of conditional typographical structures (RichText vs standard Text).
- Semantic mapping: scrollAxis→ListView.builder, TABS→CupertinoTabBar patterns, CAROUSEL→PageView, CHECKBOX/SWITCH/SLIDER→CupertinoCheckbox/CupertinoSwitch/CupertinoSlider."""

# --- repair ---
_REPAIR_L4 = """- Proficient in Dart 3.x type systems, constructor mechanics, and cascading widget definitions.
- Deep understanding of Flutter layout constraints (Flex, Stack, ParentData requirements).
- Ability to cross-reference runtime ValueKey anchors with structural design semantics."""

# --- cpi ---
_CPI_L4 = """- Expert in identifying repetitive token sequence generation (cosine similarity of code states).
- Advanced pattern recognition in compiler error logs and loop mechanics."""

# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# L6:ENVIRONMENT
# ---------------------------------------------------------------------------

# --- generate ---
_L5_SCREEN_IR_ARCHITECTURE = """7. SCREEN IR ARCHITECTURE (replaces Dart screenCode emission):
   - Populate `screenIr.root` to mirror ### cleanTree structure: every included node needs `figmaId` + `children`.
   - Start from ### screenIrBlueprint when present; adjust children order, `omitFigmaIds`, or `extracted` refs — do not invent ids.
   - Map ### widgetExtractionHints to `kind: "extracted"` nodes with `ref.widgetName` (PascalCase).
   - For each extracted widget, emit `extractedWidgets[]` with `widgetName` + `widgetIr` rooted at the subtree `figmaId` (see ### extractedWidgetBlueprints). No Dart in `code`.
   - The compiler emits Dart, flex wrappers, and Positioned pins — you supply structure only."""

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


def _acdp_layer(tag: str, body: str) -> str:
    """Wrap layer body in matching open/close ACDP tags.

    Args:
        tag: Layer tag name (e.g. ``L1:PURPOSE``).
        body: Inner text (no surrounding tags).

    Returns:
        Tagged block with explicit closing tag.
    """
    return f"<{tag}>\n{body.strip()}\n</{tag}>"


def _compose_acdp_prompt(
    *,
    l1: str,
    l2: str,
    l3_core: str,
    l3_principles_ext: str = "",
    l4: str,
    l5_core: str,
    l5_actions_ext: str = "",
    l6: str,
) -> str:
    """Assemble a system prompt with strict L1→L6 ordering and level-aware extensions.

    Conditional fragments are injected via ``l3_principles_ext`` and ``l5_actions_ext``
    inside their parent layers — never appended after ``<L6:ENVIRONMENT>``.

    Args:
        l1: ``<L1:PURPOSE>`` body text.
        l2: ``<L2:ROLE>`` body text.
        l3_core: Base ``<L3:PRINCIPLES>`` bullets (grammar, invariants).
        l3_principles_ext: Optional L3 extensions (visual gold, routing ban, refine multimodal).
        l4: ``<L4:CAPABILITIES>`` body text.
        l5_core: Base ``<L5:ACTIONS>`` numbered steps.
        l5_actions_ext: Optional L5 extensions (routing, stack root, refine, surgical).
        l6: ``<L6:ENVIRONMENT>`` block (static contract or Template-rendered repair context).

    Returns:
        Single system prompt preserving ACDP layer sequence.
    """
    l3_body = l3_core.strip()
    if l3_principles_ext.strip():
        l3_body = f"{l3_body}\n\n{l3_principles_ext.strip()}"
    l5_body = l5_core.strip()
    if l5_actions_ext.strip():
        l5_body = f"{l5_body}\n\n{l5_actions_ext.strip()}"
    return "\n\n".join(
        [
            _acdp_layer("L1:PURPOSE", l1),
            _acdp_layer("L2:ROLE", l2),
            _acdp_layer("L3:PRINCIPLES", l3_body),
            _acdp_layer("L4:CAPABILITIES", l4),
            _acdp_layer("L5:ACTIONS", l5_body),
            _acdp_layer("L6:ENVIRONMENT", l6),
        ]
    )


def _theme_layers(
    theme_variant: str,
    *,
    use_screen_ir: bool = False,
) -> tuple[str, str, str, str, str, str]:
    """Return base L1/L2/L3/L4/L5/L6 bodies for a generate theme variant."""
    l3 = _generate_l3_core(theme_variant, use_screen_ir=use_screen_ir)
    l6 = _L6_GENERATE_USER_CONTRACT_IR if use_screen_ir else _L6_GENERATE_USER_CONTRACT
    if theme_variant == "cupertino":
        return (
            _L1_GENERATE_CUPERTINO,
            _L2_GENERATE_CUPERTINO,
            l3,
            _L4_GENERATE_CUPERTINO,
            _L5_GENERATE_CUPERTINO,
            l6,
        )
    return (
        _L1_GENERATE_MATERIAL,
        _L2_GENERATE_MATERIAL,
        l3,
        _L4_GENERATE_MATERIAL,
        _L5_GENERATE_MATERIAL,
        l6,
    )


def _render_generate_prompt(
    theme_variant: str,
    *,
    l1_purpose: str | None = None,
    l3_principles_ext: str = "",
    l5_actions_ext: str = "",
    use_screen_ir: bool = False,
) -> str:
    """Render a generate/refine-base system prompt with placeholder injections at L3/L5."""
    l1, l2, l3, l4, l5, l6 = _theme_layers(theme_variant, use_screen_ir=use_screen_ir)
    if use_screen_ir:
        l5 = f"{l5}\n\n{_L5_SCREEN_IR_ARCHITECTURE}"
    return _compose_acdp_prompt(
        l1=l1_purpose or l1,
        l2=l2,
        l3_core=l3,
        l3_principles_ext=l3_principles_ext,
        l4=l4,
        l5_core=l5,
        l5_actions_ext=l5_actions_ext,
        l6=l6,
    )


def _build_l3_extensions(
    *,
    routing_enabled: bool,
    figma_reference_attached: bool,
    refine_multimodal: bool = False,
) -> str:
    """Collect L3 extensions in canonical order (routing ban → visual gold → refine)."""
    parts: list[str] = []
    if not routing_enabled:
        parts.append(_L3_GENERATE_ROUTING_OFF)
    if figma_reference_attached:
        parts.append(_L3_REFINE_VISUAL_GOLD)
    if refine_multimodal:
        parts.append(_L3_REFINE_MULTIMODAL)
    return _join_sections(*parts)


def _build_l5_extensions(
    *,
    routing_enabled: bool,
    stack_root: bool,
    refine_mode: bool = False,
    surgical_widgets: bool = False,
) -> str:
    """Collect L5 extensions in canonical order (routing → stack → refine → surgical)."""
    parts: list[str] = []
    if routing_enabled:
        parts.append(_L5_GENERATE_ROUTING)
    if stack_root:
        parts.append(_L5_GENERATE_STACK)
    if refine_mode:
        parts.append(_L5_REFINE)
    if surgical_widgets:
        parts.append(_L5_REFINE_SURGICAL)
    return _join_sections(*parts)


@dataclass(frozen=True, slots=True)
class CpiSupervisorContext:
    """Runtime bindings for the metacognitive repair-loop supervisor prompt."""

    last_patches: str
    recurring_errors: str
    figma_node_intent: str


@dataclass(frozen=True, slots=True)
class MultimodalUserLabels:
    """Text prepended to multimodal user messages (not LLM system prompts)."""

    reference_preamble: str
    figma_only: str
    figma_inline: str
    flutter_render_inline: str
    visual_diff_inline: str
    refine_intro: str
    refine_preamble: str


USER_LABELS = MultimodalUserLabels(
    reference_preamble=(
        "Attached PNG: golden-standard Figma export of the target screen. "
        "Match this reference as closely as valid Flutter layout rules allow.\n\n"
    ),
    figma_only=(
        "[[FIGMA REFERENCE — TARGET DESIGN]] "
        "Golden-standard Figma export of the target screen frame. "
        "Match this reference — it is NOT the Flutter output.\n"
    ),
    figma_inline=(
        "[[IMAGE 1 — FIGMA REFERENCE (TARGET)]] "
        "Authoritative Figma frame export. This is the design you MUST match. "
        "Do NOT treat this image as the Flutter output.\n"
    ),
    flutter_render_inline=(
        "[[IMAGE 2 — FLUTTER RENDER (CURRENT OUTPUT)]] "
        "Current Flutter golden screenshot from generated code. "
        "This is what you are fixing — move it toward IMAGE 1; never treat IMAGE 2 as the target.\n"
    ),
    visual_diff_inline=(
        "[[IMAGE 3 — VISUAL DIFF HEATMAP]] "
        "Pixel delta vs IMAGE 1: mismatches highlighted in RED on the Figma layout. "
        "Use this as an error map — do not treat red pixels as desired design.\n"
    ),
    refine_intro=(
        "Three images follow in fixed order. Each has an inline label immediately before its image block. "
        "Confirm roles via attachedImages in the JSON below.\n\n"
    ),
    refine_preamble=(
        "Attached images (fixed order — do not swap):\n"
        "- IMAGE 1 / figma_reference: Figma golden-standard export (TARGET design).\n"
        "- IMAGE 2 / flutter_render: current Flutter golden render (CURRENT output to refine).\n"
        "- IMAGE 3 / visual_diff_heatmap: red-on-Figma mismatch map (ERROR LOG vs target).\n"
        "Start from IMAGE 3 red zones → Dart code, then IMAGE 1 ↔ IMAGE 2, then CODE ↔ interactivity. "
        "Use refineHistory when present to avoid repeating failed strategies.\n\n"
    ),
)

REFERENCE_USER_PREAMBLE = USER_LABELS.reference_preamble
FIGMA_REFERENCE_ONLY_LABEL = USER_LABELS.figma_only
FIGMA_REFERENCE_INLINE_LABEL = USER_LABELS.figma_inline
FLUTTER_RENDER_INLINE_LABEL = USER_LABELS.flutter_render_inline
VISUAL_DIFF_INLINE_LABEL = USER_LABELS.visual_diff_inline
VISUAL_REFINE_IMAGE_INTRO = USER_LABELS.refine_intro
VISUAL_REFINE_USER_PREAMBLE = USER_LABELS.refine_preamble

_REFINE_IMAGE_ROLES: tuple[dict[str, str | int], ...] = (
    {
        "index": 1,
        "role": "figma_reference",
        "label": "FIGMA REFERENCE (TARGET)",
        "description": "Authoritative Figma frame export — the design to match.",
        "attachmentHint": "First labeled image block above this JSON.",
    },
    {
        "index": 2,
        "role": "flutter_render",
        "label": "FLUTTER RENDER (CURRENT OUTPUT)",
        "description": "Current Flutter golden from generated code — refine toward image 1.",
        "attachmentHint": "Second labeled image block above this JSON.",
    },
    {
        "index": 3,
        "role": "visual_diff_heatmap",
        "label": "VISUAL DIFF HEATMAP",
        "description": "Red-highlighted pixel deltas vs Figma — map red zones to code fixes.",
        "attachmentHint": "Third labeled image block above this JSON.",
    },
)


def build_system_prompt(
    *,
    routing_enabled: bool = False,
    theme_variant: str = "material_3",
    figma_reference_attached: bool = False,
    stack_root: bool = False,
    use_screen_ir: bool = False,
) -> str:
    """Build the LLM system prompt for screen codegen.

    Composes a prebuilt generate body (Material 3 or Cupertino) with optional appendices
    for prototype routing, an attached Figma PNG, or a STACK-root layout.

    Args:
        routing_enabled: When True, append prototype ``PrototypeNavigation`` rules.
        theme_variant: ``material_3`` (default) or ``cupertino``.
        figma_reference_attached: When True, append PNG gold-standard rules.
        stack_root: When True, append absolute ``Positioned`` layout rules.
        use_screen_ir: When True, require ``screenIr`` tree output instead of ``screenCode``.

    Returns:
        System prompt string for ``generate`` LLM calls.
    """
    return _render_generate_prompt(
        theme_variant,
        l3_principles_ext=_build_l3_extensions(
            routing_enabled=routing_enabled,
            figma_reference_attached=figma_reference_attached,
        ),
        l5_actions_ext=_build_l5_extensions(
            routing_enabled=routing_enabled,
            stack_root=stack_root,
        ),
        use_screen_ir=use_screen_ir,
    )


def render_repair_system_prompt(context: RepairEnvironmentContext) -> str:
    """Render the APR repair system prompt with ``string.Template.safe_substitute``.

    Args:
        context: ``L6:ENVIRONMENT`` fields built by ``repair_scope``.

    Returns:
        Repair system prompt with analyzer errors, numbered source, and history injected.
    """
    l6 = Template(_REPAIR_L6_TEMPLATE).safe_substitute(
        analyzeErrors=context.analyze_errors,
        code=context.code,
        semanticHint=context.semantic_hint,
        failedAttemptsHistory=context.failed_attempts_history,
        unchangedWidgetNames=context.unchanged_widget_names,
        cpiSupervisorDirective=context.cpi_supervisor_directive,
        repairEscalationBlock="(none — standard APR level 1)",
    )
    return _compose_acdp_prompt(
        l1=_REPAIR_L1,
        l2=_REPAIR_L2,
        l3_core=_join_sections(_REPAIR_L3, _L3_SYSTEMIC_BUG_REGISTRY),
        l4=_REPAIR_L4,
        l5_core=_join_sections(_REPAIR_L5, _REPAIR_L5_UNIFIED_DIFF),
        l6=l6,
    )


def build_repair_system_prompt(
    context: RepairEnvironmentContext | None = None,
    *,
    use_screen_ir: bool = False,
) -> str:
    """Build the APR system prompt for ``llm_repair`` / dart-analyze patch mode.

    Theme-agnostic: repair targets are taken from the user JSON payload; L6 holds
    numbered source and analyzer output from ``repair_scope``.

    Args:
        context: Environment substitutions for ``<L6:ENVIRONMENT>``. When omitted,
            uses empty-safe placeholder defaults for tests.

    Returns:
        System prompt string for repair patch structured output.
    """
    if context is None:
        context = RepairEnvironmentContext(
            analyze_errors="(none)",
            code="(empty file)",
            semantic_hint="null",
            failed_attempts_history="(no prior failed patches in this run)",
            unchanged_widget_names="(none)",
        )
    prompt = render_repair_system_prompt(context)
    if use_screen_ir:
        return f"{prompt}\n\n{_REPAIR_L3_IR_PATCHES}"
    return prompt


def render_escalated_metacognitive_repair_prompt(
    context: RepairEnvironmentContext,
    *,
    escalation_level: int,
    tactical_directive: str,
    target_file: str,
    attempt: int,
    max_attempts: int,
) -> str:
    """Replace the APR system prompt with metacognitive supervisor + repair L6 bindings."""
    base_l6 = Template(_REPAIR_L6_TEMPLATE).safe_substitute(
        analyzeErrors=context.analyze_errors,
        code=context.code,
        semanticHint=context.semantic_hint,
        failedAttemptsHistory=context.failed_attempts_history,
        unchangedWidgetNames=context.unchanged_widget_names,
        cpiSupervisorDirective=context.cpi_supervisor_directive,
        repairEscalationBlock="(see Tactical Directive below — LEVEL 2+ metacognitive shift active)",
    )
    extra_l6 = Template(_ESCALATED_REPAIR_L6_EXTRA).safe_substitute(
        escalationLevel=str(escalation_level),
        loopAttempt=f"{attempt}/{max_attempts}",
        targetFile=target_file,
        tacticalDirective=tactical_directive,
    )
    l6 = f"{base_l6}\n{extra_l6}"
    l5_sections = [tactical_directive, _REPAIR_L5, _REPAIR_L5_UNIFIED_DIFF]
    return _compose_acdp_prompt(
        l1=_CPI_L1,
        l2=_CPI_L2,
        l3_core=_join_sections(_CPI_L3, _REPAIR_L3, _L3_SYSTEMIC_BUG_REGISTRY),
        l4=_join_sections(_CPI_L4, _REPAIR_L4),
        l5_core=_join_sections(*l5_sections),
        l6=l6,
    )


def visual_refine_attached_images() -> list[dict[str, str | int]]:
    """Return image-role metadata embedded in visual-refine user JSON.

    Returns:
        Three descriptors (figma reference, Flutter render, diff heatmap) in display order.
    """
    return [dict(role) for role in _REFINE_IMAGE_ROLES]


def build_visual_refine_system_prompt(
    *,
    routing_enabled: bool = False,
    theme_variant: str = "material_3",
    stack_root: bool = False,
    surgical_widgets: bool = False,
    use_screen_ir: bool = False,
) -> str:
    """Build the LLM system prompt for visual refine (three PNGs + pixel diff).

    Reuses ``build_system_prompt`` with Figma PNG rules enabled, then appends refine-specific
    multimodal instructions. Optional surgical mode limits edits to snippet targets.

    Args:
        routing_enabled: Passed through to ``build_system_prompt``.
        theme_variant: ``material_3`` (default) or ``cupertino``.
        stack_root: When True, append STACK-root layout rules on the generate base.
        surgical_widgets: When True, append snippet-only edit constraints.

    Returns:
        System prompt string for ``visual_refine`` LLM calls.
    """
    return _render_generate_prompt(
        theme_variant,
        l1_purpose=_L1_REFINE,
        l3_principles_ext=_build_l3_extensions(
            routing_enabled=routing_enabled,
            figma_reference_attached=True,
            refine_multimodal=True,
        ),
        l5_actions_ext=_build_l5_extensions(
            routing_enabled=routing_enabled,
            stack_root=stack_root,
            refine_mode=True,
            surgical_widgets=surgical_widgets,
        ),
        use_screen_ir=use_screen_ir,
    )


def render_cpi_supervisor_prompt(context: CpiSupervisorContext) -> str:
    """Render the CPI loop-supervisor system prompt (optional repair escalation tier).

    Args:
        context: Historical patch and error metrics for stagnation detection.

    Returns:
        System prompt string for CPI supervisor structured output.
    """
    l6 = Template(_CPI_L6_TEMPLATE).safe_substitute(
        lastPatches=context.last_patches,
        recurringErrors=context.recurring_errors,
        figmaNodeIntent=context.figma_node_intent,
    )
    return _compose_acdp_prompt(
        l1=_CPI_L1,
        l2=_CPI_L2,
        l3_core=_CPI_L3,
        l4=_CPI_L4,
        l5_core=_CPI_L5,
        l6=l6,
    )
