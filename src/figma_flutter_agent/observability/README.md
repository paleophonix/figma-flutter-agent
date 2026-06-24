# observability

## Purpose

Structured telemetry for pipeline runs: stage timing, LLM trace correlation, PostHog `$ai_generation` capture, and optional Grafana Loki log shipping.

## Usage Example

```python
from figma_flutter_agent.config import load_settings
from figma_flutter_agent.logging_setup import configure_logging
from figma_flutter_agent.observability import log_stage, new_run_id
from figma_flutter_agent.observability.llm_trace import bind_pipeline_observability

settings = load_settings()
configure_logging(verbose=False, settings=settings)

run_id = new_run_id()
bind_pipeline_observability(run_id=run_id, settings=settings)
```

Set `LOKI_URL` (and `LOKI_USER` + `LOKI_API_KEY` for Grafana Cloud) in `.env` to ship JSON log lines to Loki. Set `LOKI_ENABLED=false` to keep credentials but skip remote shipping. Verify with `figma-flutter doctor`.

Prometheus ops metrics: `control_panel` `/metrics` (Bearer `CONTROL_PANEL_METRICS_TOKEN`) and ARQ worker `:9090/metrics`. See [docs/projects/observability/prometheus.md](../../../docs/projects/observability/prometheus.md).

Business/product events (control panel): `team-requested-generation`, `team-opened-issue`, `agent-committed-change`, `dev-committed-change`, `dev-submitted-feedback` via `posthog_business.capture_business_event` when `POSTHOG_API_KEY` is set. LLM detail stays in `$ai_generation`.

## LLM Context

Include `run_id`, `stage`, and `duration_ms` from bound Loguru context when summarizing failures. Loki lines are JSON with `level`, `logger`, `message`, and `extra` (for example `run_id`, `stage`, `file_key`). PostHog spans use the same `run_id` as `$ai_trace_id`.
