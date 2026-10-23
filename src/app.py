"""NCX Portal Emission & Ventilation Analytics — SEAL Golden Path App (`ENG-2075`).

Main Streamlit entrypoint (`src/app.py`) implementing Option 1 (Hybrid Golden Path
Container):
- Zero-Trust IAP JWT validation + Entra ID Workforce Identity Pool RBAC (`src/auth.py`)
- Governed BigQuery execution with 5 GiB circuit breaker & FinOps labels (`src/bq.py`)
- OpenTelemetry span tracing & Cloud Logging structured JSON (`src/telemetry.py`)
- Vertex AI ADK Engineering Sidekick with `st.feedback("thumbs")` (`src/agent_sidekick.py`)
- Full 60fps interactive HTML/SVG/Chart.js + Time-Scrubber frontend (`src/template_engine.py`)
"""

from __future__ import annotations

from datetime import date
import os
from pathlib import Path
import sys

_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import streamlit as st
import streamlit.components.v1 as components

from src.agent_sidekick import render_agent_sidekick
from src.auth import DEFAULT_ALLOWED_GROUPS, get_current_user, require_group
from src.bq import get_ncx_dashboard_payload
from src.telemetry import log_structured_event
from src.template_engine import render_dashboard_html

st.set_page_config(
    page_title="NCX Portal Emission & Ventilation Analytics | Transurban",
    page_icon="🚇",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        .block-container {
            padding-top: 0.75rem !important;
            padding-bottom: 0.5rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            max-width: 100% !important;
        }
        .seal-status-bar {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            background: #0F172A;
            color: #F8FAFC;
            padding: 8px 16px;
            border-radius: 8px;
            margin-bottom: 8px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            font-size: 12px;
            border-left: 4px solid #009D4E;
        }
        .seal-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: #1E293B;
            border: 1px solid #334155;
            padding: 3px 9px;
            border-radius: 999px;
            font-weight: 600;
            color: #E2E8F0;
        }
        .seal-badge-green {
            background: rgba(0, 157, 78, 0.18);
            border-color: #009D4E;
            color: #4ADE80;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


@require_group(*DEFAULT_ALLOWED_GROUPS)
def main() -> None:
    """Render the RBAC-protected NCX Portal Emission & Ventilation Analytics application."""
    user = get_current_user()

    with st.sidebar:
        st.markdown("### 🛡️ SEAL Golden Path Controls")
        st.caption(
            f"**User**: `{user.email}`  \n"
            f"**Auth Mode**: `{user.auth_mode}`  \n"
            f"**Groups**: `{', '.join(user.groups)}`"
        )

        st.divider()
        st.markdown("### 🗄️ Telemetry Data Source (`ENG-2083`)")
        default_live = os.environ.get("DEFAULT_DATA_MODE", "").strip().lower() == "live_bigquery"
        data_mode = st.radio(
            "Select Telemetry Feed",
            options=[
                "Verified 4-Week Snapshot (Instant)",
                "Live BigQuery (tu-data-edw-pr-1.a113_roadside)",
            ],
            index=1 if default_live else 0,
            help=(
                "Verified 4-Week Snapshot loads the pre-validated Sep 22 – Oct 20, 2026 "
                "AEST dataset (including the Oct 16–17 Forced Level 3 test) with zero "
                "BigQuery scan cost. Live BigQuery executes governed SQL with a 5 GiB "
                "circuit breaker and Australia/Sydney timezone enforcement."
            ),
        )

        start_date_val = date(2026, 9, 22)
        end_date_val = date(2026, 10, 20)
        force_live_refresh = False
        auto_refresh_choice = "Off (10m Cache)"

        if data_mode.startswith("Live BigQuery"):
            col1, col2 = st.columns(2)
            with col1:
                start_date_val = st.date_input("Start (AEST)", value=date(2026, 9, 22))
            with col2:
                end_date_val = st.date_input("End (AEST)", value=date(2026, 10, 20))
            auto_refresh_choice = st.selectbox(
                "⏱️ Auto-Sync Interval (Live BigQuery)",
                options=["Off (10m Cache)", "Every 1 min", "Every 5 min", "Every 15 min"],
                index=0,
                help="Automatically re-polls BigQuery on a timer for live control-room wallboards.",
            )
            force_live_refresh = st.button("🔄 Execute Governed BigQuery Run", use_container_width=True)
            if force_live_refresh:
                st.cache_data.clear()

        loader_mode = "live_bigquery" if data_mode.startswith("Live BigQuery") else "cached_snapshot"
        payload = get_ncx_dashboard_payload(
            mode=loader_mode,
            start_date=start_date_val.isoformat(),
            end_date=end_date_val.isoformat(),
            user_hash=user.user_hash,
            access_token=user.access_token,
        )
        finops_meta = payload.get("metadata", {}).get("finops", {})
        job_ids = ",".join(finops_meta.get("bq_job_ids", ["snapshot-cache-hit"]))

        st.markdown("#### 📊 FinOps & Telemetry Status")
        st.caption(
            f"- **Job ID**: `{job_ids}`\n"
            f"- **Bytes Billed**: `{finops_meta.get('bytes_billed', 0):,} B` (Cap: `5 GiB`)\n"
            f"- **Cache Hit**: `{finops_meta.get('cache_hit', True)}`\n"
            f"- **Duration**: `{finops_meta.get('duration_ms', 0.0)} ms`\n"
            f"- **Timezone**: `Australia/Sydney (AEST)`"
        )

        st.divider()
        st.markdown("### 🤖 Vertex AI ADK Sidekick (`ENG-2085`)")
        render_agent_sidekick(payload, user_email=user.email)

    log_structured_event(
        "dashboard_view_rendered",
        user_hash=user.user_hash,
        bq_job_id=job_ids,
        bytes_billed=finops_meta.get("bytes_billed", 0),
        duration_ms=finops_meta.get("duration_ms", 0.0),
        cache_hit=finops_meta.get("cache_hit", True),
        trace_context=user.trace_context,
        extra={"data_mode": loader_mode},
    )

    refresh_map = {
        "Off (10m Cache)": None,
        "Every 1 min": "60s",
        "Every 5 min": "300s",
        "Every 15 min": "900s",
    }
    run_every_val = refresh_map.get(auto_refresh_choice)

    @st.fragment(run_every=run_every_val)
    def _render_live_dashboard_panel() -> None:
        current_payload = (
            get_ncx_dashboard_payload(
                mode=loader_mode,
                start_date=start_date_val.isoformat(),
                end_date=end_date_val.isoformat(),
                user_hash=user.user_hash,
                access_token=user.access_token,
            )
            if run_every_val
            else payload
        )
        current_finops = current_payload.get("metadata", {}).get("finops", {})
        current_jobs = ",".join(current_finops.get("bq_job_ids", ["snapshot-cache-hit"]))

        st.markdown(
            f"""
            <div class="seal-status-bar">
                <div>
                    <strong>TRANSURBAN SEAL GOLDEN PATH (ENG-2075)</strong> &nbsp;|&nbsp;
                    <span>NorthConnex (M11) Tunnel Ventilation &amp; Portal Emission Analytics</span>
                </div>
                <div style="display:flex; gap:8px; align-items:center;">
                    <span class="seal-badge seal-badge-green">🔒 IAP + Entra ID: {user.email}</span>
                    <span class="seal-badge">🗄️ Job: {current_jobs}</span>
                    <span class="seal-badge">⚡ Billed: {current_finops.get('bytes_billed', 0):,} B / 5 GiB Cap</span>
                    <span class="seal-badge">🔄 Sync: {auto_refresh_choice}</span>
                    <span class="seal-badge">🕒 TZ: Australia/Sydney (AEST)</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        compiled_html = render_dashboard_html(current_payload)
        components.html(compiled_html, height=1880, scrolling=True)

    _render_live_dashboard_panel()


if __name__ == "__main__":
    main()
