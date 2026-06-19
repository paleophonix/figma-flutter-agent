Read run_context, agent_board, review_rubric, loop_budget, symptom_law_matrix, and the full reasoning_chain through capture.

Verify check passed and capture verdict. For SCREEN, capture must be verified unless explicitly skipped in run_context.

Build lawCompliance for every law targeted by plan.steps with status closed, partial, or not_addressed and evidence refs.

Build symptomClosure for each recognise P0 and P1 symptom in symptomLawMatrix with status addressed or open.

Check change_proof_ok, fix_proven consistency, repair scope against plan, and forbidden shortcut patterns.

Decide exactly one: CONTINUE, LOOP, or STOP.

If CONTINUE, set reason_code REVIEW_OK or RESIDUAL_NON_BLOCKING only inside regression_risks not as LOOP. List non-blocking residuals with blocking false.

If LOOP, choose one reason_code from the review enum and one route such as diagnose.refine, plan.revise, repair.retry, fix, or inspect.refine.

If STOP, use LOOP_BUDGET_EXHAUSTED, PROPOSED_LAW_NEEDS_HUMAN, EVIDENCE_CONFLICT, or INFRA_BLOCKED as appropriate.

Set task_completed_recommendation true only when decision is CONTINUE and all CONTINUE requirements are met.

Write only executive JSON to output_path. Do not write prose approval.
