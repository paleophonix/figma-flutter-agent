Confirm case_mode=SCREEN and vision_bundle.capture_kind=verified from run_context. If not verified, set blocked=true and stop without screen symptoms.

Pass A — inspect the FIGMA_REFERENCE artifact only. Record expected UI inventory and visual hierarchy: status bar, brand or logo, screen title, helper text, input fields, password visibility controls, primary CTA, dividers, social login buttons, footer signup, and system chrome as applicable.

Pass B — inspect the FLUTTER_CAPTURE artifact only. Record the same inventory on the actual render and note obvious user-visible defects: missing elements, overlap, duplication, clipping, unreadable text, wrong affordances.

Pass C — inspect the REF|CAPTURE comparison strip. Identify differences in presence, vertical and horizontal alignment, spacing, size, weight, hierarchy, overlap, and interaction affordance. Prefer global vs regional wording when the whole form block shifts together.

Pass D — inspect the DIFF_HEATMAP artifact only. Classify mismatch as global, regional, or local. Use it to support severity, not to invent element-level root cause. Do not read labels from the heatmap.

Cross-check inventory with semantic_hints when provided. Mismatch between hints and vision may increase severity but is not a law diagnosis.

Emit symptoms[] only. Each symptom needs a stable id, severity P0|P1|P2, userVisible prose for product, regions[] using generic names such as header, form, primary_cta, footer, userVisible must not cite compiler modules.

Attach visualEvidence[] with vision bundle filenames used for that symptom. Set confidence high, medium, or low.

Do not emit laws, repo paths, root causes, figmaIds, or repair plans.

Write only executive JSON to output_path.
