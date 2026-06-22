Worktree: {worktree}
Project: {project}
Feature: {feature}
Case mode: {case_mode}
Agent board: {agent_board}
Step: plan (4/7)

Debug root: {debug_root}
Manifest: {manifest_path}
Schema: {schema_path}
Output path: {output_path}
Detail log path: {detail_log_path}

Run context:
{run_context_json}

Cumulative reasoning chain (read-only; do not rewrite):
{reasoning_chain_json}

Repo navigation map (deep module slice for diagnose target paths; navigation not evidence):
{repo_map_deep_json}

Existing compiler paths (plan targetFiles must exist; sample only):
{compiler_path_catalog_json}

Plan only compiler sources under the worktree and tests named in the plan. Do not plan customer app lib or generated Dart as edit targets.
