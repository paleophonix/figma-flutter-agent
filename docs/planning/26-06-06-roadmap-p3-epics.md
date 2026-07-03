# P3 roadmap epics (research backlog)

Quarter+ initiatives. Not implemented in the P1–P2 research refactor; spec references only.

## 9. `figma-flutter watch` + Figma webhooks

- Lightweight HTTP listener for `FILE_VERSION_UPDATE`, `LIBRARY_PUBLISH`.
- HMAC verification, debounced subprocess `generate`.
- Output: PR / patch artifact — **no** silent git push.
- Pydantic models from Figma webhooks OpenAPI (v0.36+).

## 10. Logic IR (`parser/figma_logic.py`)

- Parse `reactions[]`: `SET_VARIABLE`, `SET_VARIABLE_MODE`, `CONDITIONAL`.
- Separate graph from layout IR (`ir_tree` / screen IR).
- Emit stubs into figma-id `custom-code` zones + Riverpod/BLoC per `state_management.type`.
- **Not** mixed with `ir_validate` layout guards.

## 11. Raster / effects tier

- Universal heuristics in `ambient_background.py` + assets stage.
- PNG/SVG export + `RepaintBoundary` when declarative blur/complex gradients fail.
- Optional T2 config flag; ties to spec §25 fidelity tiers.
