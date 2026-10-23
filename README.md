---
title: NorthConnex (NCX) Tunnel Ventilation & Portal Emission Analytics — SEAL Golden Path App
epic: ENG-2075
owner: Asset Management — Tunnel Ventilation & Roadside Systems
cost_centre: AM-VENTILATION-113
data_sensitivity: internal-engineering
gcp_project: tu-data-edw-pr-1
bigquery_dataset: a113_roadside
workforce_pool: locations/global/workforcePools/agentspace-entra-id-p-oidc-exnat
---

# NorthConnex (NCX) Tunnel Ventilation & Portal Emission Analytics (`ENG-2075`)

Production-ready **Option 1 (Hybrid Golden Path Container)** implementation of the **NorthConnex (M11) Tunnel Ventilation & Portal Emission Root Cause Analysis Dashboard**, packaged to comply with the **Transurban SEAL Team App Hosting Guidance (`ENG-2075` / Project GravityWell / Google Garden)**.

---

## 1. Architecture Overview (Option 1: Hybrid Golden Path Container)

![SEAL Golden Path End-to-End Architecture](./docs/diagrams/seal_golden_path_architecture.png)

This repository combines:
1. **SEAL Golden Path Cloud Run + IAP + FinOps Backend (`src/auth.py`, `src/bq.py`, `src/telemetry.py`)**:
   - Cryptographic `ES256` verification of Google Cloud IAP JWT assertions (`X-Goog-IAP-Jwt-Assertion`) and Microsoft Entra ID Workforce Identity Pool RBAC (`@require_group`).
   - Governed BigQuery access (`tu-data-edw-pr-1.a113_roadside`) with a **5 GiB `maximum_bytes_billed` circuit breaker**, mandatory FinOps cost-attribution labels (`app`, `env`, `cost_centre`, `user_hash`), BigQuery Storage Read API (`to_dataframe(create_bqstorage_client=True)`), and strict `DATETIME(..., 'Australia/Sydney')` timezone conversion.
   - Single-line structured JSON logging to `stdout` (`logging.googleapis.com/trace`) and OpenTelemetry span instrumentation.
2. **60fps Interactive HTML/SVG/Chart.js + Time-Scrubber Frontend (`src/template_engine.py`)**:
   - Dynamically injects either the **Verified 4-Week Snapshot (`2026-09-22` to `2026-10-20 AEST`, including the Oct 16–17 Forced Level 3 Overnight Test)** or **Live BigQuery telemetry** into the interactive 16-zone NCX tunnel schematic and synchronized 5-row Chart.js canvas.
3. **Vertex AI Agent Engine (ADK) Sidekick & Agentspace A2A Discovery (`src/agent_sidekick.py`, `.well-known/agent.json`)**:
   - Embedded engineering RCA assistant grounded in `NCX-MEA-01-2516-CS-SP-0001_16` (`TQ158 Rule 2k` S6 vs S2 asymmetry, 0-second debounce, `ctrJFTVZ203` PID decoupling) with mandatory `st.feedback("thumbs")` evaluation logging.

### Reference Documentation (`docs/`)
- **[Epic `ENG-2075` Specification](./docs/epic.md)** — SEAL App Hosting Guidance Epic & Business Outcome.
- **[Jira Stories `ENG-2079`–`ENG-2085`](./docs/stories.md)** — Acceptance Criteria & Definition of Done across all 7 stories.
- **[Google Garden Reference Architecture](./docs/google-garden-architecture.md)** — Transurban AI Factory / Project GravityWell architecture patterns.
- **[Implementation Plan & Options Matrix](./docs/ncx_hosting_implementation_plan.md)** — Detailed Option 1 / 2 / 3 trade-off matrix and altitude mapping.
- **[Verification Walkthrough](./docs/walkthrough.md)** — Full test suite results, diagrams, and traceability verification.

---

## 2. SEAL Epic `ENG-2075` Altitude Traceability Matrix (DDD6)

| Jira Story | Capability | Repository Implementation | Verification |
| :--- | :--- | :--- | :--- |
| **`ENG-2079`** | Pulumi Cloud Run + IAP + WIF IaC | `infra/main.go`, `infra/Pulumi.yaml` (`CpuIdle: false`, `SessionAffinity: true`, `Gen2`, private VPC egress) | `pulumi preview` |
| **`ENG-2080`** | IAP JWT Validation & Entra ID RBAC | `src/auth.py` (`verify_iap_jwt`, `@require_group`, Workforce Pool claims) | `tests/test_auth.py` |
| **`ENG-2081`** | Golden Path Cookie-Cutter Template | `pyproject.toml`, `Dockerfile` (UID `10001`), `src/app.py`, `.agents/hooks.json`, `AGENTS.md` | `tests/test_app.py` |
| **`ENG-2082`** | CI/CD Pipeline & Security Gates | `.github/workflows/ci-cd.yml` (`ruff`, `bandit`, `gitleaks`, `trivy`, `pytest`, WIF deploy) | GitHub Actions |
| **`ENG-2083`** | Governed BigQuery & FinOps Guardrails | `src/bq.py` (`build_governed_job_config`, 5 GiB cap, job labels, `Australia/Sydney` SQL) | `tests/test_app.py` |
| **`ENG-2084`** | Cloud Logging & OpenTelemetry | `src/telemetry.py` (`log_structured_event`, `trace_span`) + `st.feedback("thumbs")` | `tests/test_app.py` |
| **`ENG-2085`** | Agentspace A2A Card & ADK Sidekick | `.well-known/agent.json`, `src/agent_sidekick.py` | `tests/test_app.py` |

---

## 3. Local Development & Testing (Windows PowerShell)

```powershell
# 1. Navigate to the Golden Path repository
cd "C:\Users\amuhammad\Documents\AM Agents\App Hosting\ncx-portal-emissions-app"

# 2. Run the unit & Streamlit AppTest suite
& "C:\Program Files\Python314\python.exe" -m pytest -v

# 3. Launch the app locally (with local dev auth enabled)
$env:ALLOW_LOCAL_DEV_AUTH="true"
& "C:\Program Files\Python314\python.exe" -m streamlit run src/app.py --server.port=8501
```
