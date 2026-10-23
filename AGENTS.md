# AGENTS.md — Portable Agent Governance (`ENG-2081` / DDD0)

This repository adheres to the **Transurban SEAL Golden Path (`ENG-2075`)** and **Google Garden Sensible Defaults**. All AI coding agents (Antigravity, Claude Code, Cursor, Gemini CLI) operating in this repository must enforce the following invariants:

## 1. Zero-Trust Identity & RBAC (`ENG-2080`)
- Never trust raw `X-Goog-Authenticated-User-Email` headers without cryptographically verifying `X-Goog-IAP-Jwt-Assertion` (`ES256`) against `https://www.gstatic.com/iap/verify/public_key-jwk` in `src/auth.py`.
- All Streamlit entrypoints must be decorated with `@require_group(...)` verifying Workforce Identity Pool (`locations/global/workforcePools/agentspace-entra-id-p-oidc-exnat`) group claims.

## 2. Governed BigQuery & Timezone Rules (`ENG-2083` & `a113-telemetry`)
- Always construct BigQuery clients via `@st.cache_resource` (`get_bq_client()` in `src/bq.py`).
- Every `QueryJobConfig` **must** be created via `build_governed_job_config()` enforcing `maximum_bytes_billed = 5368709120` (5 GiB circuit breaker) and FinOps labels (`app`, `env`, `cost_centre`, `user_hash`).
- All SQL queries against `tu-data-edw-pr-1.a113_roadside` **must** explicitly convert UTC timestamps to `Australia/Sydney` (`DATETIME(..., 'Australia/Sydney')`).

## 3. Observability & Continuous Evaluation (`ENG-2084`)
- Never use bare `print()` statements for operational telemetry; emit single-line structured JSON logs to `stdout` via `log_structured_event()` and `trace_span()` in `src/telemetry.py`.
- All AI Sidekick responses in `src/agent_sidekick.py` must render `st.feedback("thumbs")` wired to Cloud Logging.

## 4. Deterministic Quality Hooks (`DDD0`)
- After editing any file under `src/` or `tests/`, run `ruff check src/ tests/`, `bandit -r src/ -ll`, and `pytest` (configured in `.agents/hooks.json`).
