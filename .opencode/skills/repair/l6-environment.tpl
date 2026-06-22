Worktree: {worktree}
Project: {project}
Feature: {feature}
Case mode: {case_mode}
Agent board: {agent_board}
Step: repair (5/7)
OpenCode mode: build

Debug root: {debug_root}
Schema: {schema_path}
Output path: {output_path}
Detail log path: {detail_log_path}

State files (authoritative; read with tools before editing):
  plan: {plan_state_path}
  diagnose: {diagnose_state_path}

Assigned plan step orders: {plan_step_orders}

Orchestrator facts (compact):
{run_context_json}

Diagnose laws executive slice (plan lawIds only):
{diagnose_laws_json}

Allowed edit scope (targetFiles + tests from plan):
{allowed_edit_scope_json}

Sandbox root for edits: {worktree}/src/figma_flutter_agent

Read plan.json and diagnose.json from the state paths above. Use repo read/grep tools for source context — do not expect full chain or repo-map dumps in this prompt.

Do not edit generated app lib, .debug bundles, or golden baselines.
