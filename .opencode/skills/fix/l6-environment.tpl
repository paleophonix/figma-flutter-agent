Worktree: {worktree}
Project: {project}
Feature: {feature}
Case mode: {case_mode}
Agent board: {agent_board}
Phase: post_check_fix
OpenCode mode: build

Schema: {schema_path}
Output path: {output_path}
Detail log path: {detail_log_path}

Canonical edit root: .repair/candidate/planned_files/

Check summary:
{check_summary_json}

Analyze errors:
{analyze_errors_json}

Allowed edit files:
{allowed_edit_files_json}

Frozen context:
{frozen_context_json}

Attempt: {fix_attempt}
Max attempts: {max_fix_attempts}

Cumulative reasoning chain:
{reasoning_chain_json}

Use board master L1 from orchestrator assembly. Do not read full debug bundle or vision artifacts unless explicitly listed in allowedEditFiles or analyze_errors file paths.
