# Contract-to-Emit Playbook

Status: report-only implementation playbook. This document describes registry metadata added
for future policy-gated emit work. It does not define production emit behavior.

## Purpose

The Contract-to-Emit registry is the bridge between semantic recognition and future
deterministic Flutter emission:

```text
ElementContract -> ContractEmitRecipe -> policy gate -> emitter
```

Recognition answers "what element is this?" and identifies owned parts such as labels,
hints, values, decorations, options, and state nodes. `ContractEmitRecipe` answers what the
emitter should eventually understand for that contract: native widget candidates, fallback
strategy, ownership rules, layout laws, accessibility laws, state laws, allowed effects,
forbidden effects, rollout stage, and risk level.

The current task intentionally stops at the registry and validation/reporting helpers.
Recipes are canonical metadata only. They are not applied to production emit.

## Architecture

```text
Semantic recognition / ElementContract
  - contract_kind
  - role / subtype
  - owned node ids
  - proposed layout laws
  - proposed effects
        |
        v
ContractEmitRecipe registry
  - native emit candidates
  - styled and visual fallback strategy
  - ownership, layout, accessibility, and state laws
  - allowed and forbidden effects
  - report-only rollout metadata
        |
        v
Future policy gate
  - decides whether a recipe or effect can affect output
        |
        v
Future deterministic emitter implementation
  - executes approved laws without inventing geometry or behavior
```

## Supported Contract Kinds

`list_supported_contract_kinds()` returns the public supported contract universe and excludes
fallback recipes. It includes:

- Text inputs: `text_input`, `email_input`, `phone_input`, `search_input`, `password_input`
- Multiline input: `textarea`, `multiline_text_input`
- Buttons: `button`, `primary_button`, `outlined_button`, `text_button`, `icon_button`, `fab_button`
- Chips: `choice_chip_group`, `choice_chip`, `filter_chip`, `input_chip`, `action_chip`
- Rating: `rating_input`, `star_rating`
- Selection controls: `checkbox`, `switch`, `radio`, `radio_group`, `segmented_control`
- Navigation: `nav_bar`, `app_bar`, `bottom_bar`, `tab_bar`, `drawer`, `pagination`, `stepper`
- Containers: `card`, `list_tile`, `grid`, `carousel`, `accordion`
- Media: `image`, `icon`, `avatar`, `badge`
- Feedback and overlay: `loader`, `skeleton`, `tooltip`, `dialog`, `bottom_sheet`, `snackbar`, `banner`
- Technical/decorative: `divider`, `spacer`, `decorative`, `system_chrome`

`list_registered_contract_kinds()` includes addressable fallback recipes too:
`unknown` and `unsupported`.

## Per-Family Recipes

Text input recipes prefer `TextField` / `TextFormField`, require `control_node_id`, and define
laws for vertical centering, input metrics, single-source content padding, placeholder/hint
ownership, value ownership, and external labels. Password/search/email/phone variants add
explicit gated effects and forbid deriving sensitive behavior from text alone.

Textarea and `multiline_text_input` resolve to the same recipe. The recipe prefers
`TextField` / `TextFormField`, uses `styled_textarea_shell` as styled fallback, and defines
`multiline_input_top_align` and `textarea_preserve_min_height`. It forbids vertically
centering multiline text.

Button recipes prefer Material button families such as `FilledButton`, `OutlinedButton`,
`TextButton`, `IconButton`, and `FloatingActionButton`. They map label and decoration nodes
to button labels/icons, preserve state, and forbid inventing handlers or action semantics.

Chip recipes prefer `Wrap` plus Material chip widgets. Chip groups require `option_node_ids`,
preserve option order, wrap spacing, selected state, and forbid text-only selected-state
derivation.

Rating recipes prefer a rating control or `Semantics+Row`, require rating option nodes,
derive value only from component variants or filled options, and forbid text-only rating
value inference.

Selection recipes cover checkbox, switch, radio, radio group, and segmented controls. Group
contracts require options. State laws require checked/selected state from variants or state,
not from text.

Navigation recipes cover bars, tabs, drawer, pagination, and stepper. They preserve docked
position, item order, selected state, app bar title alignment, and bottom safe areas while
forbidding invented destinations or route behavior.

Container recipes cover cards, list tiles, grids, carousels, and accordions. They preserve
container padding, item order, and header/body ownership while forbidding invented
interactivity, titles, or expanded state.

Media recipes cover image, icon, avatar, and badge. They preserve bounds, icon size, avatar
shape, and badge position while forbidding invented asset paths or icons from names alone.

Feedback and overlay recipes cover loader, skeleton, tooltip, dialog, bottom sheet, snackbar,
and banner. They preserve feedback message order and overlay/skeleton/loader geometry while
forbidding invented triggers, actions, and messages.

Technical/decorative recipes cover divider, spacer, decorative, and system chrome. They
preserve visual or spacing intent, exclude decorative semantics, and forbid turning
decorative nodes into controls.

## Rollout Stages

- `report_only`: recipe and validation metadata only; no production output changes.
- `diff_only`: future reports may compare current emit against expected law signals.
- `policy_gated`: future policy may approve specific recipe effects.
- `native_emit`: future deterministic emit may execute approved laws.

All recipes introduced by this playbook default to `report_only`.

## Validation

`validate_contract_against_recipe()` accepts an `ElementContract`-like object or dict. It can
report:

- missing required owned parts, such as `control_node_id` or `option_node_ids`
- proposed effects that are forbidden by the recipe
- unknown layout laws
- unknown effects
- unsupported contract kinds

Validation never mutates the contract and never changes generated output.

## Future Diff And Report Use

Future reporting should use the registry generically:

```text
contract
  -> get_contract_emit_recipe(contract.contract_kind, contract.subtype)
  -> recipe.layout_laws
  -> compare current Dart against expected law signals
```

Diff/report code should not hardcode only textareas, chips, or buttons. The registry is the
canonical source for the recognized element universe.

## Future Implementation Path

Future production work should apply recipes only through a policy gate:

```text
contract + recipe + evidence
  -> policy gate approves a specific effect
  -> deterministic emitter applies the approved law
```

Emitters should execute fixed laws and should not invent geometry, values, options,
interactivity, routes, asset paths, icons, or LLM-generated Dart.

## Non-Goals

This playbook does not:

- change production emit
- change generated Dart
- change parser classification
- change materialization behavior
- implement input layout laws in the emitter
- rewrite input decoration code
- flip semantic `report_only`
- change fidelity routing
- modify repair bot or `llm_repair`
- change preview, oracle, golden, or baseline flow
- add production regex/text/name heuristics
