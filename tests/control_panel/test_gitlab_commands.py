"""Tests for GitLab issue note commands."""

from __future__ import annotations

from control_panel.gitlab_workflow.commands import IssueNoteCommand, parse_issue_note


def test_parse_bug_command_at_line_start() -> None:
    parsed = parse_issue_note("/bug spacing is wrong on the header")
    assert parsed is not None
    assert parsed.command == IssueNoteCommand.BUG
    assert parsed.body == "spacing is wrong on the header"


def test_parse_regen_command() -> None:
    parsed = parse_issue_note("/regen")
    assert parsed is not None
    assert parsed.command == IssueNoteCommand.REGEN


def test_parse_legacy_fix_alias_maps_to_regen() -> None:
    parsed = parse_issue_note("/fix")
    assert parsed is not None
    assert parsed.command == IssueNoteCommand.REGEN


def test_parse_ignores_non_command() -> None:
    assert parse_issue_note("please /bug later") is None
    assert parse_issue_note("looks good") is None


def test_parse_legacy_repair_alias() -> None:
    parsed = parse_issue_note("/repair compiler regression")
    assert parsed is not None
    assert parsed.command == IssueNoteCommand.REPAIR
