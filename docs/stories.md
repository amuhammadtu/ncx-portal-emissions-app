# Child Stories for Epic ENG-2075 (Streamlit platform on BigQuery)

Parent Epic: **[ENG-2075](https://transurban.atlassian.net/browse/ENG-2075)**

---

## 1. [ENG-2076](https://transurban.atlassian.net/browse/ENG-2076) — Spike: ADRs for GCP hosting, Entra ID WIF, BigQuery access & Sensible Defaults (M / 5 pts)

### User story

As a **Platform Engineer and Data Application Architect**, I want **approved Architecture Decision Records (`ADR-001` through `ADR-004`) covering Google Cloud runtime hosting, Microsoft Entra ID Workforce Identity Federation, tiered BigQuery data access, and Pulumi state management**, so that **the Streamlit-on-BigQuery platform ([ENG-2075](https://transurban.atlassian.net/browse/ENG-2075)) has an agreed, security-endorsed technical foundation aligned with Transurban's Sensible Defaults before building shared infrastructure**.

### Context

Snowflake is being retired in favour of **Google BigQuery** (Project Nova / `BQM`). To replace Streamlit in Snowflake (SiS) with a 100% Google Cloud runtime and agentic paved road under Epic [ENG-2075](https://transurban.atlassian.net/browse/ENG-2075), several foundational architecture decisions must be validated and recorded as Docs-as-Code (`docs/adr/`) per [DDD6 — Documentation Philosophy](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42375610524/DDD6+-+Documentation+Philosophy) and [SEAL Development Design Decisions](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40093876406/Development+Design+Decisions):

- **Reference Documents:**
  - Parent Epic: [ENG-2075 — Streamlit platform on BigQuery (replace Streamlit in Snowflake)](https://transurban.atlassian.net/browse/ENG-2075)
  - Sensible Defaults Index: [SEAL Development Design Decisions](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40093876406/Development+Design+Decisions)
  - Documentation Standard: [DDD6 — Documentation Philosophy](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42375610524/DDD6+-+Documentation+Philosophy)
  - Outer Loop & Golden Paths: [PE-WS4 Blueprints & Golden Path Templates](https://transurban.atlassian.net/wiki/spaces/CTS/pages/42531488146/PE-WS4+Blueprints+Golden+Path+Templates)
  - Remote Workspace Boundary: [DDD7 — Remote Development Workspace](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42566713776/DDD7+-+Remote+Development+Workspace)

### Scope & deliverables

Author `docs/adr/ADR-001` through `ADR-004` in GitHub ([DDD1 — GitHub](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40090632665/DDD1+-+GitHub)) and auto-project to Confluence ([DDD6](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42375610524/DDD6+-+Documentation+Philosophy)):

- **`ADR-001` — Hosting Target (100% Google Cloud `Cloud Run v2`):**
  - Lock in **Google Cloud Run v2** in `australia-southeast1` co-located with BigQuery datasets (zero cross-cloud egress fees, sub-10ms **BigQuery Storage Read API** Apache Arrow streaming, native **BigQuery BI Engine** caching, and native **Google Agentspace** catalog integration).
- **`ADR-002` — User Sign-In (Cloud Run Direct IAP + Entra ID Workforce Identity Federation):**
  - Validate **Cloud Run Direct IAP** (`launchStage: BETA` / GA) integrated with **Workforce Identity Federation (WIF)** mapped to **Microsoft Entra ID** (`locations/global/workforcePools/agentspace-entra-id-p-oidc-exnat/...`).
  - Prove WebSocket session affinity (`/_stcore/stream`) behind Direct IAP in the target GCP project; document fallback to Global External Application Load Balancer + Serverless NEG + IAP if required by landing-zone org policy.
- **`ADR-003` — Two-Tier BigQuery & Agentic Data Access Model:**
  - *Tier 1 (Default — Owner's Rights, matching SiS default):* Dedicated per-app Cloud Run Service Account granted `roles/bigquery.jobUser` on the app host project, `roles/bigquery.readSessionUser` (Storage Read API), and dataset-scoped `roles/bigquery.dataViewer`.
  - *Tier 2 (Sensitive / Regulated Data — Caller's Rights):* End-user Workforce Identity OAuth token pass-through enforcing **Dataplex Row-Level Security (RLS)**, **Column-Level Security (CLS)**, and dynamic data masking per Entra ID user, plus **Google MCP Toolbox for Databases (BigQuery)** tool definitions.
- **`ADR-004` — Pulumi State Backend & Sensible Default Toolchain Alignment:**
  - Confirm Pulumi (Go) state backend per CloudOps / [PE-WS4](https://transurban.atlassian.net/wiki/spaces/CTS/pages/42531488146/PE-WS4+Blueprints+Golden+Path+Templates) standard (GCS state bucket with Cloud KMS CMEK vs Pulumi Cloud org backend) and document alignment with `DDD0`–`DDD7`.
  - Record target `dev` and `prod` GCP project IDs and Snowflake exit milestone dates with Project Nova (`BQM`).

### Acceptance criteria

- `ADR-001` through `ADR-004` are merged to `docs/adr/` in GitHub with explicit [DDD6](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42375610524/DDD6+-+Documentation+Philosophy) metadata headers (`Owner`, `Freshness mechanism`, `Presentation targets`).
- Direct IAP + Entra ID WIF + WebSocket streaming (`/_stcore/stream`) is proven via a spike proof-of-concept in the target `dev` GCP project.
- ADRs are projected to Confluence (`SEAL` / `CTS`) and signed off by Platform Engineering (Phil Wait), CloudOps (Julien Bonastre), and Security.
- Target `dev` and `prod` GCP Project IDs and the Snowflake cutover date are confirmed and linked back to [ENG-2075](https://transurban.atlassian.net/browse/ENG-2075).

### Out of scope

- Building the production `StreamlitApp` Pulumi (Go) component (covered in Story 4).
- Migrating existing Streamlit in Snowflake (SiS) applications (covered in Stories 11 and 12).

---

## 2. [ENG-2077](https://transurban.atlassian.net/browse/ENG-2077) — Pulumi (Go) infrastructure repo bootstrap (streamlit-bigquery-platform) (S / 3 pts)

### User story

As a **Platform Engineer**, I want **to bootstrap the `transurban/streamlit-bigquery-platform` Pulumi (Go) repository with keyless GitHub Actions OIDC CI/CD and Transurban Sensible Default quality gates**, so that **all shared GCP infrastructure for the Streamlit-on-BigQuery platform ([ENG-2075](https://transurban.atlassian.net/browse/ENG-2075)) is provisioned reproducibly with zero click-ops and zero stored cloud credentials**.

### Context

Per [ENG-2075](https://transurban.atlassian.net/browse/ENG-2075) and the [SEAL Development Design Decisions](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40093876406/Development+Design+Decisions), all infrastructure must be managed as code in **GitHub Enterprise (`github.com/transurban`)** using **Pulumi (Go)** and deployed via **GitHub Actions** with keyless OIDC to Google Cloud Workload Identity Federation.

- **Reference Documents:**
  - Parent Epic: [ENG-2075 — Streamlit platform on BigQuery (replace Streamlit in Snowflake)](https://transurban.atlassian.net/browse/ENG-2075)
  - Inner Loop & Portable Agent Config: [DDD0 — Developer Inner Loop Strategy](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42567892996/DDD0+-+Developer+Inner+Loop+Strategy)
  - Source Control & Org Manager: [DDD1 — GitHub](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40090632665/DDD1+-+GitHub)
  - Go Linting Standards: [DDD2 — Linting](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40109245590/DDD2+-+Linting)
  - Static Analysis Gate: [DDD4 — SonarQube](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40476246070/DDD4+-+SonarQube)
  - Artifact & Module Proxy: [DDD5 — Artifactory](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40615706809/DDD5+-+Artifactory)
  - Golden Path CI/CD: [PE-WS4 Blueprints & Golden Path Templates](https://transurban.atlassian.net/wiki/spaces/CTS/pages/42531488146/PE-WS4+Blueprints+Golden+Path+Templates)

### Scope & deliverables

- **Repository Provisioning ([DDD1](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40090632665/DDD1+-+GitHub)):**
  - Provision `transurban/streamlit-bigquery-platform` via [`transurban/github-org-manager`](https://github.com/transurban/github-org-manager) with branch protection, required PR reviews, and `CODEOWNERS`.
  - Initialize Pulumi (Go) program with `Pulumi.dev.yaml` and `Pulumi.prod.yaml` stack configurations for target GCP project IDs and `australia-southeast1` region.
- **Portable Agent Harness ([DDD0](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42567892996/DDD0+-+Developer+Inner+Loop+Strategy)):**
  - Include root `AGENTS.md` (with `CLAUDE.md` symlink and `.github/copilot-instructions.md`) and `.agents/hooks.json` running `golangci-lint` on `postEdit`.
- **Keyless GitHub Actions Pipeline ([PE-WS4](https://transurban.atlassian.net/wiki/spaces/CTS/pages/42531488146/PE-WS4+Blueprints+Golden+Path+Templates)):**
  - Configure `google-github-actions/auth@v2` using keyless GitHub OIDC → GCP Workload Identity Federation (zero static service account JSON keys).
  - Run `pulumi preview` on pull requests (posting the diff summary as a PR comment) and `pulumi up` on merge to `main`.
- **Sensible Default Quality Gates ([DDD2](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40109245590/DDD2+-+Linting), [DDD4](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40476246070/DDD4+-+SonarQube), [DDD5](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40615706809/DDD5+-+Artifactory)):**
  - Enforce `go vet`, `golangci-lint`, Pulumi Go mock unit tests (`go test ./...`), **SonarQube SaaS (SonarCloud)** PR quality gate, and Go module resolution via **JFrog Artifactory (`transurban.jfrog.io`)**.

### Acceptance criteria

- `transurban/streamlit-bigquery-platform` is provisioned in GitHub via `transurban/github-org-manager` with branch protection enabled on `main`.
- An initial baseline Pulumi (Go) stack deploys to `dev` from GitHub Actions using 100% keyless OIDC → GCP Workload Identity Federation.
- Pull requests automatically execute `golangci-lint`, `go test`, **SonarQube SaaS** analysis, and `pulumi preview`, blocking merge on any failure.
- Zero long-lived GCP service account keys or static credentials exist in GitHub Secrets or repository code.

### Out of scope

- Provisioning shared GCP networking, Cloud Workstations, or BigQuery BI Engine resources (covered in Story 3).
- Building the `StreamlitApp` reusable Pulumi component (covered in Story 4).

---

## 3. [ENG-2078](https://transurban.atlassian.net/browse/ENG-2078) — Shared GCP platform resources, Cloud Workstations & Agentspace connectors (M / 5 pts)

### User story

As a **Data App Developer and Platform Engineer**, I want **shared GCP platform resources, ZPA-protected Google Cloud Workstations, BigQuery BI Engine acceleration, and Google Agentspace connectors provisioned in `dev` and `prod`**, so that **developers have a <15-minute zero-ticket inner loop ([DDD0](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42567892996/DDD0+-+Developer+Inner+Loop+Strategy), [DDD7](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42566713776/DDD7+-+Remote+Development+Workspace)) and apps share governed, co-located Google Cloud foundation services**.

### Context

Under Epic [ENG-2075](https://transurban.atlassian.net/browse/ENG-2075), individual Streamlit apps rely on shared regional infrastructure in `australia-southeast1` and a remote developer inner loop built on **Google Cloud Workstations** behind **Zscaler Private Access (ZPA)** ([DDD7 — Remote Development Workspace](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42566713776/DDD7+-+Remote+Development+Workspace)).

- **Reference Documents:**
  - Parent Epic: [ENG-2075 — Streamlit platform on BigQuery (replace Streamlit in Snowflake)](https://transurban.atlassian.net/browse/ENG-2075)
  - Inner Loop Strategy: [DDD0 — Developer Inner Loop Strategy](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42567892996/DDD0+-+Developer+Inner+Loop+Strategy)
  - Artifact Management: [DDD5 — Artifactory](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40615706809/DDD5+-+Artifactory)
  - Remote Dev Workspace & Ownership Split (§6.5): [DDD7 — Remote Development Workspace](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42566713776/DDD7+-+Remote+Development+Workspace)
  - Golden Container & Blueprints: [PE-WS4 Blueprints & Golden Path Templates](https://transurban.atlassian.net/wiki/spaces/CTS/pages/42531488146/PE-WS4+Blueprints+Golden+Path+Templates)
  - Antigravity Enterprise Setup: [Playbook: Moving to Antigravity on Gemini Enterprise Plus](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42650468432/Playbook+Moving+to+Antigravity+on+Gemini+Enterprise+Plus+incl.+NAT+attestation)

### Scope & deliverables

Provision via Pulumi (Go) in `transurban/streamlit-bigquery-platform`:

- **Regional GCP Artifact Registry ([DDD5](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40615706809/DDD5+-+Artifactory)):**
  - Provision regional Docker repository in `australia-southeast1` for Cloud Run co-location, receiving container images after **JFrog Xray** security scanning in CI.
- **Networking & Google Cloud Workstations Inner Loop ([DDD7](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42566713776/DDD7+-+Remote+Development+Workspace)):**
  - Configure Direct VPC egress (`private-ranges-only`) and Private Google Access for `bigquery.googleapis.com`, `bigquerystorage.googleapis.com`, `aiplatform.googleapis.com`, and `discoveryengine.googleapis.com`.
  - Provision **Google Cloud Workstations** cluster/config behind **Zscaler ZPA** using the PE-WS4 Golden Container (Ubuntu 24.04 LTS, pre-baked Zscaler Root CA, `uv`, Python 3.12+, Go, Pulumi, `agy` CLI connected to `gemini-us.transurban.com`, and [`transurban/code-skills`](https://github.com/transurban/code-skills)).
  - Coordinate VPC, firewall, and ZPA App Connector boundaries with CloudOps (Julien Bonastre) per [DDD7 §6.5](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42566713776/DDD7+-+Remote+Development+Workspace).
- **BigQuery Acceleration & Google Agentspace Shared Services:**
  - Provision **BigQuery BI Engine** RAM reservation in `australia-southeast1` for sub-second cached dashboard/app queries.
  - Deploy shared **Google MCP Toolbox for Databases (BigQuery)** Cloud Run service (internal ingress) and register **Google Agentspace** data/app connectors.
- **Platform Operations & FinOps Baseline:**
  - Provision central Cloud Logging sink, Cloud Monitoring notification channels, and GCP Billing budget alerts.

### Acceptance criteria

- Shared Pulumi stack deploys cleanly to `dev` and `prod` in `australia-southeast1`, complying with all GCP Landing Zone Organization Policies.
- A developer can connect to a **Google Cloud Workstation** over Zscaler ZPA (`ghostty -e ssh dev-box` or VS Code Remote-SSH) and run `agy`, `bq`, and `uv` using ambient GCP Application Default Credentials with zero manual certificate or key setup (< 15 minutes Time to First Commit per [DDD0](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42567892996/DDD0+-+Developer+Inner+Loop+Strategy)).
- BigQuery BI Engine reservation and the shared MCP Toolbox for BigQuery service are active and reachable from within the VPC.

### Out of scope

- Per-application Cloud Run services and per-app IAM bindings (covered in Story 4).
- Modifying Zscaler ZPA App Connector appliances outside the inner-loop container boundary (owned by CloudOps per [DDD7 §6.5](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42566713776/DDD7+-+Remote+Development+Workspace)).

---

## 4. [ENG-2079](https://transurban.atlassian.net/browse/ENG-2079) — StreamlitApp Pulumi component (Go) + Google Agentspace / A2A registration (L / 8 pts)

### User story

As a **Data App Developer**, I want **a single reusable `StreamlitApp` Pulumi (Go) `ComponentResource` that provisions Cloud Run v2, Direct IAP, least-privilege BigQuery IAM, and Google Agentspace registration from ~15 lines of Go**, so that **I can deploy a secure, SSO-protected BigQuery Streamlit app without writing raw IAM, networking, or load-balancer boilerplate**.

### Context

In Streamlit in Snowflake (SiS), publishing an app automatically handled compute, authentication, and catalog visibility. Under [ENG-2075](https://transurban.atlassian.net/browse/ENG-2075), the `StreamlitApp` Pulumi (Go) component recreates that 1-step developer experience on **Google Cloud Run v2** + **Direct IAP** + **Google Agentspace**, developed using human-human and human-agent pair programming per [DDD3 — Pair Programming](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40142308116/DDD3+-+Pair+Programming).

- **Reference Documents:**
  - Parent Epic: [ENG-2075 — Streamlit platform on BigQuery (replace Streamlit in Snowflake)](https://transurban.atlassian.net/browse/ENG-2075)
  - Pair Programming Standard: [DDD3 — Pair Programming](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40142308116/DDD3+-+Pair+Programming)
  - Linting & Quality Gates: [DDD2 — Linting](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40109245590/DDD2+-+Linting) & [DDD4 — SonarQube](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40476246070/DDD4+-+SonarQube)
  - Golden Path Blueprints: [PE-WS4 Blueprints & Golden Path Templates](https://transurban.atlassian.net/wiki/spaces/CTS/pages/42531488146/PE-WS4+Blueprints+Golden+Path+Templates)

### Scope & deliverables

Implement `pkg/platform/streamlit_app.go` in `transurban/streamlit-bigquery-platform` exposing:

```go
platform.NewStreamlitApp(ctx, "fleet-ops", &platform.StreamlitAppArgs{
    Image:             imageRef,
    AccessGroups:      []string{"group:fleet-ops-users@transurban.com"},
    BigQueryDatasets:  []string{"tu-data-prod.tolling_ops", "tu-data-prod.fleet"},
    MaxBytesBilled:    10 << 30, // 10 GiB hard cap per query
    EnableCallerOAuth: false,    // true for Tier-2 RLS/CLS sensitive datasets
    AgentspaceAppId:   "tu-enterprise-agentspace",
    EnableAdkSidekick: true,     // mounts Vertex AI Agent Engine + MCP BigQuery toolset
    CostCentre:        "CC-4102",
    OwnerTeam:         "fleet-analytics",
})
```

The component provisions:
- **Cloud Run v2 Service (`cloudrunv2.Service`):**
  - `minInstanceCount: 0` (scale-to-zero cost efficiency; configurable `1` for latency-critical prod apps), `maxInstanceCount: 10`, `sessionAffinity: true` (for Streamlit `/_stcore/stream` WebSockets), `startupCpuBoost: true`, and Direct VPC egress.
  - Hardened health/liveness probes hitting `/_stcore/health`.
- **Dedicated Least-Privilege Runtime Service Account:**
  - Per-app Service Account granted `roles/bigquery.jobUser` and `roles/bigquery.readSessionUser` (for BigQuery Storage Read API) on the app project, plus dataset-scoped `roles/bigquery.dataViewer` **only** on `BigQueryDatasets` (never project-wide `bigquery.admin` or `bigquery.dataViewer`).
  - If `EnableAdkSidekick: true`, binds `roles/aiplatform.user` to invoke the Vertex AI Agent Engine ADK runtime.
- **Zero-Trust Direct IAP & Workforce Identity Access:**
  - Enables native Direct IAP (`iapEnabled: true`) on the Cloud Run service and binds `roles/iap.httpsResourceAccessor` strictly to the Entra ID groups in `AccessGroups` (zero `allUsers` or `allAuthenticatedUsers` bindings).
- **Google Agentspace & A2A Agent Card Registration:**
  - Registers the application tile in **Google Agentspace** (scoped to `AccessGroups`) and exposes `/.well-known/agent.json` for Agent2Agent (A2A) discovery when `EnableAdkSidekick` is enabled.
- **Secret Manager & Mandatory FinOps Labels:**
  - Binds listed Secret Manager secrets and applies mandatory labels (`app`, `owner`, `cost_centre`, `env`, `managed_by: pulumi`).

### Acceptance criteria

- Pulumi Go mock unit tests (`streamlit_app_test.go`) assert that:
  - Every app gets a dedicated Service Account with dataset-scoped `roles/bigquery.dataViewer` only.
  - `allUsers` and `allAuthenticatedUsers` IAM bindings are strictly rejected.
  - Direct IAP (`roles/iap.httpsResourceAccessor`), `sessionAffinity: true`, and mandatory FinOps labels are always set.
- Code passes `golangci-lint` ([DDD2](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40109245590/DDD2+-+Linting)) and the **SonarQube SaaS** quality gate ([DDD4](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40476246070/DDD4+-+SonarQube)).
- A sample hello-world Streamlit app deployed with `NewStreamlitApp` is reachable by members of `AccessGroups`, returns `403` to non-members, and appears in the **Google Agentspace** catalog.

### Out of scope

- In-app Python JWT verification middleware and Tier-2 Caller's Rights OAuth token exchange inside Streamlit (covered in Story 5).

---

## 5. [ENG-2080](https://transurban.atlassian.net/browse/ENG-2080) — SSO, cryptographic IAP JWT verification & Caller's Rights OAuth in apps (M / 5 pts)

### User story

As a **Security Engineer and Data App Author**, I want **every Streamlit app to cryptographically verify Google IAP JWT assertions (`X-Goog-IAP-Jwt-Assertion`) and support optional Caller's Rights OAuth token pass-through to BigQuery**, so that **user identity cannot be spoofed if ingress is ever misconfigured and sensitive datasets enforce per-user Dataplex Row/Column-Level Security**.

### Context

In Streamlit in Snowflake (SiS), `st.experimental_user` provided the signed-in user's identity. On **Google Cloud Run + Direct IAP** ([ENG-2075](https://transurban.atlassian.net/browse/ENG-2075)), Google edge proxies authenticate the user against **Microsoft Entra ID** via **Workforce Identity Federation** and inject both plain headers (`X-Goog-Authenticated-User-Email`) and a cryptographically signed ES256 JWT (`X-Goog-IAP-Jwt-Assertion`). Per Google Cloud zero-trust best practice, applications must verify the signed JWT rather than trusting raw headers.

- **Reference Documents:**
  - Parent Epic: [ENG-2075 — Streamlit platform on BigQuery (replace Streamlit in Snowflake)](https://transurban.atlassian.net/browse/ENG-2075)
  - Linting & Security Scanning: [DDD2 — Linting](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40109245590/DDD2+-+Linting) & [DDD4 — SonarQube](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40476246070/DDD4+-+SonarQube)

### Scope & deliverables

- **Entra ID Workforce Identity Pool Integration:**
  - Configure Cloud Run Direct IAP to authenticate against Transurban's Entra ID Workforce Identity Pool (`locations/global/workforcePools/agentspace-entra-id-p-oidc-exnat/providers/...`).
- **Cryptographic IAP JWT Verification (`src/auth.py`):**
  - Implement `get_current_user()` in `src/auth.py` using `google.oauth2.id_token.verify_token(jwt_assertion, requests.Request(), audience=expected_audience, certs_url="https://www.gstatic.com/iap/verify/public_key-jwk")`.
  - Validate expected audience `/projects/{PROJECT_NUMBER}/global/backendServices/{SERVICE_ID}` and issuer `https://cloud.google.com/iap`.
  - Populate `st.session_state.user` (`email`, `sub`, `groups`, `user_hash`) for audit logging and query labelling.
- **Role/Group Guard Decorator:**
  - Provide `@require_group("group:...")` decorator for page-level or action-level authorization inside multipage Streamlit apps.
- **Tier-2 Caller's Rights OAuth Flow (Sensitive / Regulated Datasets):**
  - Implement opt-in Workforce Identity user OAuth credential pass-through (`EnableCallerOAuth: true`) so BigQuery queries execute under the signed-in Entra ID user's identity, enforcing **Dataplex Row-Level Security (RLS)**, **Column-Level Security (CLS)**, and dynamic data masking.

### Acceptance criteria

- Users outside `AccessGroups` receive an HTTP `403 Forbidden` at the Google IAP edge before reaching the Cloud Run container.
- Users inside `AccessGroups` see their verified Entra ID email and group claims in `st.session_state.user` with zero secondary login prompts.
- Unit tests (`pytest`) prove that a forged `X-Goog-Authenticated-User-Email` header without a valid ES256 `X-Goog-IAP-Jwt-Assertion` signature raises a `PermissionError` and blocks page execution.
- A Tier-2 test query against a Dataplex RLS-protected BigQuery view returns only the rows permitted for the signed-in Entra ID user.

### Out of scope

- Threat modelling of the end-to-end platform and formal Security penetration testing sign-off (covered in Story 10).

---

## 6. [ENG-2081](https://transurban.atlassian.net/browse/ENG-2081) — Golden Path Streamlit app template repo + transurban/code-skills plugin (M / 5 pts)

### User story

As a **Data Scientist or Analytics Engineer**, I want **a 1-click GitHub Golden Path template (`transurban/streamlit-bigquery-template`) and a reusable `transurban/code-skills` Antigravity plugin**, so that **I can reach Time to First Commit in under 15 minutes and deploy a production-grade BigQuery + Vertex AI ADK Streamlit app to `dev` in under 1 hour**.

### Context

To achieve the inner-loop velocity targets set out in [DDD0 — Developer Inner Loop Strategy](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42567892996/DDD0+-+Developer+Inner+Loop+Strategy) (Time to First Commit < 15 minutes) and [PE-WS4 Blueprints & Golden Path Templates](https://transurban.atlassian.net/wiki/spaces/CTS/pages/42531488146/PE-WS4+Blueprints+Golden+Path+Templates), Epic [ENG-2075](https://transurban.atlassian.net/browse/ENG-2075) provides both a Golden Path GitHub template repository and codified **Google Antigravity (`agy`)** skills in [`transurban/code-skills`](https://github.com/transurban/code-skills).

- **Reference Documents:**
  - Parent Epic: [ENG-2075 — Streamlit platform on BigQuery (replace Streamlit in Snowflake)](https://transurban.atlassian.net/browse/ENG-2075)
  - Inner Loop Strategy: [DDD0 — Developer Inner Loop Strategy](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42567892996/DDD0+-+Developer+Inner+Loop+Strategy)
  - GitHub & Golden Paths: [DDD1 — GitHub](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40090632665/DDD1+-+GitHub) & [PE-WS4 Blueprints & Golden Path Templates](https://transurban.atlassian.net/wiki/spaces/CTS/pages/42531488146/PE-WS4+Blueprints+Golden+Path+Templates)
  - Linting & Artifactory: [DDD2 — Linting](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40109245590/DDD2+-+Linting) & [DDD5 — Artifactory](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40615706809/DDD5+-+Artifactory)
  - Skill Catalog: [Transurban AI Coding Agents - Plugin & Skill Catalog](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42562814412/Transurban+AI+Coding+Agents+-+Plugin+Skill+Catalog)
  - Antigravity Playbook: [Playbook: Moving to Antigravity on Gemini Enterprise Plus](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42650468432/Playbook+Moving+to+Antigravity+on+Gemini+Enterprise+Plus+incl.+NAT+attestation)

### Scope & deliverables

1. **Golden Path Template Repository (`transurban/streamlit-bigquery-template`):**
   - Multipage Streamlit skeleton (`src/app.py`, `src/pages/`), `pyproject.toml` managed by `uv` proxied through **JFrog Artifactory (`transurban.jfrog.io`)** ([DDD5](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40615706809/DDD5+-+Artifactory)), with `ruff`, `bandit`, and `pytest` (`streamlit.testing.v1.AppTest`) configured ([DDD2](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40109245590/DDD2+-+Linting)).
   - Hardened non-root multi-stage `Dockerfile` (`--server.enableCORS=false`, `--server.enableXsrfProtection=true` behind Direct IAP).
   - `src/bq.py`: Singleton BigQuery client with **BigQuery Storage Read API** (`to_dataframe(create_bqstorage_client=True)`), `BigFrames` helper, `@st.cache_data(ttl=600, max_entries=100)`, enforced `maximum_bytes_billed`, and mandatory `QueryJobConfig(labels={"app": ..., "user_hash": ..., "cost_centre": ..., "env": ...})`.
   - `src/agent_sidekick.py`: Optional embedded `st.chat_input` sidekick connected to **Vertex AI Agent Engine (ADK)** + **Google MCP Toolbox for BigQuery** with `st.feedback("thumbs")` wired to Vertex AI GenAI Evaluation.
   - `infra/main.go`: 15-line Pulumi (Go) program consuming `platform.NewStreamlitApp`.
   - Portable agent instructions: root `AGENTS.md`, `CLAUDE.md` symlink, `.github/copilot-instructions.md`, and `.agents/hooks.json` (`postEdit` Ruff + `bq query --dry_run` cost check + NAT data leak check).
2. **Codified Skills in [`transurban/code-skills`](https://github.com/transurban/code-skills) ([DDD0](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42567892996/DDD0+-+Developer+Inner+Loop+Strategy)):**
   - Author and publish three skills to `transurban/code-skills` (installable via `/plugin` in Antigravity and Claude Code):
     - `sis-to-bq-migrator`: Translates `snowflake.snowpark.context.get_active_session()` and Snowflake SQL idioms (`FLATTEN`, `DATEADD`, `ILIKE`, `QUALIFY`, `PARSE_JSON`) to GoogleSQL / `BigFrames` + `src/bq.py` and generates `AppTest` parity tests.
     - `sis-disposition-triager`: Scores SiS apps against the 4-Tier Disposition Taxonomy (`Retire`, `Replace -> Looker`, `Reimagine -> Agentspace Agent Designer`, `Migrate -> Cloud Run Streamlit`).
     - `bq-streamlit-scaffold`: Scaffolds new pages, `streamlit-pydantic` forms, and Pulumi `BigQueryDatasets` bindings.

### Acceptance criteria

- `transurban/streamlit-bigquery-template` is marked as a GitHub Template Repository in `github.com/transurban`.
- The three skills (`sis-to-bq-migrator`, `sis-disposition-triager`, `bq-streamlit-scaffold`) are merged into [`transurban/code-skills`](https://github.com/transurban/code-skills) and verified in Google Antigravity (`agy`).
- A developer on a ZPA-protected Cloud Workstation can click "Use this template", customize the app name and access group, reach **Time to First Commit in < 15 minutes**, and deploy a working app to `dev` in **< 1 hour**.

### Out of scope

- Reusable GitHub Actions CI/CD workflow implementation details (covered in Story 7).

---

## 7. [ENG-2082](https://transurban.atlassian.net/browse/ENG-2082) — Reusable App CI/CD pipeline (GitHub Actions + SonarQube + JFrog Xray + Pulumi) (M / 5 pts)

### User story

As a **Data App Developer**, I want **a single reusable GitHub Actions workflow that runs Ruff, pytest `AppTest`, BigQuery SQL dry-runs, SonarQube SaaS, JFrog Xray container scanning, Pulumi deployment, and Docs-as-Code sync**, so that **every Streamlit app repo inherits Transurban's Sensible Default outer loop (`DDD1`–`DDD6`) with zero custom pipeline maintenance**.

### Context

Per [PE-WS4 Blueprints & Golden Path Templates](https://transurban.atlassian.net/wiki/spaces/CTS/pages/42531488146/PE-WS4+Blueprints+Golden+Path+Templates) and the [SEAL Development Design Decisions](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40093876406/Development+Design+Decisions), app teams should call a centralized reusable GitHub Actions workflow rather than copy-pasting CI YAML across repositories.

- **Reference Documents:**
  - Parent Epic: [ENG-2075 — Streamlit platform on BigQuery (replace Streamlit in Snowflake)](https://transurban.atlassian.net/browse/ENG-2075)
  - Source Control & CI: [DDD1 — GitHub](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40090632665/DDD1+-+GitHub) & [PE-WS4 Blueprints & Golden Path Templates](https://transurban.atlassian.net/wiki/spaces/CTS/pages/42531488146/PE-WS4+Blueprints+Golden+Path+Templates)
  - Linting: [DDD2 — Linting](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40109245590/DDD2+-+Linting)
  - Code Quality Gate: [DDD4 — SonarQube](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40476246070/DDD4+-+SonarQube)
  - Artifact & Vulnerability Scanning: [DDD5 — Artifactory](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40615706809/DDD5+-+Artifactory)
  - Docs-as-Code Projection: [DDD6 — Documentation Philosophy](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42375610524/DDD6+-+Documentation+Philosophy)

### Scope & deliverables

Build the reusable workflow `.github/workflows/streamlit-app-pipeline.yml` covering five automated stages:

1. **Lint, Security & Headless UI Test ([DDD2](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40109245590/DDD2+-+Linting)):**
   - Run `uv run ruff check`, `uv run ruff format --check`, `uv run bandit -r src/`, and `uv run pytest` (executing headless `streamlit.testing.v1.AppTest` tests).
   - Execute `bq query --dry_run` against all `.sql` files to validate GoogleSQL syntax and verify estimated bytes scanned before deployment.
2. **Static Analysis Quality Gate ([DDD4](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40476246070/DDD4+-+SonarQube)):**
   - Run **SonarQube SaaS (SonarCloud)** analysis and enforce the quality gate (coverage, reliability, maintainability, security hotspots) as a required PR status check.
3. **Container Build & Supply-Chain Scan ([DDD5](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40615706809/DDD5+-+Artifactory)):**
   - Resolve Python and Go dependencies via **JFrog Artifactory (`transurban.jfrog.io`)**, build the non-root container image, scan image layers and dependencies with **JFrog Xray**, and push the verified image to regional **GCP Artifact Registry** (`australia-southeast1`).
4. **Keyless Pulumi Deployment ([DDD1](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40090632665/DDD1+-+GitHub)):**
   - Authenticate via keyless GitHub OIDC → GCP Workload Identity Federation.
   - Run `pulumi preview` on PRs; run `pulumi up` to `dev` on merge to `main`, and to `prod` on release tag / GitHub Environment approval.
5. **Docs-as-Code Projection ([DDD6](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42375610524/DDD6+-+Documentation+Philosophy)):**
   - Automatically publish updated `README.md` and `docs/adr/` to Confluence and trigger the **Google Agentspace** connector sync on merge to `main`.

### Acceptance criteria

- `transurban/streamlit-bigquery-template` deploys end-to-end to `dev` and `prod` by invoking the reusable workflow with keyless OIDC authentication.
- Deliberately introducing a Ruff lint error, a failing `AppTest`, a SonarQube quality gate failure, or a critical JFrog Xray CVE blocks the PR/deployment pipeline.
- Merging a `README.md` change to `main` automatically updates the linked Confluence page per [DDD6](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42375610524/DDD6+-+Documentation+Philosophy).

### Out of scope

- Migrating legacy Jenkins or Bitbucket pipelines unrelated to [ENG-2075](https://transurban.atlassian.net/browse/ENG-2075).

---

## 8. [ENG-2083](https://transurban.atlassian.net/browse/ENG-2083) — BigQuery FinOps & three-layer cost guardrails (S / 3 pts)

### User story

As a **FinOps Lead and Data Platform Owner**, I want **three-layer BigQuery cost guardrails (dev-time dry-run hooks, app-time byte caps & caching, and platform-time quotas & attribution views)**, so that **Streamlit's reactive script re-run model cannot cause runaway BigQuery slot/byte spend and every dollar is attributed to an app and cost centre**.

### Context

Streamlit re-executes Python scripts on user widget interactions. Without guardrails, uncached or unpartitioned queries against multi-terabyte BigQuery tables can rapidly drive up spend. Epic [ENG-2075](https://transurban.atlassian.net/browse/ENG-2075) enforces defense-in-depth across the inner loop ([DDD0](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42567892996/DDD0+-+Developer+Inner+Loop+Strategy)), the application SDK, and the GCP project.

- **Reference Documents:**
  - Parent Epic: [ENG-2075 — Streamlit platform on BigQuery (replace Streamlit in Snowflake)](https://transurban.atlassian.net/browse/ENG-2075)
  - Inner Loop Guardrails: [DDD0 — Developer Inner Loop Strategy](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42567892996/DDD0+-+Developer+Inner+Loop+Strategy)

### Scope & deliverables

- **Layer 1 — Dev-Time Guardrail (Google Antigravity `hooks.json`):**
  - Configure `.agents/hooks.json` (`postEdit`) to run `bq query --dry_run --use_legacy_sql=false` whenever a `.sql` or `src/bq.py` query is modified, warning/blocking if estimated bytes scanned exceed 10 GiB or if a partitioned table is queried without a partition filter.
- **Layer 2 — App-Time Guardrail (`src/bq.py` & BI Engine):**
  - Enforce mandatory `QueryJobConfig(maximum_bytes_billed=app_cap, labels={"app": ..., "env": ..., "cost_centre": ..., "user_hash": ...})` on every BigQuery job.
  - Enforce `@st.cache_data(ttl=600)` + **BigQuery BI Engine** in-memory caching + **BigQuery Storage Read API** so UI interactions hit memory caches rather than re-billing BigQuery slots.
- **Layer 3 — Platform-Time Guardrail (GCP Quotas & FinOps Attribution View):**
  - Provision project-level custom query quotas (`QueryUsagePerDay` and `QueryUsagePerUserPerDay`) and GCP Billing budget alerts via Pulumi.
  - Create a shared BigQuery FinOps reporting view over `region-australia-southeast1.INFORMATION_SCHEMA.JOBS_BY_PROJECT` aggregating `total_bytes_billed`, `total_slot_ms`, and estimated cost by `labels.app`, `labels.cost_centre`, and `labels.user_hash` (exposed in Looker and queryable via **Google Agentspace**).

### Acceptance criteria

- Editing a SQL query that scans > 10 GiB triggers an immediate warning in Google Antigravity via `.agents/hooks.json` before code is even committed.
- Executing a query that exceeds `maximum_bytes_billed` in `dev` fails fast with a friendly Streamlit error banner and bills `0` bytes.
- Every query executed by the template app appears in `INFORMATION_SCHEMA.JOBS_BY_PROJECT` with populated `app`, `env`, `cost_centre`, and `user_hash` labels, and renders in the FinOps attribution view.

### Out of scope

- Enterprise-wide BigQuery slot reservation procurement outside the Streamlit platform projects (owned by the core `BQM` / Project Nova team).

---

## 9. [ENG-2084](https://transurban.atlassian.net/browse/ENG-2084) — Observability, Cloud Logging & OpenTelemetry tracing (S / 3 pts)

### User story

As an **SRE and App Owner**, I want **structured JSON logging to Cloud Logging, OpenTelemetry distributed tracing across Streamlit, BigQuery, and Vertex AI ADK, and automated Cloud Monitoring alerts**, so that **we can diagnose slow queries, monitor app availability, and correlate every BigQuery job back to the originating UI interaction**.

### Context

To operate production data apps on **Google Cloud Run** under [ENG-2075](https://transurban.atlassian.net/browse/ENG-2075), every app must emit structured logs and OpenTelemetry traces aligned with Transurban's `opentelemetry` skill in [`transurban/code-skills`](https://github.com/transurban/code-skills).

- **Reference Documents:**
  - Parent Epic: [ENG-2075 — Streamlit platform on BigQuery (replace Streamlit in Snowflake)](https://transurban.atlassian.net/browse/ENG-2075)
  - Skill Catalog (`opentelemetry` skill): [Transurban AI Coding Agents - Plugin & Skill Catalog](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42562814412/Transurban+AI+Coding+Agents+-+Plugin+Skill+Catalog)

### Scope & deliverables

- **Structured JSON Logging (`src/telemetry.py`):**
  - Emit structured JSON logs to `stdout` automatically ingested by **Cloud Logging** with standard fields: `severity`, `logging.googleapis.com/trace`, `logging.googleapis.com/spanId`, `app`, `env`, `page`, `user_hash`, `bq_job_id`, `bytes_billed`, `duration_ms`, and `cache_hit`.
- **OpenTelemetry Distributed Tracing (`Cloud Trace`):**
  - Instrument the Golden Path template using the `opentelemetry` skill (`opentelemetry-exporter-gcp-trace`), creating linked spans across `streamlit.page_render` → `bigquery.query` (including `bq.job_id` and `bq.bytes_billed` span attributes) → `vertex_ai.adk_turn`.
- **Automated Dashboards & Alerting in `StreamlitApp` Pulumi Component:**
  - Extend `platform.NewStreamlitApp` to automatically provision a per-app **Cloud Monitoring** uptime check (`/_stcore/health`), a standard golden-signals dashboard (request latency, 5xx error rate, active instances, BigQuery slot/byte consumption), and alert policies routed to the owning team's notification channel.

### Acceptance criteria

- Logs emitted by the template app appear in **Cloud Logging** with structured JSON fields (`app`, `user_hash`, `bq_job_id`, `bytes_billed`) and clickable correlation to **Cloud Trace**.
- A slow page render produces an end-to-end waterfall trace in **Cloud Trace** showing the exact child BigQuery query and Vertex AI ADK latency.
- Provisioning an app with `platform.NewStreamlitApp` automatically creates its Cloud Monitoring uptime check and alert policy.

### Out of scope

- Third-party APM SaaS agents (e.g., Datadog/New Relic); all telemetry runs natively inside Google Cloud Operations Suite (`Cloud Logging`, `Cloud Trace`, `Cloud Monitoring`).

---

## 10. [ENG-2085](https://transurban.atlassian.net/browse/ENG-2085) — Security review, threat model & NAT compliance guardrails (M / 5 pts)

### User story

As a **Cyber Security Architect and Platform Owner**, I want **a comprehensive threat model, data-classification mapping, Model Armor guardrails, and NAT data compliance verification for the Streamlit-on-BigQuery platform**, so that **Security formally signs off the platform before the first production application goes live**.

### Context

Under Epic [ENG-2075](https://transurban.atlassian.net/browse/ENG-2075), Streamlit apps access enterprise BigQuery datasets and optionally expose embedded **Vertex AI Agent Engine (ADK)** sidekicks. The platform must satisfy Transurban's Cyber Security standards and the **National / Sensitive Data (NAT)** attestation requirements defined in the [Gemini Enterprise Plus Playbook](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42650468432/Playbook+Moving+to+Antigravity+on+Gemini+Enterprise+Plus+incl.+NAT+attestation).

- **Reference Documents:**
  - Parent Epic: [ENG-2075 — Streamlit platform on BigQuery (replace Streamlit in Snowflake)](https://transurban.atlassian.net/browse/ENG-2075)
  - NAT Attestation & Gemini Enterprise Plus: [Playbook: Moving to Antigravity on Gemini Enterprise Plus (incl. NAT attestation)](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42650468432/Playbook+Moving+to+Antigravity+on+Gemini+Enterprise+Plus+incl.+NAT+attestation)
  - Inner Loop Security & Certs: [DDD0 — Developer Inner Loop Strategy](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42567892996/DDD0+-+Developer+Inner+Loop+Strategy)
  - Pair Programming for High-Consequence Reviews: [DDD3 — Pair Programming](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40142308116/DDD3+-+Pair+Programming)
  - SAST & Supply Chain Security: [DDD4 — SonarQube](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40476246070/DDD4+-+SonarQube) & [DDD5 — Artifactory](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40615706809/DDD5+-+Artifactory)

### Scope & deliverables

- **Platform Threat Model (`docs/security/threat-model.md`, projected to Confluence per [DDD6](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42375610524/DDD6+-+Documentation+Philosophy)):**
  - Mitigate **IAP bypass / header spoofing**: Enforced via `INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER` + Direct IAP + mandatory ES256 JWT verification (`X-Goog-IAP-Jwt-Assertion`).
  - Mitigate **Runtime SA over-privilege**: Dedicated per-app Service Account with dataset-scoped IAM (`roles/bigquery.dataViewer`) and Pulumi unit-test policy gates.
  - Mitigate **Data exfiltration**: **VPC Service Controls (VPC-SC)** perimeter around `bigquery.googleapis.com`, `bigquerystorage.googleapis.com`, and `run.googleapis.com`, plus audit logging of CSV/dataframe exports.
  - Mitigate **Prompt injection / PII leakage in ADK sidekick**: Enable **Google Cloud Model Armor** + **Cloud DLP (Sensitive Data Protection)** inspection templates on Vertex AI Agent Engine inputs and outputs.
  - Mitigate **Supply-chain vulnerabilities**: Mandatory **SonarQube SaaS** ([DDD4](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40476246070/DDD4+-+SonarQube)) and **JFrog Xray** ([DDD5](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40615706809/DDD5+-+Artifactory)) gates.
- **Data Classification & NAT Compliance Mapping:**
  - Define the formal decision matrix mapping Transurban data classifications to **Tier 1 (Per-App Service Account)** vs **Tier 2 (Caller's Rights OAuth + Dataplex RLS/CLS + VPC-SC)**.
  - Enforce NAT data guardrails in `.agents/rules/` and pre-commit hooks per the [Gemini Enterprise Plus Playbook](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42650468432/Playbook+Moving+to+Antigravity+on+Gemini+Enterprise+Plus+incl.+NAT+attestation).
- **Security Review & Sign-off:**
  - Conduct formal review / penetration test with Cyber Security and record sign-off.

### Acceptance criteria

- Threat model and data-classification matrix are merged to GitHub, projected to Confluence, and linked to [ENG-2075](https://transurban.atlassian.net/browse/ENG-2075).
- Model Armor and NAT compliance pre-commit/agent rules are active and verified by automated tests.
- Formal Cyber Security sign-off is recorded on [ENG-2075](https://transurban.atlassian.net/browse/ENG-2075) with zero unresolved Critical or High findings.

### Out of scope

- Modifying enterprise-wide Microsoft Entra ID conditional access policies outside the Workforce Identity Federation pool configuration.

---

## 11. [ENG-2086](https://transurban.atlassian.net/browse/ENG-2086) — Pilot migration of one SiS app using Antigravity + Pair Programming (M / 5 pts)

### User story

As a **Product Owner of an existing Streamlit in Snowflake (SiS) application**, I want **my application migrated to the new Cloud Run + BigQuery platform using Google Antigravity and human-agent pair programming**, so that **my business users experience sub-second performance via Google Agentspace with zero loss of functionality before Snowflake is decommissioned**.

### Context

To prove the platform end-to-end under [ENG-2075](https://transurban.atlassian.net/browse/ENG-2075) and refine the `sis-to-bq-migrator` skill in [`transurban/code-skills`](https://github.com/transurban/code-skills), the platform team will pair with a data/application squad ([DDD3 — Pair Programming](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40142308116/DDD3+-+Pair+Programming)) to migrate a representative production SiS app (e.g., aligning with `DAP-2729` / Project Nova).

- **Reference Documents:**
  - Parent Epic: [ENG-2075 — Streamlit platform on BigQuery (replace Streamlit in Snowflake)](https://transurban.atlassian.net/browse/ENG-2075)
  - Inner Loop & Skills: [DDD0 — Developer Inner Loop Strategy](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42567892996/DDD0+-+Developer+Inner+Loop+Strategy) & [Transurban AI Coding Agents - Plugin & Skill Catalog](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42562814412/Transurban+AI+Coding+Agents+-+Plugin+Skill+Catalog)
  - Pair Programming: [DDD3 — Pair Programming](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40142308116/DDD3+-+Pair+Programming)
  - Repo Retirement / Archival: [DDD1 — GitHub](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40090632665/DDD1+-+GitHub)

### Scope & deliverables

- **Pilot Selection & Baseline Capture:**
  - Select one representative production SiS application whose underlying Snowflake tables are available in BigQuery (`BQM`).
  - Capture baseline Snowflake query outputs, row counts, and UI screenshots.
- **Agent-Assisted Migration ([DDD0](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42567892996/DDD0+-+Developer+Inner+Loop+Strategy), [DDD3](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40142308116/DDD3+-+Pair+Programming)):**
  - Pair program on a ZPA-protected **Google Cloud Workstation** using **Google Antigravity (`agy`)** and the `sis-to-bq-migrator` skill in [`transurban/code-skills`](https://github.com/transurban/code-skills):
    - Scaffold the repo from `transurban/streamlit-bigquery-template`.
    - Convert `snowflake.snowpark.context.get_active_session()` and Snowflake SQL (`FLATTEN`, `DATEADD`, `ILIKE`, `QUALIFY`, variant JSON paths) to **GoogleSQL / BigFrames** and `src/bq.py`.
    - Author headless `streamlit.testing.v1.AppTest` parity tests verifying identical row counts and aggregates against BigQuery.
- **Production Cutover & Continuous Learning (`/learn`):**
  - Deploy to `dev` and `prod` behind Direct IAP and register the app in **Google Agentspace**.
  - Run in parallel with the legacy SiS app, collect formal business user sign-off, schedule the legacy SiS app for retirement, and feed any discovered SQL/Snowpark edge cases back into `sis-to-bq-migrator` in `transurban/code-skills`.

### Acceptance criteria

- The pilot Streamlit app is live in `prod` on Cloud Run + BigQuery behind Direct IAP and discoverable in **Google Agentspace**.
- Automated `AppTest` and data-parity checks confirm matching metrics between the legacy SiS app and the new BigQuery app.
- The business owner has signed off on the migrated app and agreed on the decommission date for the legacy SiS version.
- Learnings from the pilot are merged back into the `sis-to-bq-migrator` skill in [`transurban/code-skills`](https://github.com/transurban/code-skills).

### Out of scope

- Migrating the remaining portfolio of SiS apps within this story (covered via the migration backlog generated in Story 12).

---

## 12. [ENG-2087](https://transurban.atlassian.net/browse/ENG-2087) — Automated SiS app inventory, 4-tier disposition & migration backlog (S / 3 pts)

### User story

As a **Program Manager and Data Platform Lead**, I want **an automated inventory of every existing Streamlit in Snowflake (SiS) app classified into the 4-Tier Disposition Taxonomy (`Retire`, `Replace -> Looker`, `Reimagine -> Agentspace Agent Designer`, `Migrate -> Cloud Run Streamlit`) with linked Jira tickets**, so that **we eliminate unnecessary migrations and sequence the remaining apps ahead of the Snowflake exit date**.

### Context

As clarified on [ENG-2075](https://transurban.atlassian.net/browse/ENG-2075), not every Streamlit in Snowflake script should become a containerized Cloud Run service. By classifying every SiS workload using the **4-Tier Disposition Taxonomy**, simple read-only dashboards move to **Looker** and simple conversational/lookup tools move to **Google Agentspace Agent Designer (No-Code)**, reserving **Cloud Run + BigQuery Streamlit** for true stateful Python applications.

- **Reference Documents:**
  - Parent Epic: [ENG-2075 — Streamlit platform on BigQuery (replace Streamlit in Snowflake)](https://transurban.atlassian.net/browse/ENG-2075)
  - GitHub Archival Policy: [DDD1 — GitHub](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40090632665/DDD1+-+GitHub)
  - Skill Catalog (`sis-disposition-triager`, `spec-to-backlog`): [Transurban AI Coding Agents - Plugin & Skill Catalog](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42562814412/Transurban+AI+Coding+Agents+-+Plugin+Skill+Catalog)

### Scope & deliverables

- **Automated SiS Discovery & Usage Extraction:**
  - Query Snowflake metadata (`INFORMATION_SCHEMA.STREAMLITS` and `SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY` / `ACCESS_HISTORY` over the last 90 days) and scan GitHub repositories to extract every SiS app's owner, active user count, query volume, referenced tables, and Python/Snowpark AST complexity.
- **4-Tier Disposition Classification (`sis-disposition-triager` skill):**
  - Classify and agree disposition with each app owner:
    1. **Retire:** `0` active users in 90 days or superseded → archive repository cleanly in GitHub per [DDD1](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/40090632665/DDD1+-+GitHub) (never delete).
    2. **Replace (BI Dashboard):** Read-only charts/KPIs with no stateful Python logic → rebuild in **Looker / Looker Studio Pro** on BigQuery BI Engine.
    3. **Reimagine (No-Code Agent):** Simple parameterised SQL lookups or table Q&A → rebuild in **Google Agentspace Agent Designer** backed by **Google MCP Toolbox for BigQuery** (zero code/container to maintain).
    4. **Migrate (Stateful Data App):** Custom Python workflows, write-backs, simulations, or ML apps → migrate to **Cloud Run + BigQuery Streamlit** using the `google-antigravity` SDK batch migration script (`scripts/batch_migrate_sis.py`) to open draft GitHub PRs automatically.
- **Jira Backlog Generation (`twg`):**
  - Create and link the per-app Jira work items under/related to [ENG-2075](https://transurban.atlassian.net/browse/ENG-2075) via `twg jira workitem create` (`spec-to-backlog` skill), ordered by BigQuery dataset readiness (`BQM`) and the Snowflake exit date.

### Acceptance criteria

- 100% of existing Streamlit in Snowflake (SiS) apps are catalogued with usage metrics, owner, BigQuery table readiness, and an owner-agreed disposition (`Retire` / `Replace` / `Reimagine` / `Migrate`).
- Jira tickets for all `Reimagine` and `Migrate` apps are created via `twg` and linked to [ENG-2075](https://transurban.atlassian.net/browse/ENG-2075).
- The `scripts/batch_migrate_sis.py` Antigravity SDK script is tested on at least one `Migrate` candidate to verify automated draft PR generation.

### Out of scope

- Executing the full migration of every `Migrate`-tier app within this single story (each app is tracked via its generated Jira ticket).

---

## 13. [ENG-2088](https://transurban.atlassian.net/browse/ENG-2088) — Docs-as-Code, onboarding & support model (DDD6) (S / 3 pts)

### User story

As a **Data Scientist or Analytics Engineer in a feature squad**, I want **self-service Docs-as-Code quickstarts, migration playbooks, and a clear support model projected automatically from GitHub to Confluence and Google Agentspace**, so that **my team can build, migrate, and operate BigQuery Streamlit apps independently without hand-holding from the platform team**.

### Context

Per [DDD6 — Documentation Philosophy](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42375610524/DDD6+-+Documentation+Philosophy) (*"Docs-as-Code in GitHub; Maintain Once, Present Everywhere; Altitude Traceability"*), documentation for the Streamlit-on-BigQuery platform ([ENG-2075](https://transurban.atlassian.net/browse/ENG-2075)) must live in GitHub alongside code and tests, declare an explicit freshness mechanism, and project automatically to **Confluence (`SEAL` / `CTS`)** and **Google Agentspace**.

- **Reference Documents:**
  - Parent Epic: [ENG-2075 — Streamlit platform on BigQuery (replace Streamlit in Snowflake)](https://transurban.atlassian.net/browse/ENG-2075)
  - Documentation Philosophy: [DDD6 — Documentation Philosophy](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42375610524/DDD6+-+Documentation+Philosophy)
  - Inner Loop Metrics (Principle 5): [DDD0 — Developer Inner Loop Strategy](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42567892996/DDD0+-+Developer+Inner+Loop+Strategy)
  - Remote Dev Workspace: [DDD7 — Remote Development Workspace](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42566713776/DDD7+-+Remote+Development+Workspace)

### Scope & deliverables

- **Author in GitHub (`docs/`) & Project to Confluence + Google Agentspace ([DDD6](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42375610524/DDD6+-+Documentation+Philosophy)):**
  - **Quickstart Guide:** *"Your first BigQuery Streamlit app in under 1 hour"* (covering both ZPA-protected **Google Cloud Workstations** per [DDD7](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42566713776/DDD7+-+Remote+Development+Workspace) and local macOS via `transurban/mac-dev-bootstrap`).
  - **Migration Playbook:** *"Streamlit in Snowflake (SiS) to Google Garden Playbook"* covering the 4-Tier Disposition Taxonomy, building no-code agents in **Google Agentspace Agent Designer**, and running the `sis-to-bq-migrator` skill in **Google Antigravity**.
  - **Operations Runbook & Ownership Model:** Clear RACI between Platform Engineering (owns `StreamlitApp` Pulumi component, Golden Path template, `transurban/code-skills` plugin, and shared GCP stack) and App/Data squads (own app code, dataset IAM requests, and BigQuery spend).
- **DDD6 Metadata Contract & Altitude Traceability:**
  - Every Markdown document includes frontmatter declaring **Owner**, **Freshness mechanism** (CI test / Git-to-Confluence webhook), and **Presentation targets**, plus an **Altitude Traceability** table linking:
    - *10 ft (Code/Tests)* ↔ *100 ft (`docs/adr/ADR-001..004`)* ↔ *1,000 ft (`README.md`)* ↔ *10,000 ft (Platform Architecture)* ↔ *100,000 ft ([DDD0](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42567892996/DDD0+-+Developer+Inner+Loop+Strategy) / [PE-WS4](https://transurban.atlassian.net/wiki/spaces/CTS/pages/42531488146/PE-WS4+Blueprints+Golden+Path+Templates))*.
- **Second-Team Onboarding Validation & DX Metrics ([DDD0 Principle 5](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42567892996/DDD0+-+Developer+Inner+Loop+Strategy)):**
  - Observe a second squad onboarding using only the projected docs and `transurban/code-skills` plugin, recording **Time to First Commit (< 15 minutes)** and **Time to First Deployed App (< 1 hour)**.

### Acceptance criteria

- All guides and runbooks are merged in GitHub with valid [DDD6](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42375610524/DDD6+-+Documentation+Philosophy) metadata headers and automatically projected to Confluence and indexed in **Google Agentspace**.
- A second team successfully deploys a new BigQuery Streamlit app to `dev` using only the documentation and `transurban/code-skills` plugin, with zero platform team intervention.
- Hard DX metrics (**Time to First Commit < 15 min**, **Time to First Deployed App < 1 hr**) are recorded and linked to [ENG-2075](https://transurban.atlassian.net/browse/ENG-2075).

### Out of scope

- Hand-maintained wiki pages in Confluence that are not backed by a GitHub source-of-truth file (prohibited by [DDD6](https://transurban.atlassian.net/wiki/spaces/SEAL/pages/42375610524/DDD6+-+Documentation+Philosophy)).

---
