# E2a Evidence Alongside Legacy

## Goal
Introduce the first live E2a pattern by producing `SemanticEvidence(candidate)` next to an existing text-derived password heuristic while keeping legacy production behavior unchanged. This gives E2b a concrete pattern for the future no-new text/name production-effect lint without introducing a real gated emit consumer.

## Scope
Included:
- Add evidence production at the smallest safe password-hint callsite.
- Preserve existing `input_hint_implies_obscure_text` behavior.
- Add tests proving evidence is available and remains candidate-only.
- Add a minimal local policy/test helper only for contract tests.
- Prove candidate evidence does not create a new production effect.

Excluded:
- Removing or migrating legacy production behavior.
- Enabling a blocking lint.
- Adding a production `gated_emit` consumer.
- Integrating fidelity-router, corpus governance, or E5 budgets.
- Touching `DeviationRecord` or Branch C/F2 scope.

## Technical Plan
1. Extend the F1 evidence model area with a minimal explicit-gate contract that can be used by tests without routing production emit.
2. Add a sibling evidence-producing helper for password hint text that returns `SemanticEvidence(candidate)` for text-derived password copy and no evidence for link copy such as "Forgot Password".
3. Keep the existing legacy bool helper and downstream emit behavior unchanged.
4. Add focused tests for evidence creation, candidate-only behavior, explicit-gate requirements, and unchanged output.
5. Run targeted tests around evidence models, form controls, interaction rendering, and variant password behavior.

## Checklist
1. [x] Add minimal test-only/local policy contract for explicit gated effects.
2. [x] Add password-hint `SemanticEvidence(candidate)` production alongside the legacy helper.
3. [x] Add tests for text hint evidence and no evidence for link-style password copy.
4. [x] Add tests proving candidate evidence has no production effect and gated output requires explicit policy.
5. [x] Run targeted pytest and ruff checks for the touched F1/E2a files.

## Acceptance Criteria
- Text-derived password hints produce `SemanticEvidence` with `source=text_hint` and `allowedEffect=candidate`.
- Link-style text such as "Forgot Password ?" does not produce password behavior evidence.
- Existing `input_hint_implies_obscure_text` return values and generated `obscureText` output remain unchanged.
- Candidate evidence alone cannot authorize production output in the local policy contract.
- No blocking lint is enabled and no real production `gated_emit` consumer is introduced.
