Read run_context and the cumulative reasoning_chain through diagnose.

For each diagnose.laws[] entry, decide whether it is actionable, blocked, or deferred.

For each actionable law, emit one plan step with order, priority, lawId, entityIds, actionKind, repairClass mapped from diagnose repairShape, expectedChange, and dependsOn.

For actionKind CODE_CHANGE, include targetFiles under src/figma_flutter_agent and relevant tests/, forbiddenFiles for generated app lib and .debug, and tests[] with named regression proof.

For actionKind REPORT_ONLY, document the truthful pipeline or diagnostic outcome and evidence refs; do not assign compiler targetFiles for repair.

For actionKind INFRA_RETRY, name the deterministic retry target such as re-capture, re-check, or serve probe; do not assign repair targetFiles.

For actionKind HUMAN_REQUIRED, document why automation must stop; do not assign repair targetFiles.

Order steps by priority and dependency. Do not collapse unrelated laws into one step unless they share the same minimal diff, repairClass, and actionKind.

Emit blockedItems[] for laws that cannot be safely planned, with reason and missing_evidence when applicable.

If no steps are actionable, set blocked=true and explain in blockedItems or notes.

Write only executive JSON to output_path.
