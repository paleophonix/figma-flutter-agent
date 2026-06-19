Worktree: {worktree}
Project: {project}
Feature: {feature}
Case mode: {case_mode}
Agent board: {agent_board}
Step: review (6/7)

Schema: {schema_path}
Output path: {output_path}
Detail log path: {detail_log_path}

Run context:
{run_context_json}

Cumulative reasoning chain:
{reasoning_chain_json}

Review rubric:
{review_rubric_json}

Capture verdict (orchestrator summary; do not re-analyze images):
{capture_verdict_json}

Symptom-law matrix:
{symptom_law_matrix_json}

Check gate summary:
{check_summary_json}

Run manifest summary (change_proof, runIds):
{run_manifest_summary_json}

Review gate snapshot (loop budget, hard gate coercion hints):
{review_gate_snapshot_json}

Scope diff summary (repair vs plan):
{scope_diff_summary_json}

Repo navigation map (touched files; navigation not evidence):
{repo_map_compact_json}

Do not use figma.png or heatmap as primary judgment input. Judge closure from gates, laws, and symptom matrix.
