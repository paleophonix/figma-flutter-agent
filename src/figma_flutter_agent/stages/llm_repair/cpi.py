"""CPI supervisor escalation helpers for the analyze-repair loop."""

from __future__ import annotations

from figma_flutter_agent.errors import LlmError, format_error_for_log
from figma_flutter_agent.observability.llm_trace import set_llm_stage
from figma_flutter_agent.stages.llm_repair.models import LlmRepairStageResult


async def engage_cpi_supervisor_for_syntax_failure(
    llm_client,
    request,
    result: LlmRepairStageResult,
    *,
    syntax_directive: str,
    analyze_errors: tuple[str, ...],
    failed_attempts_history: list[str],
    attempt: int,
    max_attempts: int,
    log,
) -> str:
    """Run the CPI supervisor on a critical syntax-broken failure.

    Args:
        llm_client: LLM client used to call the CPI supervisor endpoint.
        request: Repair-stage request, providing clean tree and feature name.
        result: Current repair-stage result; warnings are appended in place.
        syntax_directive: Directive describing the critical syntax failure.
        analyze_errors: Analyzer errors from the failing attempt.
        failed_attempts_history: History of prior failed repair attempts.
        attempt: Current repair attempt number (1-indexed).
        max_attempts: Maximum number of repair attempts configured.
        log: Bound logger for status messages.

    Returns:
        The CPI supervisor directive to feed into the next repair prompt, or the
        original `syntax_directive` if the supervisor call fails.
    """
    try:
        set_llm_stage("repair_cpi_supervisor")
        cpi_response = await llm_client.cpi_supervisor_async(
            request.clean_tree,
            feature_name=request.resolved_feature,
            analyze_errors=[syntax_directive, *list(analyze_errors)],
            failed_attempts_history=failed_attempts_history,
        )
        directive = (
            f"{syntax_directive}\n\n{cpi_response.pattern_interrupt_directive.strip()}"
        )
        log.warning(
            "dart format parse failure; CPI supervisor engaged with "
            "{} (attempt {}/{})",
            "CRITICAL_SYNTAX_BROKEN_TAG",
            attempt,
            max_attempts,
        )
        preview = cpi_response.analysis.strip().replace("\n", " ")
        if len(preview) > 160:
            preview = f"{preview[:157]}..."
        result.warnings.append(f"CPI supervisor (CRITICAL_SYNTAX_BROKEN): {preview}")
        return directive
    except LlmError as exc:
        log.warning(
            "CPI supervisor failed on dart format failure (attempt {}): {}",
            attempt,
            format_error_for_log(exc),
        )
        result.warnings.append(f"CPI supervisor failed: {exc}")
        return syntax_directive


async def engage_cpi_supervisor_for_stagnation(
    llm_client,
    request,
    result: LlmRepairStageResult,
    *,
    analyze_errors: tuple[str, ...],
    failed_attempts_history: list[str],
    attempt: int,
    max_attempts: int,
    log,
) -> str | None:
    """Run the CPI supervisor when repair attempts stagnate on identical errors.

    Args:
        llm_client: LLM client used to call the CPI supervisor endpoint.
        request: Repair-stage request, providing clean tree and feature name.
        result: Current repair-stage result; warnings are appended in place.
        analyze_errors: Analyzer errors from the failing attempt.
        failed_attempts_history: History of prior failed repair attempts.
        attempt: Current repair attempt number (1-indexed).
        max_attempts: Maximum number of repair attempts configured.
        log: Bound logger for status messages.

    Returns:
        The pattern-interrupt directive from the CPI supervisor, or `None` if the
        supervisor call fails.
    """
    try:
        set_llm_stage("repair_cpi_supervisor")
        cpi_response = await llm_client.cpi_supervisor_async(
            request.clean_tree,
            feature_name=request.resolved_feature,
            analyze_errors=list(analyze_errors),
            failed_attempts_history=failed_attempts_history,
        )
        directive = cpi_response.pattern_interrupt_directive.strip()
        log.warning(
            "Analyze repair stagnated; CPI supervisor issued pattern interrupt "
            "(attempt {}/{})",
            attempt,
            max_attempts,
        )
        preview = cpi_response.analysis.strip().replace("\n", " ")
        if len(preview) > 160:
            preview = f"{preview[:157]}..."
        result.warnings.append(f"CPI supervisor: {preview}")
        return directive
    except LlmError as exc:
        log.warning(
            "CPI supervisor failed on stagnation (attempt {}): {}",
            attempt,
            format_error_for_log(exc),
        )
        result.warnings.append(f"CPI supervisor failed: {exc}")
        return None
