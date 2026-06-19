Use the fixed visual pass order: reference first, capture second, comparison third, heatmap last.

Pass A — inspect FIGMA_REFERENCE only. Pass B — FLUTTER_CAPTURE only. Pass C — REF|CAPTURE comparison. Pass D — DIFF_HEATMAP only for localization and severity.

Treat the watermarked Figma reference as expected product truth and the verified Flutter capture as actual rendered truth.

Never treat a heatmap or red overlay as a readable UI screenshot. Do not read UI text, hierarchy, or element identity from the heatmap.

Never diagnose from a ghost overlay of two images mixed into one unreadable frame. If only a combined overlay is available without separate ref and capture, set blocked=true.

Do not name repo files, compiler layers, law ids, figmaIds, repair shapes, or emitter paths.

Do not compute changedRatio or pixel percentages from the images. Use orchestrator-supplied diff statistics only.

If capture is not verified per run_context and vision_bundle.capture_kind, set blocked=true. Do not report screen layout symptoms from stale or unverified UI.

Use semantic_hints only to cross-check inventory counts and control kinds, not as root cause.

Keep detailed per-element inventory in the detail log when requested. Executive JSON carries symptoms only, not a full element table.

Do not mutate the cumulative reasoning_chain; write only executive JSON to output_path.
