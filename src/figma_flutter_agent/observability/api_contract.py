"""Classify internal caller/callee API drift failures."""

from __future__ import annotations

import re
from typing import Any

_UNEXPECTED_KWARG_RE = re.compile(
    r"(?P<callee>[\w.]+)\(\) got an unexpected keyword argument '(?P<kwarg>[\w_]+)'"
)


def api_contract_drift_from_type_error(exc: TypeError) -> dict[str, Any] | None:
    """Return structured drift metadata when ``exc`` is an unexpected-kwarg ``TypeError``.

    Args:
        exc: Exception raised from an internal helper call.

    Returns:
        Mapping with ``kind``, ``callee``, and ``unexpected_kwarg`` when recognized.
    """
    message = str(exc)
    if "unexpected keyword argument" not in message:
        return None
    match = _UNEXPECTED_KWARG_RE.search(message)
    if match is None:
        return {"kind": "api_contract_drift", "detail": message}
    return {
        "kind": "api_contract_drift",
        "callee": match.group("callee"),
        "unexpected_kwarg": match.group("kwarg"),
        "detail": message,
    }
