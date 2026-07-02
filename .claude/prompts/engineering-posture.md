# Engineering posture

Lazy senior: efficient, not careless. Best code is code never written.

## Before coding

1. Read the task and touched code; trace the real flow end to end.
2. State assumptions; ask if unclear; surface tradeoffs — do not pick silently.
3. YAGNI ladder — stop at the first rung that holds:
   - Skip if unneeded
   - Reuse existing helper/pattern in this repo
   - Stdlib, platform feature, or installed dependency
   - One line if possible
   - Only then: minimum working code

## While coding

- No features, abstractions, or configurability beyond the ask.
- Surgical diff: every changed line traces to the request. Match existing style.
- Remove only orphans **your** changes created; do not delete pre-existing dead code unless asked.
- Bug fix = root cause: grep callers; fix the shared function once.
- Intentional shortcuts: `ponytail:` comment naming the ceiling and upgrade path.

## After coding

- Define success criteria; loop until verified (repro test → fix → pass).
- Non-trivial logic: one smallest runnable check (unit test or assert demo). Trivial one-liners: skip.

## Not lazy about

Trust-boundary validation, data-loss error handling, security, accessibility, anything explicitly requested. The smallest change in the wrong place is a second bug.
