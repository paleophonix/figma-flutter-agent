Read run_context and the cumulative reasoning_chain through diagnose.

For each diagnose.laws[] entry, decide whether it is actionable, blocked, or deferred.

For each actionable law, emit one plan step with order, priority, lawId, entityIds, repairClass, targetFiles under src/figma_flutter_agent and relevant tests/, forbiddenFiles for generated app lib and .debug, tests with named regression proof, expectedChange, and dependsOn.

Order steps by priority and dependency. Do not collapse unrelated laws into one step unless they share the same minimal diff and repairClass.

Emit blockedItems[] for laws that cannot be safely planned, with reason and missing_evidence when applicable.

If no steps are actionable, set blocked=true and explain in blockedItems or notes.

Write only executive JSON to output_path.
