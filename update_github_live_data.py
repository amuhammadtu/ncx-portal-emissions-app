"""Pull live BigQuery telemetry from `tu-data-edw-pr-1.a113_roadside`
(`ncx_traffic_loops`, `ncx_pmcs_airf`, `ncx_pmcs_jftvz_03`, `ncx_pmcs_cems`, `ncx_pmcs_vaf`, `ncx_events`)
and generate GitHub Pages browser-runnable apps (`index.html`, `docs/index.html`, and `docs/streamlit.html`).

This allows the NCX Portal Emissions App to run directly via a live GitHub Pages URL
(`https://<org-or-user>.github.io/<repo>/`) without requiring users to download HTML files
and while waiting for GCP Cloud Run IAM provisioning.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent
DOCS_DIR = APP_ROOT / "docs"

# Ensure user site-packages and app root are on sys.path
for p in [
    APP_ROOT,
    Path(r"C:\Users\amuhammad\AppData\Roaming\Python\Python314\site-packages"),
    Path(r"C:\Program Files\Python314\Lib\site-packages"),
]:
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

try:
    import pip_system_certs.wrapt_requests  # noqa: F401
except ImportError:
    pass

from google.cloud import bigquery
from src.bq import (
    build_finops_job_config,
    build_ncx_events_sql,
    build_ncx_timeseries_sql,
    get_tod_baseline,
)


def fetch_live_bq_payload(project_id: str = "tu-data-edw-pr-1", days: int = 14) -> dict:
    """Query `tu-data-edw-pr-1.a113_roadside` across all 6 NCX tables with AEST conversion."""
    end_dt = dt.date.today() + dt.timedelta(days=1)
    start_dt = end_dt - dt.timedelta(days=days + 1)
    start_date = start_dt.strftime("%Y-%m-%d")
    end_date = end_dt.strftime("%Y-%m-%d")

    print(
        f"[1/3] Querying live BigQuery `{project_id}.a113_roadside` "
        f"({start_date} -> {end_date}, 30-min intervals)..."
    )
    client = bigquery.Client(project=project_id, location="australia-southeast1")
    job_cfg = build_finops_job_config(user_hash="github-pages-sync")

    sql_ts = build_ncx_timeseries_sql(start_date, end_date, project_id=project_id)
    sql_ev = build_ncx_events_sql(start_date, end_date, project_id=project_id)

    df_ts = client.query(sql_ts, job_config=job_cfg).to_dataframe(create_bqstorage_client=False)
    df_ev = client.query(sql_ev, job_config=job_cfg).to_dataframe(create_bqstorage_client=False)

    # Filter out future empty rows beyond the latest telemetry reading
    non_empty = df_ts[(df_ts["total_traffic_vol"] > 0) | (df_ts["s2_flow"] != 0) | (df_ts["n8_flow"] != 0)]
    if not non_empty.empty:
        max_time = non_empty["sydney_time"].max()
        df_ts = df_ts[df_ts["sydney_time"] <= max_time].copy()
    else:
        max_time = df_ts["sydney_time"].max() if not df_ts.empty else "N/A"

    nb_baselines: list[int] = []
    sb_baselines: list[int] = []
    overdrive_flags: list[int] = []
    for _, row in df_ts.iterrows():
        dt_syd = dt.datetime.strptime(str(row["sydney_time"]), "%Y-%m-%d %H:%M")
        nb_base, sb_base = get_tod_baseline(dt_syd)
        nb_baselines.append(nb_base)
        sb_baselines.append(sb_base)
        is_od = 1 if (row["nb_vent_level"] > nb_base or row["sb_vent_level"] > sb_base) else 0
        overdrive_flags.append(is_od)

    df_ts["nb_tod_baseline"] = nb_baselines
    df_ts["sb_tod_baseline"] = sb_baselines
    df_ts["is_vent_overdrive"] = overdrive_flags

    synced_at = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S AEST")
    print(
        f"      [OK] Retrieved {len(df_ts):,} 30-min intervals & {len(df_ev):,} Portal Emissions alarms "
        f"(Latest AEST: {max_time})"
    )

    return {
        "metadata": {
            "title": "NorthConnex Tunnel Ventilation & Portal Emission Trend Model (Live BigQuery)",
            "source_mode": "live_bigquery",
            "project_id": project_id,
            "dataset": "a113_roadside",
            "start_date": start_date,
            "end_date": end_date,
            "latest_telemetry_aest": str(max_time),
            "synced_at_aest": synced_at,
            "interval_minutes": 30,
            "total_intervals": len(df_ts),
            "total_alarms": len(df_ev),
            "generated_at": synced_at,
        },
        "timeseries": json.loads(df_ts.to_json(orient="records")),
        "alarm_events": json.loads(df_ev.to_json(orient="records")),
    }


def build_interactive_html(payload: dict) -> str:
    """Generate a standalone interactive HTML web app that runs directly on GitHub Pages."""
    payload_json = json.dumps(payload)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>NCX Tunnel Ventilation & Portal Emission Analytics (Live BigQuery)</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    :root {{
      --bg: #0b1120;
      --panel: #111827;
      --border: #1e293b;
      --text: #f8fafc;
      --muted: #94a3b8;
      --accent: #38bdf8;
      --green: #22c55e;
      --amber: #f59e0b;
      --red: #ef4444;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
    }}
    header {{
      background: linear-gradient(90deg, #0f172a 0%, #1e293b 100%);
      border-bottom: 1px solid var(--border);
      padding: 16px 26px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 14px;
    }}
    .title-group h1 {{ margin: 0; font-size: 1.3rem; font-weight: 700; }}
    .title-group p {{ margin: 4px 0 0 0; font-size: 0.82rem; color: var(--muted); }}
    .badge-row {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
    .badge {{
      padding: 6px 12px;
      border-radius: 999px;
      font-size: 0.76rem;
      font-weight: 600;
      background: rgba(34, 197, 94, 0.14);
      color: #4ade80;
      border: 1px solid rgba(34, 197, 94, 0.35);
    }}
    .badge.info {{
      background: rgba(56, 189, 248, 0.14);
      color: #38bdf8;
      border-color: rgba(56, 189, 248, 0.35);
    }}
    .layout {{
      display: grid;
      grid-template-columns: 280px 1fr;
      min-height: calc(100vh - 72px);
    }}
    aside {{
      background: var(--panel);
      border-right: 1px solid var(--border);
      padding: 20px;
    }}
    aside h3 {{
      margin-top: 0;
      font-size: 0.85rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--muted);
    }}
    .control-group {{ margin-bottom: 16px; }}
    .control-group label {{
      display: block;
      font-size: 0.8rem;
      color: var(--muted);
      margin-bottom: 6px;
    }}
    select, input[type="range"], input[type="text"], button {{
      width: 100%;
      padding: 8px 10px;
      border-radius: 6px;
      border: 1px solid #334155;
      background: #0f172a;
      color: var(--text);
      font-size: 0.85rem;
    }}
    button.btn-primary {{
      background: #0284c7;
      border-color: #0369a1;
      font-weight: 600;
      cursor: pointer;
      margin-top: 8px;
    }}
    button.btn-primary:hover {{ background: #0369a1; }}
    .nav-link {{
      display: block;
      text-align: center;
      padding: 8px 10px;
      border-radius: 6px;
      background: rgba(56, 189, 248, 0.12);
      color: #38bdf8;
      text-decoration: none;
      font-size: 0.82rem;
      font-weight: 600;
      border: 1px solid rgba(56, 189, 248, 0.3);
      margin-top: 10px;
    }}
    main {{ padding: 22px 26px; overflow-x: hidden; }}
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(185px, 1fr));
      gap: 14px;
      margin-bottom: 20px;
    }}
    .kpi-card {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 14px 16px;
    }}
    .kpi-label {{
      font-size: 0.75rem;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .kpi-value {{
      font-size: 1.5rem;
      font-weight: 700;
      margin-top: 6px;
      color: var(--text);
    }}
    .kpi-sub {{ font-size: 0.74rem; color: #4ade80; margin-top: 4px; }}
    .chart-card {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 16px;
      margin-bottom: 18px;
    }}
    .chart-card h4 {{ margin: 0 0 10px 0; font-size: 0.92rem; color: var(--text); }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.8rem; }}
    th, td {{ padding: 8px 10px; border-bottom: 1px solid var(--border); text-align: left; }}
    th {{ background: #0f172a; color: var(--muted); font-weight: 600; position: sticky; top: 0; }}
    .table-wrap {{ max-height: 320px; overflow-y: auto; border: 1px solid var(--border); border-radius: 8px; }}
    @media (max-width: 860px) {{
      .layout {{ grid-template-columns: 1fr; }}
      aside {{ border-right: none; border-bottom: 1px solid var(--border); }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="title-group">
      <h1>NCX Tunnel Ventilation & Portal Emission Analytics</h1>
      <p>NorthConnex (`tu-data-edw-pr-1.a113_roadside`) &bull; Explicit UTC &rarr; AEST (`Australia/Sydney`) Timezone Enforcement</p>
    </div>
    <div class="badge-row">
      <span class="badge">&#9679; Live BigQuery Telemetry: <span id="latest-ts"></span> AEST</span>
      <span class="badge info">Synced: <span id="synced-at"></span></span>
    </div>
  </header>

  <div class="layout">
    <aside>
      <h3>Telemetry Controls</h3>
      <div class="control-group">
        <label for="direction-select">Tunnel Direction / Section</label>
        <select id="direction-select">
          <option value="BOTH">Both Tubes (Southbound S2/S8 + Northbound N8)</option>
          <option value="SB">Southbound (S2 Entry / S8 Exit Portal)</option>
          <option value="NB">Northbound (N2 Entry / N8 Exit Portal)</option>
        </select>
      </div>

      <div class="control-group">
        <label for="days-range">Lookback Window: <strong id="days-label">7</strong> Days</label>
        <input type="range" id="days-range" min="1" max="14" value="7" />
      </div>

      <div class="control-group">
        <label for="tod-filter">Time-of-Day Filter</label>
        <select id="tod-filter">
          <option value="ALL">All Hours (24h)</option>
          <option value="DAY">Daytime (06:00 – 22:00 AEST)</option>
          <option value="NIGHT">Night Hygiene / Maintenance (22:00 – 06:00 AEST)</option>
        </select>
      </div>

      <button class="btn-primary" id="export-csv-btn">Download Telemetry CSV</button>
      <a class="nav-link" href="./streamlit.html">Switch to Full Python Streamlit (Stlite) &rarr;</a>

      <hr style="border:0;border-top:1px solid var(--border);margin:18px 0;" />
      <div style="font-size:0.76rem;color:var(--muted);line-height:1.5;">
        <strong>Data Source:</strong><br/>
        <code>tu-data-edw-pr-1.a113_roadside</code><br/>
        (&bull; <code>ncx_pmcs_airf</code><br/>
         &bull; <code>ncx_pmcs_jftvz_03</code><br/>
         &bull; <code>ncx_pmcs_cems</code><br/>
         &bull; <code>ncx_pmcs_vaf</code><br/>
         &bull; <code>ncx_traffic_loops</code><br/>
         &bull; <code>ncx_events</code>)<br/><br/>
        <strong>To sync fresh BigQuery data to GitHub:</strong><br/>
        Run <code>.\\sync_bq_to_github.ps1</code>
      </div>
    </aside>

    <main>
      <div class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-label">30-Min Intervals</div>
          <div class="kpi-value" id="kpi-intervals">-</div>
          <div class="kpi-sub" id="kpi-range-sub">-</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Portal Emissions Alarms</div>
          <div class="kpi-value" id="kpi-alarms" style="color:#f87171;">-</div>
          <div class="kpi-sub" id="kpi-alarms-sub">S2 + S8 + N8 SCADA Events</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Mean S8 / N8 Portal Velocity</div>
          <div class="kpi-value" id="kpi-flow">-</div>
          <div class="kpi-sub">m/s (5-min Rolling Avg Sensor)</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Mean Stack Flow (VS01 / VS04)</div>
          <div class="kpi-value" id="kpi-stack">-</div>
          <div class="kpi-sub">m&sup3;/s CEMS Stack Exhaust</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Ventilation Overdrive Rate</div>
          <div class="kpi-value" id="kpi-overdrive" style="color:#fbbf24;">-</div>
          <div class="kpi-sub">Above OMCS TOD Baseline</div>
        </div>
      </div>

      <div class="chart-card">
        <h4>Portal Air Velocity (`s2_flow5`, `s8_flow5`, `n8_flow5` m/s) &amp; Reversal Threshold (0 m/s)</h4>
        <div id="flow-chart" style="height:320px;"></div>
      </div>

      <div class="chart-card">
        <h4>Ventilation Stack Exhaust (`vs01_stack_flow`, `vs04_stack_flow` m&sup3;/s) &amp; Jet Fan Levels</h4>
        <div id="stack-chart" style="height:290px;"></div>
      </div>

      <div class="chart-card">
        <h4>Forensic SCADA Portal Emissions Alarm Log (`a113_roadside.ncx_events` — AEST)</h4>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Event Time (AEST)</th>
                <th>Registry Name</th>
                <th>Location</th>
                <th>Message Text</th>
                <th>Action</th>
                <th>Priority</th>
              </tr>
            </thead>
            <tbody id="alarms-tbody"></tbody>
          </table>
        </div>
      </div>
    </main>
  </div>

  <script>
    const PAYLOAD = {payload_json};
    const META = PAYLOAD.metadata || {{}};
    const TS = PAYLOAD.timeseries || [];
    const ALARMS = PAYLOAD.alarm_events || [];

    document.getElementById("latest-ts").textContent = META.latest_telemetry_aest || "-";
    document.getElementById("synced-at").textContent = META.synced_at_aest || "-";

    const dirSelect = document.getElementById("direction-select");
    const daysRange = document.getElementById("days-range");
    const daysLabel = document.getElementById("days-label");
    const todFilter = document.getElementById("tod-filter");

    function render() {{
      const dir = dirSelect.value;
      const days = parseInt(daysRange.value, 10);
      daysLabel.textContent = days;
      const tod = todFilter.value;

      const maxTimeStr = TS.length ? TS[TS.length - 1].sydney_time : null;
      let cutoff = null;
      if (maxTimeStr) {{
        cutoff = new Date(maxTimeStr.replace(" ", "T"));
        cutoff.setDate(cutoff.getDate() - days);
      }}

      const rows = TS.filter(r => {{
        if (cutoff) {{
          const dt = new Date(String(r.sydney_time).replace(" ", "T"));
          if (dt < cutoff) return false;
        }}
        if (tod === "DAY" && r.is_night === 1) return false;
        if (tod === "NIGHT" && r.is_night === 0) return false;
        return true;
      }});

      const n = rows.length;
      const s2Alarms = rows.reduce((a, r) => a + (r.s2_alarm_count || 0), 0);
      const s8Alarms = rows.reduce((a, r) => a + (r.s8_alarm_count || 0), 0);
      const n8Alarms = rows.reduce((a, r) => a + (r.n8_alarm_count || 0), 0);
      const totAlarms = s2Alarms + s8Alarms + n8Alarms;

      const avgS8 = n ? (rows.reduce((a, r) => a + (r.s8_flow5 || 0), 0) / n).toFixed(2) : "0.00";
      const avgN8 = n ? (rows.reduce((a, r) => a + (r.n8_flow5 || 0), 0) / n).toFixed(2) : "0.00";
      const avgVS01 = n ? (rows.reduce((a, r) => a + (r.vs01_stack_flow || 0), 0) / n).toFixed(0) : "0";
      const avgVS04 = n ? (rows.reduce((a, r) => a + (r.vs04_stack_flow || 0), 0) / n).toFixed(0) : "0";
      const odRate = n ? ((rows.reduce((a, r) => a + (r.is_vent_overdrive || 0), 0) / n) * 100).toFixed(1) : "0.0";

      document.getElementById("kpi-intervals").textContent = n.toLocaleString();
      document.getElementById("kpi-range-sub").textContent = rows.length
        ? `${{rows[0].date_syd}} to ${{rows[rows.length - 1].date_syd}}`
        : "-";
      document.getElementById("kpi-alarms").textContent = totAlarms.toLocaleString();
      document.getElementById("kpi-alarms-sub").textContent = `S2: ${{s2Alarms}} | S8: ${{s8Alarms}} | N8: ${{n8Alarms}}`;
      document.getElementById("kpi-flow").textContent = `${{avgS8}} / ${{avgN8}} m/s`;
      document.getElementById("kpi-stack").textContent = `${{avgVS01}} / ${{avgVS04}}`;
      document.getElementById("kpi-overdrive").textContent = `${{odRate}}%`;

      const xTimes = rows.map(r => r.sydney_time);
      const flowTraces = [];
      if (dir === "BOTH" || dir === "SB") {{
        flowTraces.push({{
          x: xTimes,
          y: rows.map(r => r.s2_flow5),
          name: "SB Entry Portal S2 (m/s)",
          mode: "lines",
          line: {{ color: "#f59e0b", width: 1.8 }}
        }});
        flowTraces.push({{
          x: xTimes,
          y: rows.map(r => r.s8_flow5),
          name: "SB Exit Portal S8 (m/s)",
          mode: "lines",
          line: {{ color: "#38bdf8", width: 2.0 }}
        }});
      }}
      if (dir === "BOTH" || dir === "NB") {{
        flowTraces.push({{
          x: xTimes,
          y: rows.map(r => r.n8_flow5),
          name: "NB Exit Portal N8 (m/s)",
          mode: "lines",
          line: {{ color: "#22c55e", width: 2.0 }}
        }});
      }}

      Plotly.newPlot("flow-chart", flowTraces, {{
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        font: {{ color: "#cbd5e1" }},
        margin: {{ l: 48, r: 20, t: 10, b: 38 }},
        xaxis: {{ gridcolor: "#1e293b" }},
        yaxis: {{ gridcolor: "#1e293b", title: "Air Velocity (m/s)", zeroline: true, zerolinecolor: "#ef4444", zerolinewidth: 2 }},
        legend: {{ orientation: "h", y: 1.12 }}
      }}, {{ responsive: true, displayModeBar: false }});

      const stackTraces = [];
      if (dir === "BOTH" || dir === "SB") {{
        stackTraces.push({{
          x: xTimes,
          y: rows.map(r => r.vs01_stack_flow),
          name: "VS01 Southbound Stack Flow (m³/s)",
          mode: "lines",
          line: {{ color: "#38bdf8", width: 2 }}
        }});
      }}
      if (dir === "BOTH" || dir === "NB") {{
        stackTraces.push({{
          x: xTimes,
          y: rows.map(r => r.vs04_stack_flow),
          name: "VS04 Northbound Stack Flow (m³/s)",
          mode: "lines",
          line: {{ color: "#a855f7", width: 2 }}
        }});
      }}

      Plotly.newPlot("stack-chart", stackTraces, {{
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        font: {{ color: "#cbd5e1" }},
        margin: {{ l: 48, r: 20, t: 10, b: 38 }},
        xaxis: {{ gridcolor: "#1e293b" }},
        yaxis: {{ gridcolor: "#1e293b", title: "Stack Exhaust (m³/s)" }},
        legend: {{ orientation: "h", y: 1.12 }}
      }}, {{ responsive: true, displayModeBar: false }});

      // Render alarms table
      const tbody = document.getElementById("alarms-tbody");
      const recentAlarms = ALARMS.slice().reverse().slice(0, 150);
      tbody.innerHTML = recentAlarms.map(a => `
        <tr>
          <td>${{a.event_time_syd || ""}}</td>
          <td><code>${{a.registry_name || ""}}</code></td>
          <td>${{a.registry_loc || ""}}</td>
          <td style="color:#fca5a5;">${{a.message_text || ""}}</td>
          <td>${{a.alarm_action || ""}}</td>
          <td>${{a.alarm_priority || ""}}</td>
        </tr>
      `).join("");
    }}

    dirSelect.addEventListener("change", render);
    daysRange.addEventListener("input", render);
    todFilter.addEventListener("change", render);

    document.getElementById("export-csv-btn").addEventListener("click", () => {{
      if (!TS.length) return;
      const headers = Object.keys(TS[0]);
      const csv = [
        headers.join(","),
        ...TS.map(r => headers.map(h => JSON.stringify(r[h] ?? "")).join(","))
      ].join("\\n");
      const blob = new Blob([csv], {{ type: "text/csv" }});
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `ncx_a113_live_telemetry_${{(META.latest_telemetry_aest || "latest").replace(/[: ]/g, "_")}}.csv`;
      a.click();
    }});

    render();
  </script>
</body>
</html>
"""


def build_stlite_html(payload: dict) -> str:
    """Generate a Serverless Streamlit (`@stlite/mountable`) HTML page that runs Streamlit in the browser."""
    payload_json = json.dumps(payload)
    st_code = '''import json
import pandas as pd
import streamlit as st

st.set_page_config(page_title="NCX Portal Emissions (GitHub Pages Stlite)", layout="wide")

with open("live_bq_data.json", "r") as f:
    payload = json.load(f)

meta = payload.get("metadata", {})
ts_df = pd.DataFrame(payload.get("timeseries", []))
ev_df = pd.DataFrame(payload.get("alarm_events", []))

st.title("NCX Tunnel Ventilation & Portal Emission Analytics")
st.caption(
    f"Serverless Python Streamlit running directly in Browser on GitHub Pages | "
    f"Source: `{meta.get('project_id')}.{meta.get('dataset')}` | "
    f"Latest Telemetry: **{meta.get('latest_telemetry_aest')} AEST**"
)

with st.sidebar:
    st.header("Telemetry Controls")
    tod_choice = st.selectbox("Time-of-Day Filter", ["All Hours (24h)", "Daytime (06:00-22:00)", "Night Hygiene (22:00-06:00)"])
    st.success(f"Synced from Live BigQuery:\\n**{meta.get('synced_at_aest')}**")
    st.markdown("[← Back to Fast Plotly View](./index.html)")

if not ts_df.empty:
    if tod_choice == "Daytime (06:00-22:00)":
        ts_df = ts_df[ts_df["is_night"] == 0]
    elif tod_choice == "Night Hygiene (22:00-06:00)":
        ts_df = ts_df[ts_df["is_night"] == 1]

c1, c2, c3, c4 = st.columns(4)
tot_alarms = int(ts_df["s2_alarm_count"].sum() + ts_df["s8_alarm_count"].sum() + ts_df["n8_alarm_count"].sum()) if not ts_df.empty else 0
c1.metric("30-Min Intervals", f"{len(ts_df):,}")
c2.metric("Portal Emissions Alarms", f"{tot_alarms:,}")
c3.metric("Mean S8 / N8 Velocity (m/s)", f"{ts_df['s8_flow5'].mean():.2f} / {ts_df['n8_flow5'].mean():.2f}" if not ts_df.empty else "-")
c4.metric("Latest Telemetry (AEST)", meta.get("latest_telemetry_aest", "-"))

st.subheader("Portal Air Velocity (`s2_flow5`, `s8_flow5`, `n8_flow5` m/s — AEST)")
if not ts_df.empty:
    chart_df = ts_df.set_index("sydney_time")[["s2_flow5", "s8_flow5", "n8_flow5"]]
    st.line_chart(chart_df)

st.subheader("Ventilation Stack Exhaust (`vs01_stack_flow`, `vs04_stack_flow` m³/s)")
if not ts_df.empty:
    stack_df = ts_df.set_index("sydney_time")[["vs01_stack_flow", "vs04_stack_flow"]]
    st.line_chart(stack_df)

st.subheader("Forensic SCADA Portal Emissions Alarm Log (`ncx_events`)")
st.dataframe(ev_df, use_container_width=True)
'''
    return f"""<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8" />
    <meta http-equiv="X-UA-Compatible" content="IE=edge" />
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no" />
    <title>NCX Portal Emissions — Streamlit on GitHub Pages (Stlite)</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@stlite/mountable@0.63.1/build/stlite.css" />
  </head>
  <body>
    <div id="root"></div>
    <script src="https://cdn.jsdelivr.net/npm/@stlite/mountable@0.63.1/build/stlite.js"></script>
    <script>
      stlite.mount(
        {{
          requirements: ["pandas"],
          entrypoint: "streamlit_app.py",
          files: {{
            "streamlit_app.py": {json.dumps(st_code)},
            "live_bq_data.json": {json.dumps(payload_json)}
          }}
        }},
        document.getElementById("root")
      );
    </script>
  </body>
</html>
"""


def main() -> int:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    payload = fetch_live_bq_payload(project_id="tu-data-edw-pr-1", days=14)

    print("[2/3] Writing live BigQuery snapshot & browser-runnable GitHub Pages files...")
    payload_str = json.dumps(payload, indent=2)
    (DOCS_DIR / "live_bq_data.json").write_text(payload_str, encoding="utf-8")

    # Also update the bundled snapshot in src/data so offline/fallback mode has the latest live data
    data_dir = APP_ROOT / "src" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "ncx_expanded_dashboard_payload.json").write_text(payload_str, encoding="utf-8")

    interactive_html = build_interactive_html(payload)
    (DOCS_DIR / "index.html").write_text(interactive_html, encoding="utf-8")
    (APP_ROOT / "index.html").write_text(interactive_html, encoding="utf-8")

    stlite_html = build_stlite_html(payload)
    (DOCS_DIR / "streamlit.html").write_text(stlite_html, encoding="utf-8")
    (APP_ROOT / "streamlit.html").write_text(stlite_html, encoding="utf-8")

    (DOCS_DIR / ".nojekyll").write_text("", encoding="utf-8")
    (APP_ROOT / ".nojekyll").write_text("", encoding="utf-8")

    print("[3/3] Done! Generated:")
    print(f"      - {APP_ROOT / 'index.html'} (Root GitHub Pages Interactive App)")
    print(f"      - {DOCS_DIR / 'index.html'} (/docs GitHub Pages Interactive App)")
    print(f"      - {DOCS_DIR / 'streamlit.html'} (Serverless Python Streamlit via WebAssembly)")
    print(f"      - {DOCS_DIR / 'live_bq_data.json'} (Live BigQuery data snapshot)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
