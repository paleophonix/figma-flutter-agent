"""Centralized secret redaction for logs and error messages."""

from __future__ import annotations

import re

# figd_* Figma PATs, OpenAI/Anthropic/OpenRouter keys, Google API keys, Bearer tokens.
_SECRET_PATTERN = re.compile(
    r"(figd_[A-Za-z0-9_-]+"
    r"|sk-ant-[A-Za-z0-9_-]+"
    r"|sk-or-v1-[A-Za-z0-9_-]+"
    r"|AIza[0-9A-Za-z_-]{10,}"
    r"|Bearer\s+[A-Za-z0-9._-]+"
    r"|sk-[A-Za-z0-9_-]+)",
    re.IGNORECASE,
)


def redact_secrets(text: str) -> str:
    """Replace known secret patterns with a fixed placeholder."""
    return _SECRET_PATTERN.sub("***", text)
