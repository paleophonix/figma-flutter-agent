Use inspect.entities as your input boundary. Every law must reference entityIds from inspect.entities[].id. Do not invent repo paths that inspect did not surface unless you set blocked=true and request inspect.refine via missing_evidence.

Treat inspect entity confidence as a hint, not proof. Low-confidence entities require stronger evidence before closing a law.

Use inspect artifactRefs as starting evidence anchors. Deep-read repo modules listed in inspect.repoPaths to explain mechanism inside the module.

Repo navigation map deepModules slice in L6 is navigation aid for selected paths, not evidence. Cite actual file lines and artifacts in evidence[].

Do not repeat recognise symptoms as diagnosis. Do not repeat inspect WHERE summaries as diagnosis.

Group findings by law and owning layer, not by screen region, visual quadrant, or inspect entity kind alone.

A valid diagnosis requires a stable law id or proposedLaw=true, an owning layer, entityIds from inspect, evidence refs, repairShape, and forbidden shortcuts.

Prefer existing law vocabulary from the project corpus. If a new law is needed, set proposedLaw=true and phrase the law so it applies to comparable Figma trees, not one screen.

If inspect.blocked is true or a symptom lacks anchored entities, set blocked=true or omit laws for that symptom until inspect.refine completes.

If case_mode is FORENSIC, diagnose pipeline truth: generation, writeback, runId alignment, rollback, capture passport, gate, or toolchain failure. Do not diagnose unverified Chrome UI or visual fidelity laws as current screen truth.

If case_mode is SCREEN but capture is not verified, do not close visual fidelity laws that require a verified PNG passport.

Do not re-run recognise or inspect. On diagnose.refine, amend laws[] only; do not restart the triad unless orchestrator routes recognise.refine or inspect.refine.

If evidence is missing, set blocked=true and list missing_evidence. Do not guess from memory or screenshot alone.

Do not emit plan steps, file edit instructions, or repair queue ordering — that belongs to the plan step.

Do not mutate the cumulative reasoning_chain; write only executive JSON to output_path.
