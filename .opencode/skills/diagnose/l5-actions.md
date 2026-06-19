Read run_context and confirm case_mode SCREEN or FORENSIC and agent_board from the orchestrator.

Read the cumulative reasoning_chain: recognise.symptoms and inspect.entities. If inspect.blocked is true, set blocked=true unless you can diagnose only from fully anchored entities.

For each inspect entity, follow relatesToSymptoms back to recognise symptoms, then read repoPaths and artifactRefs only as needed to confirm or reject a root cause inside that surface.

Merge entities that share the same law and layer when evidence points to one mechanism. Do not emit one law per entity by default.

Group findings by law and owning layer, not by screen region or visual quadrant.

Emit laws[] with id, priority, layer, entityIds, evidence[], repairShape, forbidden[], proposedLaw when the registry law is insufficient, and optional relatesToSymptoms for traceability.

If the entity map or evidence is insufficient, set blocked=true and list missing_evidence. Request inspect.refine when WHERE anchors are missing, not recognise.refine for compiler mechanism gaps.

Write only executive JSON to output_path. Do not produce a prose triage report or BATCH PRE-FIX TRIAGE REPORT.
