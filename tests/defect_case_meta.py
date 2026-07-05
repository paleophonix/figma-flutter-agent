"""Shared CaseMeta timestamps for defect corpus tests."""

from __future__ import annotations

from datetime import date, datetime, timezone


def case_timestamps(
    observed: date,
    *,
    created_hour: int = 12,
    updated_hour: int | None = None,
) -> tuple[datetime, datetime]:
    """Build UTC minute-precision ``created_at`` / ``updated_at`` pair."""
    created = datetime(
        observed.year,
        observed.month,
        observed.day,
        created_hour,
        0,
        tzinfo=timezone.utc,
    )
    updated = datetime(
        observed.year,
        observed.month,
        observed.day,
        updated_hour if updated_hour is not None else created_hour,
        0,
        tzinfo=timezone.utc,
    )
    return created, updated
