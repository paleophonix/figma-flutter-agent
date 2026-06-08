"""Figma API batching and retry limits."""

from __future__ import annotations

MAX_RETRIES = 3
BATCH_SIZE = 20
DEFAULT_MAX_CONCURRENT_DOWNLOADS = 8
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
# Figma may return multi-hour Retry-After values when the rate bucket is empty.
# Automatic CLI retries should fail fast instead of blocking for days.
MAX_AUTO_RETRY_DELAY_SEC = 120.0
UNIX_TIMESTAMP_THRESHOLD = 1_000_000_000.0
