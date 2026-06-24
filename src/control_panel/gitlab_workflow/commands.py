"""Parse GitLab issue note commands."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class IssueNoteCommand(StrEnum):
    """Supported slash commands in issue notes."""

    BUG = "bug"
    REGEN = "regen"
    REPAIR = "repair"


_NOTE_COMMAND_ALIASES = {
    "fix": IssueNoteCommand.REGEN.value,
}


@dataclass(frozen=True)
class ParsedIssueNote:
    """Parsed issue note command."""

    command: IssueNoteCommand
    body: str


def parse_issue_note(note: str) -> ParsedIssueNote | None:
    """Parse a note that starts with ``/bug``, ``/regen``, or legacy ``/fix`` / ``/repair``.

    Args:
        note: Raw GitLab note body.

    Returns:
        Parsed command or ``None`` when the note is not a command.
    """
    stripped = (note or "").strip()
    if not stripped.startswith("/"):
        return None
    first_line = stripped.splitlines()[0].strip()
    if not first_line.startswith("/"):
        return None
    parts = first_line.split(maxsplit=1)
    token = parts[0].lstrip("/").lower()
    token = _NOTE_COMMAND_ALIASES.get(token, token)
    if token not in {item.value for item in IssueNoteCommand}:
        return None
    remainder = ""
    if len(parts) > 1:
        remainder = parts[1].strip()
    elif "\n" in stripped:
        remainder = "\n".join(stripped.splitlines()[1:]).strip()
    return ParsedIssueNote(command=IssueNoteCommand(token), body=remainder)
