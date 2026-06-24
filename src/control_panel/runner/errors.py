"""User-facing pipeline failure messages for control-panel jobs."""

from __future__ import annotations

from figma_flutter_agent.errors import FigmaApiError


def format_generation_failure_message(exc: BaseException) -> str:
    """Turn a pipeline exception into an actionable Discord/API error string.

    Args:
        exc: Exception raised during ``run_generation_job``.

    Returns:
        Redacted, human-readable failure text (may include API body snippet).
    """
    if isinstance(exc, FigmaApiError):
        base = str(exc)
        if exc.status_code == 404:
            return (
                "Figma API 404: file or node not found, or this token cannot access the file. "
                "For Community designs: open in Figma, duplicate to your account, and use the "
                "duplicated file URL. Verify FIGMA_ACCESS_TOKEN in the agent repo .env and "
                "restart figma-flutter-worker.\n"
                f"API: {base}"
            )
        if exc.status_code == 403:
            return (
                "Figma API 403: token rejected or lacks file access. "
                "Regenerate FIGMA_ACCESS_TOKEN and restart the worker.\n"
                f"API: {base}"
            )
        return base
    return str(exc)


def enrich_failure_message(text: str) -> str:
    """Upgrade raw Figma HTTP bodies stored on older worker runs.

    Args:
        text: Failure message from the job row or worker callback.

    Returns:
        Actionable message when a known Figma API status is embedded in JSON text.
    """
    stripped = text.strip()
    if not stripped or "Figma API 404:" in stripped or "Figma API 403:" in stripped:
        return stripped
    if '"status":404' in stripped or '"status": 404' in stripped:
        return format_generation_failure_message(FigmaApiError(stripped, status_code=404))
    if '"status":403' in stripped or '"status": 403' in stripped:
        return format_generation_failure_message(FigmaApiError(stripped, status_code=403))
    return stripped
