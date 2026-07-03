# Element Layout Laws & Control Contracts

> Status: **DESIGN / SPEC (report-only).** This document is an architecture analysis and
> specification. It defines **no production behavior** and changes **no emit**. It is written
> so that a later implementation agent can fix concrete defects (e.g. textbox inner-text
> vertical centering) by applying a typed `TextInputContract` layout law, without needing
> product context.
>
> Date: 2026-06-13 · Author role: architecture analyst/reviewer · Repo: `paleophonix/figma-flutter-agent`

---

## 1. Executive summary

The compiler today runs **two parallel, decoupled recognition systems**, and the one that
actually ships by default is the weakest one:

1. **System A — semantic recognition (typed, mostly dormant).**
   The LLM emits *report-only* `semanticVerdicts` / `semanticSummary`
   (`schemas/ir.py:249-302`), and a deterministic classifier
   (`parser/semantics/classify.py`) assigns a `WidgetIrKind` + typed `KindPayload`
   (`schemas/ir_payloads.py`) + a `FidelityTier` to each node. There is even a native
   Jinja emit path (`generator/ir/semantic_emit.py`). **But** native emit is gated off by
   `agent.semantics.report_only = True` (default, `config/models.py:97`) **and** by
   `fidelity_tier == native_verified` (`generator/ir/fidelity/router.py:31-33`). So in the
   default configuration the typed recognition is computed and then **discarded at emit
   time**.

2. **System B — legacy structural emit (untyped, authoritative in practice).**
   `generator/layout/widgets/emit/dispatch.py` → `parser/interaction/*` re-derive
   "is this a textarea / password / input / button / chip" directly from
   `CleanDesignTreeNode` geometry **and from layer names / text content**, then emit Dart.
   This is the path that produces the shipping widget tree, and this is where the
   vertical-centering bug lives.

**Consequence (the core problem stated in the task):** the system *does* recognize visual
structure (System A), but it does **not** apply a typed control contract at emit time. The
recognition result is not a binding contract; emit re-invents the control from incidental
Figma geometry and string heuristics.

**The textbox vertical-centering bug, concretely.** For a single-line input the legacy path
(`generator/layout/widgets/input/decoration.py` + `.../input/fields.py`) chooses inner-text
vertical position via **five competing `contentPadding` derivations** behind a `vertical_center`
flag, several of which read *incidental* values (`stack_placement.top`, `glyph_top_offset`,
per-edge Figma padding) rather than a single deterministic centering law. It also strips the
Material baseline (`InputBorder.none`) without re-establishing a bounded height + symmetric
vertical inset. The result is non-deterministic centering. Even the *native* template
`templates/widgets/input_text_field.dart.j2` is bare — it sets neither `textAlignVertical`
nor `contentPadding`, so it cannot enforce the law either.

**What this document proposes.** A typed **Element Contract** — a binding object that, once a
visual group is recognized as a textbox/button/chip/etc., carries: the control-boundary node,
owned label/hint/value/decoration nodes, state/value, accessibility role, native widget
mapping, **deterministic layout laws** (vertical alignment, content padding, baseline/metrics),
and explicit allowed/forbidden production effects + confidence/provenance. Recognition (LLM +
classifier) **proposes** a contract; a **policy gate** decides whether it is trusted enough to
apply; the **materializer/emitter** applies fixed laws and invents no geometry. Delivered in
five non-breaking stages, starting report-only.

---

## 2. Current pipeline inventory

The relevant decision points, in pipeline order. Each is tagged **[SEM]** (semantic /
recognition responsibility), **[LAY]** (layout responsibility), or **[EMIT]** (emit
responsibility), plus whether it encodes a **layout law** or only **incidental geometry**.

### 2.1 CleanDesignTree node typing — **[SEM]**, incidental

| Symbol | Responsibility |
|---|---|
| `schemas/types.py:17` `NodeType` | The closed set of clean-tree node types (`INPUT`, `BUTTON`, `CHECKBOX`, `SWITCH`, `RADIO`, `DROPDOWN`, `SLIDER`, …). This is the *first* place "what is this" is decided. |
| `parser/tree.py` `infer_leaf_type` (legacy) | Assigns `NodeType` partly from **layer names** ("input"/"button"/"card"). This is a known laundering source. |
| `parser/semantics/signals/type_trust.py:19` `semantic_signal_type` | **Downgrades** name-inferred `INPUT`/`BUTTON`/`CARD` to `CONTAINER` when the node id is in the legacy-name registry (`is_legacy_semantic_type_node`), so detectors don't trust the laundered passport. |

Finding: node typing mixes authoritative structural signals with name matching. The
`type_trust` shim is a *symptom*: it exists only because `node.type` is partly built from
names and cannot be trusted as-is.

### 2.2 IR classification — **[SEM]**, recognition (not yet a law)

| Symbol | Responsibility |
|---|---|
| `parser/semantics/prefilter.py:130` `plausible_kinds` | Cheap candidate set (2–8 kinds) per node from `node.type`, variant properties, geometry. Already uses some **string sniffing on variant values** (`"search"`, `"date"`, `"chip"`, …, lines 149-196). |
| `parser/semantics/detectors/*` (`inputs.py`, `actions.py`, `controls.py`, …) | Per-kind `RuleDetector` predicates scored by tier (`PROPERTIES > ANATOMY > GEOMETRY`). E.g. `inputs.py:16` `_is_input_text_field` = `signal_type == INPUT`. |
| `parser/semantics/arbiter.py` `arbitrate` / `merge_signals` | Picks a winner among candidate classifications, applies confidence threshold + grey-zone, returns kind + payload. |
| `parser/semantics/classify.py:107` `classify_node` / `:196` `classify_screen_ir` | Walks IR ∥ clean tree, assigns `WidgetIrKind` + `KindPayload`, builds a report. `authoritative_classifier=True` even **resets an LLM-proposed kind to `AUTO`** and re-derives it deterministically (`classify.py:220-226`). |
| `generator/ir/passes/semantic.py:13` `classify_screen_ir_pass` | The classifier as a registered IR pass. `mutates = {screen_ir.kind, payload, classification_hint}`. |

Finding: this layer produces a *recognition result* (kind + payload), not a *contract*. It
does not record which child nodes are the label/hint/value, and its output is consumed only
by the (gated-off) native emit.

### 2.3 `WidgetIrKind` selection & payloads — **[SEM]**, typed but thin

| Symbol | Responsibility |
|---|---|
| `schemas/ir.py:13` `WidgetIrKind` | Large enum: MVP kinds (`INPUT_TEXT_FIELD`, `BUTTON_FILLED`, `CHIP_CHOICE`, `CONTAINER_CARD`, `CONTAINER_LIST_TILE`, `NAV_SCROLL_HOST`, `TECHNICAL_DIVIDER`) + many backlog **stubs** (enum-only, no emit). |
| `schemas/ir.py:74` `SEMANTIC_MVP_IR_KINDS` / `:88` `STUB_IR_KINDS` | The MVP kinds have emit; stubs fall back to layout emit with a warning (`expression.py:143-148`). |
| `schemas/ir_payloads.py` `KindPayload` (`ChipChoicePayload`, `InputTextFieldPayload`, `GenericSemanticPayload`) | The only typed payloads. `InputTextFieldPayload` carries `hint_text`, `error_text`, `is_multiline`, `max_lines` — **no node-ownership, no layout law, no metrics**. |
| `schemas/ir_payloads.py:10` `LlmClassificationHint` | LLM grey-zone hint, `confidence 0.0–1.0`, "never authoritative on its own". |

Finding: `InputTextFieldPayload` is the natural home for an input contract, but today it
encodes *content* (hint/value/multiline) only, not *ownership* (which nodes) or *laws*
(alignment/padding/baseline).

### 2.4 Materialization (IR → generator/Dart) — **[LAY]/[EMIT]**, dual path

| Symbol | Responsibility |
|---|---|
| `generator/ir/materialize.py:31` `materialize_screen_code_from_ir` | Orchestrates: normalize presence → validate/guards → layout passes → **classification passes** → `stamp_fidelity_tiers` → `emit_screen_code_from_ir`. |
| `generator/ir/screen.py:14` `emit_screen_code_from_ir` | Merges IR onto clean tree, emits screen body + scaffold shell. |
| `generator/ir/expression.py:81` `emit_widget_expression` | **The fork.** If `kind in SEMANTIC_MVP_IR_KINDS` **and** `_semantic_mvp_emit_enabled(ctx)` (i.e. *not* `report_only`): route by fidelity tier → native template / styled primitive / baked. Otherwise (and always under default `report_only=True`): fall through to `render_leaf_body` (System B). |
| `generator/ir/expression.py:47` `_semantic_mvp_emit_enabled` | Reads `agent.semantics.report_only`. **Default True ⇒ native path off.** |
| `generator/ir/fidelity/router.py:31` `tier_allows_native` | Native template allowed **only** for `FidelityTier.NATIVE_VERIFIED`. Everything else → styled primitive / baked. |

Finding: even with `report_only=False`, native emit fires only for `native_verified` nodes;
all others get `emit_styled_primitive`, which for `INPUT_TEXT_FIELD` produces a `DecoratedBox`
wrapping `render_leaf_body` (System B again) — **not** a real `TextField`
(`generator/ir/fidelity/styled_emit.py:75-84,116`).

### 2.5 Input / text / button / chip emit (System B) — **[EMIT]**, incidental-geometry heavy

| Symbol | Responsibility | Law or incidental? |
|---|---|---|
| `generator/layout/widgets/emit/dispatch.py:39` `render_node_body` | Recursive dispatcher. Re-detects textarea / consent row / payment selection / pill / checkbox / input-trailing-icon **from the clean node**, independent of `WidgetIrKind`. | incidental — structural + name/text heuristics |
| `.../input/fields.py:54` `_render_stack_input`, `:217` `_render_flex_input_with_trailing_chrome`, `:155` `_render_textarea_field` | Build the actual `TextField`/`TextFormField`. Compute `vertical_center = field_height > 0` and conditionally add `textAlignVertical: TextAlignVertical.center`. | **partial law** (centering attempted) but driven by incidental height/geometry |
| `.../input/decoration.py` | **Five** competing `contentPadding` builders: `_flex_input_content_padding`, `_optical_single_line_input_content_padding`, `_input_content_padding`, `_planner_input_content_padding`, plus a symmetric fallback; selected by an if/elif cascade in `_stack_input_decoration:167-271`. | incidental — reads `stack_placement.top`, `glyph_top_offset`, per-edge padding |
| `.../input/decoration.py:17` `_input_style_line_box_height` | Computes line-box height from `TextMetricsFrame.line_height_px` / `glyph_height` / `font_size·line_height`. | **law-shaped** (the right input to a centering law) but only used inside the cascade |
| `.../button/core.py:209` `_wrap_button_stack` | Wraps a stack in Material `InkWell`/Cupertino tap target, paints fill/border/shadow/shine from the **painted surface** heuristics. Emits `Container`+`InkWell`+label, **never** `FilledButton`/`OutlinedButton`. | incidental |
| `generator/ir/fidelity/styled_emit.py` | Themed primitive shells per kind (chip/button/input/card). For inputs, no real field. | partial law (theme) |
| `parser/interaction/forms.py`, `input_fields.py`, `chips.py`, `buttons.py`, `selection.py` | The detector library System B calls: `looks_like_textarea_field` (**name contains "textarea"**, `forms.py:305-307`), `looks_like_password_field_stack`, `input_hint_node` (**first TEXT child** = hint, `input_fields.py:42-47`), `input_value_style_node` (**longest TEXT** = value), `input_hint_implies_obscure_text` (**"password" in hint**), `is_link_text` (label hint list), `_is_input_visibility_affordance` (**"eye"/"visibility" in name**). | incidental + **name/text production heuristics** |

### 2.6 Text metrics / baseline / vertical alignment — **[EMIT]**, partial law

| Symbol | Responsibility |
|---|---|
| `schemas/geometry.py:108` `TextMetricsFrame` | Parsed glyph metrics: `line_height_px`, `glyph_top_offset`, `glyph_height`, `font_size`, `delta_top`, `input_padding_top/bottom`, `strut_height_ratio`, `baseline_verifiable`. **The data needed for a centering law already exists.** |
| `generator/layout/widgets/emit/text.py:46` `render_text_node` | Decides `StrutStyle`, optical centering, `textAlign`, multi-line splitting — via many parent/style heuristics (`omit_glyph_strut` cascade, `text.py:88-106`). |
| `generator/layout/style` `strut_style_expr`, `should_emit_strut_style`, `text_widget_trailing_params` | StrutStyle + trailing params for `Text`. |

Finding: glyph metrics are parsed and partly consumed, but vertical alignment is decided by
scattered conditionals, not by one owner.

### 2.7 Style & padding derivation — **[EMIT]**, mixed

| Symbol | Responsibility |
|---|---|
| `generator/layout/style/colors.py`, `style/decoration.py` | Color/border/radius/shadow expressions from `node.style`. |
| `.../input/decoration.py` padding builders (see 2.5) | `contentPadding` for inputs — the centering payload. |
| `generator/layout/scroll.py` `padding_edge_insets` | Generic padding → `EdgeInsets`. |

### 2.8 Existing semantic payload / classification-hint usage — **[SEM]**

| Symbol | Responsibility |
|---|---|
| `schemas/ir.py:226` `WidgetIrNode.classification_hint` | LLM grey-zone hint on a node; only used when `llm_gray_zone_annotations=True` (default False). |
| `schemas/ir.py:225` `WidgetIrNode.payload` | Typed `KindPayload`, auto-built in `validate_kind_payload` (`ir.py:233-246`). |
| `schemas/ir.py:298-302` `ScreenIr.semantic_summary` / `semantic_verdicts` | **Report-only** LLM annotations. Populated by the LLM structured response only (prompt `llm/prompts/environment.py:19-23`: *"proposedEffects are suggestions only — the compiler and emitter do not apply them"*). **Never read by emit.** |
| `generator/ir/passes/semantic.py` + provenance | Records classifier decisions + checkpoint `CP2_semantic`; writes a classification report to disk. |

**Inventory verdict.** Recognition (2.1–2.3, 2.8) and emit (2.4–2.7) are connected by exactly
one thin wire — `WidgetIrKind` + `KindPayload` — and that wire is cut at emit by
`report_only` and `tier_allows_native`. The verdicts (the richest recognition output) are not
wired to emit at all. There is no object that says *"this is an input, these are its parts,
and here is the law that governs its layout."* That object is the **Element Contract**.

---

## 3. The Element Contract model

An **Element Contract** is the binding result of recognizing a visual group as a typed control.
It is **not** `role = text_input`. It is a closed record with the following fields. (Pydantic
sketch; field names are proposals, not yet code.)

```python
class ElementContract(BaseModel):
    # --- identity ---
    control_node_id: str                 # the control BOUNDARY node (the field/button frame)
    role: ControlRole                     # closed enum: text_input | button | chip | rating | ...
    subtype: str | None                   # single_line | multiline | password | search | email | phone ...
    native_widget: NativeWidgetMapping    # TextFormField | FilledButton | ChoiceChip | ...

    # --- owned parts (node ids, all must exist in clean tree) ---
    label_node_ids: list[str]             # field label / caption (NOT inner text)
    hint_node_ids: list[str]              # placeholder copy
    value_node_ids: list[str]             # prefilled value copy
    decoration_node_ids: list[str]        # leading/trailing icons, prefix/suffix chrome

    # --- state / data ---
    state: ControlState | None            # default | disabled | loading | selected | error
    value: Any | None                     # selected value / rating value / checked
    options: list[ContractOption]         # for chips/segmented/radio/rating

    # --- accessibility ---
    a11y_role: str | None                 # textField | button | checkbox | ...
    a11y_label_source: Literal["label", "hint", "value", "explicit"] | None

    # --- layout laws (parameters, NOT Dart) ---
    layout_law: LayoutLawSpec             # see §4/§5: alignment, padding source, metrics policy

    # --- production effects governance ---
    allowed_effects: frozenset[ProductionEffect]
    forbidden_effects: frozenset[ProductionEffect]

    # --- trust ---
    confidence: float                     # 0..1
    provenance: ContractProvenance        # see below
```

Supporting types:

```python
class LayoutLawSpec(BaseModel):
    vertical_align: Literal["center", "top", "bottom"]   # the LAW, not a guess
    horizontal_align: Literal["start", "center", "end"]
    content_padding_source: Literal["contract_token", "metrics_derived", "control_default"]
    content_padding: EdgeInsetsSpec | None               # resolved px, derivation pinned
    line_box_source: Literal["text_metrics_frame", "font_size_fallback"]
    pin_height: bool                                     # bound the control height for centering
    min_height: float | None                             # native min (e.g. 48 for inputs)

class ContractProvenance(BaseModel):
    source: Literal["llm_verdict", "deterministic_classifier", "both"]
    classifier_kind: WidgetIrKind | None
    classifier_confidence: float | None
    llm_confidence: float | None
    evidence: dict[str, Any]                             # the detector evidence dict
    requires_policy_gate: bool = True                    # never applied without a gate

class ProductionEffect(StrEnum):
    LOWER_TO_NATIVE_INPUT = "lower_to_native_input"      # emit a real TextField
    APPLY_VERTICAL_CENTER_LAW = "apply_vertical_center_law"
    OBSCURE_TEXT = "obscure_text"
    SET_SELECTED_STATE = "set_selected_state"
    LOWER_TO_NATIVE_BUTTON = "lower_to_native_button"
    # ...
```

### What a contract must guarantee

1. **Boundary identity.** Exactly one `control_node_id`. All owned node ids are descendants of
   (or the) boundary node. No overlap between `label`/`hint`/`value`/`decoration` sets.
2. **Ownership totality for the law it claims.** If `role == text_input` and it claims
   `APPLY_VERTICAL_CENTER_LAW`, then it must resolve `hint_node_ids` *or* `value_node_ids`
   (the inner copy the law centers) and a `line_box_source`.
3. **No Dart, no invented geometry.** `layout_law` carries *parameters* (align mode, padding
   source, metrics source). It never carries a Dart string. Pixel values, if present, are
   *derived* from contract-owned metrics/tokens with a pinned `content_padding_source`.
4. **Effect gating.** A contract proposes `allowed_effects`; emit may apply only effects that
   are both in `allowed_effects` **and** authorized by the policy gate (§6).
5. **Provenance + confidence.** Every contract records where it came from and how confident.
   `requires_policy_gate=True` until a policy explicitly clears it.

---

## 4. Text input contracts

`role == text_input`, `subtype ∈ {single_line, multiline, password, search, email, phone}`.

### 4.1 Required semantic fields (per subtype)

| Field | single_line | multiline | password | search | email/phone |
|---|---|---|---|---|---|
| `role` | `text_input` | `text_input` | `text_input` | `text_input` | `text_input` |
| `subtype` | `single_line` | `multiline` | `password` | `search` | `email`/`phone` |
| `control_node_id` | required | required | required | required | required |
| `label_node_ids` | optional | optional | optional | optional | optional |
| `hint_node_ids` (placeholder) | optional | optional | optional | optional | optional |
| `value_node_ids` | optional | optional | **must be masked, never carry the cleartext** | optional | optional |
| `decoration_node_ids` | optional | optional | eye/visibility toggle if present | leading search glyph | optional |
| `is_multiline` | `false` | `true` | `false` | `false` | `false` |
| `max_lines` | `1` | known or `null` | `1` | `1` | `1` |
| `state` | optional | optional | optional | optional | optional |
| keyboard hint | `text` | `multiline` | `visiblePassword`/`text` | `text` | `emailAddress`/`phone` |

Notes:
- `password` subtype must be established from **structure/decoration/variant**
  (mask glyphs, eye affordance, component variant), **not** from the word "password" in the
  hint text. Today this is `input_hint_implies_obscure_text` (`forms.py:390-397`) — a text
  heuristic the contract replaces.
- `search` / `email` / `phone` subtypes are relevant only when there is a non-text signal
  (variant axis, dedicated `NodeType`, keyboard component, leading search glyph). Absent that,
  classify as `single_line`. Do **not** sniff "search"/"@"/digits from copy for production.

### 4.2 Text input layout laws (precise, deterministic)

These are the laws an implementation agent applies. `H` = resolved control-boundary height
(px); `L` = resolved line-box height of the inner copy style (px); `pad_l`,`pad_r` = horizontal
insets from the contract token.

- **LAW-TI-1 (single-line vertical center).** When `is_multiline == false`, the inner editable
  **and** the hint MUST be vertically centered within the control boundary. Realized by **all
  three** of:
  1. `textAlignVertical: TextAlignVertical.center`,
  2. a **bounded height** on the field (`SizedBox(height: H)`, or `ConstrainedBox(minHeight: max(H, min_height))` when HUG), and
  3. **symmetric** vertical content padding `v = max(0, (H − L) / 2)` (top == bottom),
     with `content_padding_source = metrics_derived`.

  Forbidden inputs to `v`: `stack_placement.top`, `glyph_top_offset`, asymmetric per-edge
  Figma padding. (These are exactly what `_input_content_padding` / `_flex_input_content_padding`
  read today, `decoration.py:117-164`.)

- **LAW-TI-2 (multiline top align).** When `is_multiline == true`,
  `textAlignVertical: TextAlignVertical.top`, `maxLines: max_lines or null`,
  `minLines` from contract (default ≥3 only if the boundary height implies it),
  top-anchored content padding from the contract token (`content_padding_source = contract_token`).

- **LAW-TI-3 (content padding source).** `content_padding` MUST come from the contract:
  either an explicit control padding token, or a single `metrics_derived` computation
  (LAW-TI-1). There MUST NOT be five competing derivations chosen by an if/elif cascade
  (current `decoration.py:167-271`). The line-box `L` MUST come from `TextMetricsFrame`
  (`line_box_source = text_metrics_frame`); `font_size`-only is a fallback that MUST set
  `line_box_source = font_size_fallback` and lower confidence.

- **LAW-TI-4 (label ownership).** Text in `label_node_ids` MUST NOT become the inner field
  text/hint/value. It is rendered as a sibling (`Text` above/beside the field) or as
  `InputDecoration.labelText`. It is never the editable content. (Prevents the
  "label treated as field value" failure mode that `input_hint_node` = first TEXT child can
  cause, `input_fields.py:42-47`.)

- **LAW-TI-5 (hint ownership).** Text in `hint_node_ids` MUST be emitted as
  `InputDecoration.hintText` (+ `hintStyle` from the hint node's style), **never** as a
  separately positioned `Text` child once the control is lowered to a native input.

- **LAW-TI-6 (value ownership).** Text in `value_node_ids` MUST be emitted as
  `initialValue` (or controller text), **never** positioned by arbitrary child geometry.

- **LAW-TI-7 (decoration ownership).** Nodes in `decoration_node_ids` MUST map to
  `prefixIcon`/`suffixIcon`, not free siblings. The password eye affordance lives here.

- **LAW-TI-8 (metrics over bounds).** Vertical alignment MUST consider text metrics
  (`L` from `TextMetricsFrame`), not box bounds alone. Box height alone determines `H`, not the
  centering offset.

- **LAW-TI-9 (baseline restoration).** If borders are removed (`InputBorder.none`), the law
  MUST re-establish a bounded height (LAW-TI-1.2) so `textAlignVertical.center` has a frame to
  center within. Removing the border without pinning height is forbidden.

### 4.3 Emit implications

- **When to lower into `TextField`/`TextFormField`:** only when the contract is policy-gated to
  `LOWER_TO_NATIVE_INPUT` (§6) **and** ownership totality holds (one boundary; resolved
  hint/value; metrics or token padding). With no prefilled value → `TextField`; with a
  contract value → `TextFormField(initialValue: …)` (matches today's `_prefilled_input_field_expr`,
  `fields.py:30-51`).
- **When to preserve as visual-only container:** when the contract is *not* gated, or
  ownership is incomplete, or the node is recognized but only for layout (e.g. a read-only
  display field). Then emit the styled primitive / container — but it must still respect the
  **vertical-center law for the inner Text** when `vertical_align == center`.
- **Visual fidelity vs native layout:** the painted surface (fill/radius/border/shadow) is
  carried by the boundary node's `style` and wraps the native field
  (`Container(decoration: …, child: TextField(…))`), as today (`fields.py:119-148`). The
  native input owns inner alignment; the wrapper owns chrome. They do not fight because the
  law pins `H` on the wrapper and centers within it.
- **What stays report-only until policy-gated:** subtype inference (password/search/email),
  `OBSCURE_TEXT`, and `LOWER_TO_NATIVE_INPUT`. Until gated, these are recorded on the contract
  and surfaced in the report; emit does not act on them.

---

## 5. Other control contracts (high level)

For each: what **recognition** owns, what **layout law** follows, what the **emitter must not
guess from text/name alone**.

### 5.1 Button / primary button (`role = button`)
- **Recognition owns:** boundary node; `subtype ∈ {filled, outlined, text, icon, fab}` from
  variant/style/fill (filled = solid brand fill; outlined = border + transparent fill; text =
  no chrome); label node(s); leading/trailing icon nodes; `state` (disabled from variant).
- **Layout law:** label centered (LAW shared with chips); content padding from contract token
  or symmetric metrics; on FILL width → full-width with pinned height; native mapping
  `FilledButton`/`OutlinedButton`/`TextButton`/`IconButton`. Label color from the button's
  `onX` role, not force-white.
- **Emitter must not guess:** subtype from label text ("LOG IN"); disabled from copy;
  filled-vs-outlined from name. Today buttons are `Container`+`InkWell`
  (`button/core.py:209`) — fidelity is fine but the *role* and label-color are surface
  heuristics, not contract.

### 5.2 Chip / choice chip / filter chip (`role = chip`, subtype `choice|filter|input|action`)
- **Recognition owns:** boundary; label node; **selected state from component variant / fill /
  style token**, not from text; leading icon node.
- **Layout law:** label vertically centered; symmetric padding; selected ⇒ container/label
  color from the selected variant tokens; native `ChoiceChip`/`FilterChip` with `selected:`.
- **Emitter must not guess:** selected from the word "selected"/active-looking copy. Today
  `ChipChoicePayload.is_selected` exists (`ir_payloads.py:28-34`) and `is_selected` is
  validated (`ir.py:240-245`) — the contract formalizes its **source** (variant/style).

### 5.3 Rating / star rating (`role = rating`)
- **Recognition owns:** boundary; the repeated star/segment option nodes; **value from the
  count of filled vs empty option variants/fills**, not from a number in a sibling label.
- **Layout law:** fixed item size + gap from contract; value clamped to `[0, options]`; native
  `RatingBar`-equivalent or row of icons reflecting `value`.
- **Emitter must not guess:** the rating value from copy ("4.5") or from name.

### 5.4 Checkbox / switch / radio (`role = selection`)
- IR support exists: `NodeType.CHECKBOX/SWITCH/RADIO/RADIO_GROUP` (`types.py`) and detectors
  (`detectors/controls.py`, `selection.py`).
- **Recognition owns:** boundary; checked/on state from variant/fill (`variant_is_checked`);
  label node; group membership for radio.
- **Layout law:** control + label aligned on a shared baseline/center; tap target ≥48; native
  `Checkbox`/`Switch`/`Radio` with `value:`/`groupValue:`.
- **Emitter must not guess:** checked from a check-glyph asset name; on/off from copy.

### 5.5 Nav / app bar / system chrome (`role = nav`)
- **Recognition owns:** boundary; bar type (app bar / bottom nav / tab bar) from position +
  variant; item nodes; selected index from variant.
- **Layout law:** docked position from contract (top/bottom), **not** absolute `Positioned(top:738)`
  on a fixed-height artboard (a known FID-21 failure); native `AppBar`/`NavigationBar`/`TabBar`.
- **Emitter must not guess:** bar role from name; selected tab from copy.

---

## 6. Layout law ownership

Strict three-tier ownership. Arrows of authority point downward; lower tiers may never assume
a higher tier's responsibility.

### LLM / IR semantic output **may decide (propose only)**
- This visual group is a text input / button / chip / rating / …
- This node is the **control boundary**.
- These nodes are **label / hint / value / decoration**.
- A **proposed** control contract (role, subtype, ownership, suggested effects), report-only.

It may **not**: generate Dart; set arbitrary geometry/pixels; force a production effect;
override the deterministic classifier (`classify.py:220-226` already resets LLM kinds to
`AUTO` and re-derives).

### Compiler policy **may decide**
- Whether a proposed contract is **trusted enough to apply** (confidence + provenance +
  agreement between LLM verdict and deterministic classifier).
- Whether a given **production effect is allowed** for this contract (intersection of
  `allowed_effects` and the policy's per-effect risk class).
- Whether **high-risk** behavior (e.g. `LOWER_TO_NATIVE_INPUT`, `OBSCURE_TEXT`) is permitted in
  the current run profile (`strict_fidelity` / `strict_a11y` / `report_only`).

It may **not**: invent ownership the recognition didn't provide; emit Dart.

### Materializer / emitter **must decide**
- The **exact** Flutter widget structure for a gated contract.
- The **exact** padding/baseline/alignment application, per the §4/§5 laws — deterministically,
  from contract-owned metrics/tokens.
- It MUST invent **no** geometry and **no** text. If the law needs a value the contract didn't
  supply, it falls back to the documented `*_fallback` source and lowers confidence — it does
  not guess.

**Explicit invariants:**
- **LLM does not generate Dart.**
- **LLM does not directly set arbitrary geometry.**
- **LLM proposes a contract; the compiler applies the laws.**
- **`semantic_verdicts` / `ElementContract` are never production authority by themselves** —
  the policy gate is the only path from proposal to effect.

---

## 7. Failure modes the contracts must prevent

| # | Failure mode | Current root | Contract law that prevents it |
|---|---|---|---|
| F1 | Textbox hint/value not vertically centered | 5 competing padding derivations + incidental `stack_placement`/`glyph_top_offset` (`decoration.py:117-271`); native template bare (`input_text_field.dart.j2`) | LAW-TI-1, LAW-TI-3, LAW-TI-8, LAW-TI-9 |
| F2 | Multiline textarea treated as single-line (or vice-versa) | `looks_like_textarea_field` keys on **name contains "textarea"** (`forms.py:305-307`) | `subtype`/`is_multiline` from contract structure; LAW-TI-2 |
| F3 | Label treated as field value/hint | `input_hint_node` = **first TEXT child**, `input_value_style_node` = **longest TEXT** (`input_fields.py:42-47,99-125`) | LAW-TI-4 (label ownership disjoint from hint/value) |
| F4 | Placeholder emitted as separate `Text` instead of `hintText` | positioned hint child in stack inputs | LAW-TI-5 |
| F5 | Chip selected state inferred from text | name/copy heuristics | §5.2: selected from variant/style only |
| F6 | Button emitted as generic container/text without role | `Container`+`InkWell` only (`button/core.py`) | §5.1: native mapping + role from variant/style |
| F7 | Accessibility role missing/derived from copy | `Semantics(label: hint)` ad hoc (`fields.py:151`) | `a11y_role` + `a11y_label_source` on contract |
| F8 | Direct `node.name`/`text` heuristics drive production | `input_hint_implies_obscure_text` ("password"), `is_link_text`, `_is_input_visibility_affordance` ("eye") (`forms.py`) | subtype/effects from structure/variant; text heuristics demoted to report-only signals |
| F9 | Component metadata ignored or over-trusted | `type_trust` launders names but variant data underused; `authoritative_classifier` can discard LLM ownership | provenance records both sources; policy requires agreement for high-risk effects |
| F10 | Password cleartext leaked through value | `value_node_ids` could carry mask/cleartext | §4.1: password value masked, never cleartext |

---

## 8. Acceptance tests (proposed, for future implementation)

Tests are grouped by the three distinct concerns. **None of these may pass by changing emit
during the report-only stage** — see the ordering in §9.

### 8.1 Report-only semantic contract recovery (Stage 1)
- `test_semantic_contract_report_does_not_change_emit` — generating a fixture with contract
  recovery **on** produces byte-identical Dart to recovery **off** (report-only proven).
- `test_text_input_contract_recovers_control_boundary` — for an input fixture, the recovered
  contract has exactly one `control_node_id` equal to the field frame.
- `test_text_input_contract_separates_label_and_placeholder` — label node id ∈ `label_node_ids`,
  placeholder node id ∈ `hint_node_ids`, sets disjoint (guards F3/F4).
- `test_textarea_contract_marks_multiline_from_structure` — a tall multi-line shell recovers
  `subtype=multiline, is_multiline=true` **without** relying on the layer name "textarea" (F2).
- `test_password_contract_subtype_from_structure_not_text` — mask-glyph / eye-affordance fixture
  recovers `subtype=password`; a fixture whose only password signal is the word "password" in
  copy does **not** (F8).
- `test_chip_contract_recovers_selected_state_from_variant_or_style` — selected chip recovers
  `value/selected=true` from variant/style; a chip whose copy merely *reads* active does not (F5).
- `test_rating_contract_recovers_value_from_option_variants` — value derived from filled-option
  count, not sibling number text (F5/rating).
- `test_contract_records_provenance_and_confidence` — every recovered contract has
  `provenance.source` and a `confidence`.

### 8.2 Policy-gated contract application (Stage 3+)
- `test_policy_gate_required_before_contract_application` — with the gate denying, emit is
  unchanged even though a contract exists.
- `test_policy_gate_low_risk_contract_applies` — a low-risk contract (e.g. `TECHNICAL_DIVIDER`
  or chip selected-state) passes the gate and changes emit deterministically.
- `test_policy_gate_blocks_high_risk_without_agreement` — `LOWER_TO_NATIVE_INPUT` is blocked
  when LLM verdict and deterministic classifier disagree (F9).
- `test_strict_profiles_reject_unverified_native` — under `strict_fidelity`, an
  unverified-tier input is not lowered to native (mirrors `router.py:62-66`).

### 8.3 Emitter layout-law enforcement (Stage 4+)
- `test_single_line_input_contract_centers_inner_text` — emitted field has
  `textAlignVertical: TextAlignVertical.center`, a bounded height, and **symmetric** vertical
  `contentPadding` with `top == bottom` (LAW-TI-1).
- `test_textarea_contract_top_aligns_hint_text` — emitted field has
  `textAlignVertical: TextAlignVertical.top` and `maxLines: null` (LAW-TI-2).
- `test_input_content_padding_has_single_source` — the emitted `contentPadding` is produced by
  the one contract-driven builder; assert the legacy 5-way cascade is not consulted (LAW-TI-3).
- `test_input_line_box_uses_text_metrics_frame` — `L` is sourced from `TextMetricsFrame`; with
  metrics absent, `line_box_source == font_size_fallback` and confidence is lowered (LAW-TI-8).
- `test_password_contract_obscures_only_when_gated` — `obscureText: true` appears only when the
  `OBSCURE_TEXT` effect is both allowed and gated (not from text) (F8/F10).
- `test_placeholder_lowered_to_hint_text_not_sibling` — no positioned `Text` for the
  placeholder; it is `InputDecoration.hintText` (LAW-TI-5).
- `test_label_not_lowered_into_field_value` — label text never appears as `initialValue`/inner
  text (LAW-TI-4).
- `test_border_none_pins_bounded_height` — when `InputBorder.none`, the emit wraps a bounded
  height so centering is well-defined (LAW-TI-9).

---

## 9. Staged implementation plan

Each stage lists **scope**, **forbidden changes**, **acceptance criteria**, **risks**.
Gate: a stage does not start until the previous stage's acceptance criteria are green.

### Stage 1 — Report-only contract recovery inside the existing IR structured call
- **Scope:** add the `ElementContract` model (§3) and recover contracts from existing inputs:
  the deterministic classifier output (`classify_screen_ir`), the LLM `semanticVerdicts`, and
  parsed metrics/variant. Attach as a new **report-only** field (e.g.
  `ScreenIr.element_contracts`) and write them into the existing classification report
  artifact. Reuse `semantic_verdicts` as one input source.
- **Forbidden:** any change to `emit_widget_expression` / System B; flipping `report_only`;
  reading contracts at emit; new name/text production heuristics.
- **Acceptance:** §8.1 tests; `test_semantic_contract_report_does_not_change_emit` is the gate.
- **Risks:** schema churn on `ScreenIr` (extra field is additive, `extra="forbid"` tolerates it
  only on the model that declares it — keep it on `ScreenIr`, not nodes, in this stage).

### Stage 2 — Compare recovered contracts against current compiler output
- **Scope:** an offline diff/report (CLI or test artifact) that, per fixture, lists where the
  recovered contract's law (e.g. expected vertical-center padding) **disagrees** with what
  System B currently emits. No behavior change — this quantifies the gap and builds the corpus.
- **Forbidden:** mutating emit; gating; baseline updates.
- **Acceptance:** report enumerates F1–F10 occurrences on the fixture corpus with node ids;
  reproducible.
- **Risks:** the comparison must parse current Dart output read-only (no AST mutation).

### Stage 3 — Policy gate for one low-risk contract
- **Scope:** implement the policy gate (§6) and wire it for **one** low-risk effect — recommend
  chip **selected-state** (`SET_SELECTED_STATE`) or `TECHNICAL_DIVIDER`, both already MVP kinds
  with payloads. Gate keyed on confidence + provenance agreement.
- **Forbidden:** lowering inputs to native; touching the text-input law; broad rollout.
- **Acceptance:** §8.2 tests; the gated low-risk contract changes emit deterministically and
  only when gated.
- **Risks:** introducing a second authority over `is_selected`; keep the gate the single source.

### Stage 4 — Text input layout-law enforcement
- **Scope:** implement LAW-TI-1…TI-9 as **one** contract-driven content-padding / alignment
  builder; route the gated `TextInputContract` through it (native template path made
  law-complete: add `textAlignVertical`, bounded height, symmetric padding to
  `input_text_field.dart.j2` + its context builder). This is where the textbox vertical-center
  bug is fixed.
- **Forbidden:** keeping the 5-way cascade as a parallel authority for gated contracts; new
  name/text heuristics; changing ungated/legacy nodes' emit.
- **Acceptance:** §8.3 tests; the F1 fixtures from Stage 2 now center correctly; ungated nodes
  unchanged.
- **Risks:** divergence between native template and styled-primitive input paths — both must
  obey the same law; regressions on inputs that were *accidentally* correct via the cascade
  (the Stage 2 corpus is the safety net).

### Stage 5 — Migrate legacy shortcuts into the contract/policy system
- **Scope:** fold System B's name/text heuristics (`looks_like_textarea_field`,
  `input_hint_implies_obscure_text`, `_is_input_visibility_affordance`, `is_link_text`) into
  contract recognition (structure/variant signals) + policy, demoting the string checks to
  report-only signals with low weight. Retire the redundant padding builders.
- **Forbidden:** removing a heuristic before its contract replacement passes the corpus gate
  (avoid regressions); deleting pre-existing tests without replacement.
- **Acceptance:** burn-down — number of name/text production heuristics decreases; corpus
  fixtures stable; the cascade in `decoration.py` reduced to the single law.
- **Risks:** long tail of screens relying on a specific heuristic; migrate per-heuristic behind
  the corpus diff.

---

## 10. Explicit non-goals

This analysis task (and Stage 1) must **not**:
- implement production emit changes;
- update goldens/baselines;
- touch the repair bot / `stages/llm_repair`;
- change preview/oracle flow;
- change vector degradation behavior;
- add new text/name regex production heuristics;
- make `semantic_verdicts` / contracts production authority directly (the policy gate is the
  only path to an effect).

---

## Appendix A — Key file/line references

| Concern | Location |
|---|---|
| `WidgetIrKind`, `ScreenIr`, `SemanticControlVerdict` | `src/figma_flutter_agent/schemas/ir.py` |
| Typed payloads, `LlmClassificationHint` | `src/figma_flutter_agent/schemas/ir_payloads.py:10,28,37,60` |
| `TextMetricsFrame` (glyph metrics, input padding channels) | `src/figma_flutter_agent/schemas/geometry.py:108-123` |
| Deterministic classifier | `src/figma_flutter_agent/parser/semantics/classify.py:107,196` |
| Candidate prefilter (+ variant string sniffing) | `src/figma_flutter_agent/parser/semantics/prefilter.py:130-218` |
| Input detectors | `src/figma_flutter_agent/parser/semantics/detectors/inputs.py` |
| Type-trust laundering shim | `src/figma_flutter_agent/parser/semantics/signals/type_trust.py:19-39` |
| Emit fork (native vs legacy) | `src/figma_flutter_agent/generator/ir/expression.py:47,81,98` |
| `report_only` default True | `src/figma_flutter_agent/config/models.py:97` |
| Fidelity routing (`native_verified` only) | `src/figma_flutter_agent/generator/ir/fidelity/router.py:31-81` |
| Native input template (bare) | `src/figma_flutter_agent/generator/templates/widgets/input_text_field.dart.j2` |
| Styled-primitive input (no real field) | `src/figma_flutter_agent/generator/ir/fidelity/styled_emit.py:75-84,116` |
| Legacy input emit + `vertical_center` | `src/figma_flutter_agent/generator/layout/widgets/input/fields.py:54,217` |
| **Five competing content-padding builders** | `src/figma_flutter_agent/generator/layout/widgets/input/decoration.py:57,84,117,150,167` |
| Legacy structural dispatch | `src/figma_flutter_agent/generator/layout/widgets/emit/dispatch.py:39` |
| Name/text production heuristics | `src/figma_flutter_agent/parser/interaction/forms.py:305,390,400` ; `input_fields.py:42,99` |
| Button wrap (no native button) | `src/figma_flutter_agent/generator/layout/widgets/button/core.py:209` |
| Prompt: verdicts report-only | `src/figma_flutter_agent/llm/prompts/environment.py:19-23` |

## Appendix B — Open questions

1. **Contract home in IR.** Stage 1 puts contracts on `ScreenIr.element_contracts` (top-level,
   report-only, option **A**). When gated (Stage 3+), should the trusted contract be lowered
   into a richer `InputTextFieldPayload` on the node (option **C**), or kept top-level and
   joined by `control_node_id` at emit (option **B**)? Recommendation: **A → C** — recover
   top-level, lower the *gated* contract into the node payload so emit reads one typed object.
   To confirm with the implementer once Stage 1 data shape is real.
2. **Boundary vs surface.** The "control boundary" node and the "painted surface" node can
   differ (`interaction_surface_node` already distinguishes them). Should the contract carry
   both `control_node_id` and `surface_node_id`? Likely yes for chrome ownership.
3. **`min_height` policy for inputs.** Material default tap target is 48; some designs use
   40px fields. Does LAW-TI-1.2 pin `H` exactly (fidelity) or enforce `max(H, 48)`
   (accessibility)? This interacts with the known short-input `BoxConstraints` crash
   (ROB-01). Recommendation: pin `H` for centering, clamp tap target separately.
4. **Verdict ↔ classifier disagreement.** When the LLM verdict and the deterministic
   classifier disagree on the boundary or ownership, which wins for *report* (vs the gate,
   where agreement is required for high-risk effects)? Propose: report both; classifier is the
   default boundary, verdict supplies ownership hints.
5. **Cupertino parity.** The native template branches on `theme_variant == 'cupertino'`
   (`CupertinoTextField`). `CupertinoTextField` centers differently; does LAW-TI-1 need a
   Cupertino-specific realization (`padding` vs `contentPadding`)? Out of scope here; flag for
   Stage 4.
