# Unmigrated emit routes (PolicyDecision P0-3)

Main semantic IR route (`generator/ir/expression.py`) uses `resolve_policy_decision`.

These routes still apply legacy interaction predicates directly:

- `generator/layout/widgets/emit/dispatch.py`
- `generator/layout/widgets/emit/flex.py`
- `generator/layout/widgets/emit/stack.py`
- `generator/layout/widgets/emit/controls.py`
- `generator/layout/widgets/option_chip.py`
- `generator/layout/choice_chip_row.py`
- `generator/ir/semantic_emit.py`

See also `UNMIGRATED_EMIT_ROUTES` in `generator/ir/policy.py`.
