"""L3 prompt principles and systemic bug guardrails."""

from __future__ import annotations

from figma_flutter_agent.llm.prompts.shared import _join_sections

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
    "NEVER list real clean-tree node ids in `omitFigmaIds` — omit is for decorative ids absent from the tree; the compiler strips real ids before emit.",
    "NEVER set `kind=extracted` in screenIr without a matching `extractedWidgets[].widgetName` and `widgetIr` — orphan refs are downgraded to inline emit.",
    "NEVER place flex-layout INPUT fields in the lower half of the screen without a scroll ancestor — IR validation sets `scrollAxis: vertical` on the nearest COLUMN or fails.",
    "If the screen contains any text input (`TextField` / INPUT nodes), NEVER hardcode absolute fixed parent heights (e.g. `Container(height: 844)`) — the software keyboard shrinks the viewport and causes bottom overflow; use scrollable or flexible constraints.",
    "Interactive hit targets (buttons, icon taps, links) MUST be at least 44×44 logical pixels; when Figma frames are smaller (e.g. 24×24 close icons), add transparent padding or `minTouchTarget` / `SizedBox` constraints — IR validation may auto-fix.",
    "NEVER output raw `Color(0xFF…)` literals or ad-hoc border radii unless explicitly forced — map fills and radii to ### tokens / `Theme.of(context)` / `AppColors` / `AppTypography`; IR `overrides` only accept registered token colors and typography sizes.",
    "NEVER place `Flexible`, `Expanded`, or unbounded `Row`/`Column` children directly inside a `Stack` — flex children belong under `Row`/`Column` only.",
    "NEVER wrap `Expanded` or `Flexible` inside `RepaintBoundary`, `SizedBox`, or `ConstrainedBox` when the flex child is a direct `Row`/`Column` descendant — emit `Expanded(child: RepaintBoundary(...))` (flex parent-data must sit directly under the flex host).",
    "NEVER emit `height: double.infinity`, `SizedBox.expand`, or cross-axis `SizedBox(height: double.infinity)` under `Row`/`Flexible` — scroll columns give unbounded cross-axis height; pin Figma `sizing.height` (or omit cross stretch) instead.",
    "NEVER emit `Positioned` inside a `Stack` without explicit bounds from cleanTree: provide both horizontal pins (`left` and `width`, or `left` and `right`) AND both vertical pins (`top` and `height`, or `top` and `bottom`) for BUTTON, INPUT, and CONTAINER nodes that host nested stacks.",
    "NEVER output interactive or text widgets inside a `Stack` without verifying width and height (or equivalent pin pairs) exist in cleanTree sizing — implicit loose stacks crash layout.",
    "NEVER use bare `theme.colorScheme` without `final ThemeData theme = Theme.of(context);` in the same `build` — always write `Theme.of(context).colorScheme` when no local binding exists.",
    "Button label colors on opaque fills MUST match Figma text fills from ### tokens / cleanTree — do not blindly substitute `onPrimary` when the design specifies black or custom label colors.",
    "NEVER instantiate `TextEditingController(...)` inside a `StatelessWidget.build` for static prefilled INPUT values — use `TextFormField(initialValue: ...)` or hoist the controller into a `StatefulWidget` parent.",
    "NEVER wrap a root `Stack` in artboard preview with `OverflowBox(maxHeight: double.infinity)` — `RenderStack` requires finite bounds; use a fixed `SizedBox` preview shell instead.",
    "NEVER pin a product-card quantity stepper to a narrow Figma slot width when the compiled stepper is wider — scale with `FittedBox` instead of forcing `SizedBox(width: …)` that overflows.",
    "NEVER emit a discount percent badge overlay on product hero imagery when the badge subtree is text-only and the hero already renders a full-bleed raster photo (badge pixels are baked into the export).",
    "NEVER wrap a card or form host with `InkWell`, `GestureDetector.onTap`, or `button-action` when descendant `BUTTON` nodes compile their own tap targets — emit a passive decorated container and keep inner buttons interactive.",
    "NEVER upscale the fixed Figma canvas with `FittedBox(fit: BoxFit.contain)` on full-screen backgrounds — prefer `BoxFit.scaleDown` or the template `BoxFit.cover` shell so typography does not stretch.",
    "NEVER mark a widget `const` when its subtree uses `MediaQuery.textScalerOf(context)`, `Theme.of(context)`, or other runtime `context` lookups.",
    "NEVER introduce `LayoutBuilder`, `MediaQuery.of(context).size`, or manual scale factors on coordinate literals — the engine wrappers own responsiveness.",
    "NEVER emit stray closing-bracket lines (`])))}}`) or semicolon-only lines — they break `dart format` and analyzer passes.",
    "NEVER emit layouts that never reach layout idle (infinite flex/stack relayout) — golden capture uses `pumpAndSettle` with a 20s cap and will fail refine without `flutter_render.png`.",
    "NEVER pin intrinsic button bodies (`button_should_flow_as_column`, stacked text column, composite row) with fixed `SizedBox(height: …)` inside bounded `Positioned` slots — use `ConstrainedBox(minHeight: …)` or grow the slot; otherwise `RenderFlex overflowed` fails signoff.",
    "NEVER subtract host padding from `OverflowBox` maxHeight/maxWidth when the wrapped subtree already includes that node's `Padding` — use the full positioned slot extent or flex children get starved (e.g. 12px Column inside 84px header slot).",
    "NEVER pin a fixed-height artboard shell with `SizedBox(height: …)` when descendants use intrinsic flow growth (`button_should_flow_as_column`, flow stacks) — use `ConstrainedBox(minHeight: …)` so `grow_then_gate` content is not clipped by the Figma frame cap.",
    "NEVER use `Alignment.start` — map to `AlignmentDirectional.centerStart`, `Alignment.centerLeft`, or `Align(alignment: ...)` per flex/stack context.",
    "NEVER use `Image.network` for static Figma assets — use `Image.asset` / `SvgPicture.asset` paths from ### assetManifest.",
    "NEVER declare helper `*Widget` classes at the end of screenCode — prebuilt subtree widgets already live in separate files; reference them only with `const WidgetName()` (imports are wired by the generator).",
    "NEVER emit `SizedBox.shrink()` placeholder widget classes — they hide real assets and break golden capture.",
    "NEVER reference `_artboardPreviewWidth` or `_artboardPreviewHeight` in screenCode — those static fields belong only to `GeneratedScreenShell`; your screen class `build()` must not contain any artboard preview conditional.",
    "NEVER reference `designWidth`, `designHeight`, `canvasWidth`, or `canvasHeight` in screenCode — artboard sizing belongs in `lib/generated/*_layout.dart` only; screen `build()` must delegate via `GeneratedScreenShell(child: const FeatureLayout())`.",
    "NEVER emit `designWidth` / `designHeight` without a matching `const double designWidth` / `designHeight` declaration in the same scope — compiler scroll/viewport code uses `constraints.maxWidth` / `constraints.maxHeight` instead.",
    "NEVER emit Dart class names starting with a digit (e.g. `01SplashScreen`) — feature folders like `01_splash` compile to `N01SplashScreen` / `N01SplashLayout`.",
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

_REPAIR_L3_IR_PATCHES = """- SCREEN IR REPAIR (MANDATORY): When `currentScreenIr` is present you MUST NOT emit `screenCode` patches. Fix the screen graph only via `irPatches` (each `figmaId` must exist in currentScreenIr / cleanTree).
- For analyzer errors such as \"isn't a class\", `undefined_method`, or wrong widget constructor: align EXTRACTED refs in screenIr with `extractedWidgets` / deterministic widget files — use `irPatches` to add or fix `kind=extracted` nodes (`ref.widgetName` must match a public `*Widget` class).
- IR patch fields: `replaceSubtree` (full WidgetIrNode), `overrides` (`text` / `accessibilityLabel` only), `reorderChildren` (figma id list). Never put Dart, widgets, or theme calls inside IR JSON.
- Unified-diff `patches` are ONLY for `extractedWidget` targets with a planned Dart path (syntax fixes)."""

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

