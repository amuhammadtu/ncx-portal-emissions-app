"""
BigQuery Data Layer, Storage Read API & FinOps Guardrails (`ENG-2081` & `ENG-2083`).

Provides:
- Singleton `@st.cache_resource` BigQuery client (Tier-1 Per-App Service Account ADC
  default; Tier-2 Caller's Rights OAuth token pass-through opt-in).
- Mandatory FinOps `QueryJobConfig` guardrails: `maximum_bytes_billed` (5 GiB cap)
  and attribution labels (`app`, `env`, `cost_centre`, `user_hash`).
- Strict `Australia/Sydney` (AEST/AEDT) timezone conversion for `tu-data-edw-pr-1.a113_roadside`
  per `.agents/skills/a113-telemetry`.
- `@st.cache_data(ttl=600, max_entries=100)` query caching with BigQuery Storage Read API
  (`create_bqstorage_client=True`).
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Load Transurban corporate SSL certificates patch if present in user space
try:
    import pip_system_certs.wrapt_requests  # noqa: F401
except Exception:
    pass

import pandas as pd
import streamlit as st
from google.cloud import bigquery
from google.oauth2 import credentials as oauth2_credentials

from src.telemetry import (
    APP_ENV,
    APP_NAME,
    COST_CENTRE,
    GCP_PROJECT_ID,
    log_structured_event,
    trace_span,
)

# Default 5 GiB per-query safety cap (`ENG-2083`)
DEFAULT_MAX_BYTES_BILLED = int(
    os.environ.get("BQ_MAX_BYTES_BILLED", str(5 * 1024 * 1024 * 1024))
)
BQ_DATASET = os.environ.get("BQ_DATASET", "a113_roadside")

# Candidate paths for the verified 4-week NCX telemetry snapshot
SNAPSHOT_CANDIDATE_PATHS = (
    Path(__file__).resolve().parent / "assets" / "ncx_expanded_dashboard_payload.json",
    Path(__file__).resolve().parent / "data" / "ncx_expanded_dashboard_payload.json",
    Path(r"C:\Users\amuhammad\Documents\AM Agents\NCX Portal Emission Analysis\ncx_expanded_dashboard_payload.json"),
)


def _sanitize_bq_label(value: str) -> str:
    """Sanitize a string to comply with BigQuery label rules: lowercase `[a-z0-9_-]`, <=63 chars."""
    cleaned = re.sub(r"[^a-z0-9_-]", "-", (value or "unknown").strip().lower())
    return cleaned[:63] or "unknown"


@st.cache_resource(show_spinner=False)
def get_bq_client(project_id: str = GCP_PROJECT_ID) -> bigquery.Client:
    """
    Return a singleton BigQuery client using Tier-1 Per-App Service Account ADC (`ENG-2080`).
    """
    return bigquery.Client(project=project_id)


def get_caller_rights_bq_client(
    access_token: str,
    project_id: str = GCP_PROJECT_ID,
) -> bigquery.Client:
    """
    Return a Tier-2 Caller's Rights BigQuery client authenticated with the end-user's
    Workforce Identity Federation OAuth access token (`ENG-2080` Tier-2 Pattern).
    """
    user_creds = oauth2_credentials.Credentials(token=access_token)
    return bigquery.Client(project=project_id, credentials=user_creds)


def build_finops_job_config(
    *,
    user_hash: str = "anonymous",
    max_bytes_billed: int = DEFAULT_MAX_BYTES_BILLED,
    app_name: str = APP_NAME,
    env: str = APP_ENV,
    cost_centre: str = COST_CENTRE,
) -> bigquery.QueryJobConfig:
    """
    Construct a BigQuery `QueryJobConfig` enforcing SEAL FinOps guardrails (`ENG-2083`):
    1. `maximum_bytes_billed` hard ceiling to block runaway full-table scans.
    2. Mandatory `labels` (`app`, `env`, `cost_centre`, `user_hash`) for `INFORMATION_SCHEMA.JOBS`
       cost attribution per dashboard and user.
    """
    labels = {
        "app": _sanitize_bq_label(app_name),
        "env": _sanitize_bq_label(env),
        "cost_centre": _sanitize_bq_label(cost_centre),
        "user_hash": _sanitize_bq_label(user_hash),
    }
    return bigquery.QueryJobConfig(
        maximum_bytes_billed=int(max_bytes_billed),
        labels=labels,
        use_query_cache=True,
    )


def get_tod_baseline(dt: datetime) -> tuple[int, int]:
    """
    Compute OMCS Time-of-Day (TOD) baseline ventilation setpoints according to
    Functional Specification `NCX-MEA-01-2516-CS-SP-0001_16`:
    - Table 30-14 (Table J-19): Northbound Time of Day Table (Levels 1-4)
    - Table 30-15 (Table J-20): Southbound Time of Day Table (Levels 1-5)
    """
    is_weekend = dt.weekday() >= 5  # Saturday=5, Sunday=6
    hr = dt.hour

    if not is_weekend:
        # Weekday (Mon-Fri) - Northbound Table 30-14
        if hr in (0, 1, 2):
            nb_base = 1
        elif hr == 3:
            nb_base = 2
        elif hr == 4:
            nb_base = 3
        elif hr in (5, 6):
            nb_base = 4
        elif hr == 7:
            nb_base = 3
        elif 8 <= hr <= 18:
            nb_base = 4
        elif hr in (19, 20):
            nb_base = 3
        else:
            nb_base = 2

        # Weekday (Mon-Fri) - Southbound Table 30-15
        if 0 <= hr <= 3:
            sb_base = 2
        elif hr in (4, 5):
            sb_base = 3
        elif 6 <= hr <= 8:
            sb_base = 4
        elif 9 <= hr <= 16:
            sb_base = 5
        elif hr == 17:
            sb_base = 4
        elif 18 <= hr <= 21:
            sb_base = 3
        else:
            sb_base = 2
    else:
        # Weekend (Sat-Sun) - Northbound Table 30-14
        if 0 <= hr <= 3:
            nb_base = 1
        elif hr == 4:
            nb_base = 2
        elif hr in (5, 6):
            nb_base = 3
        elif hr == 7:
            nb_base = 2
        elif 8 <= hr <= 18:
            nb_base = 3
        elif hr in (19, 20):
            nb_base = 2
        else:
            nb_base = 1

        # Weekend (Sat-Sun) - Southbound Table 30-15
        if 0 <= hr <= 3:
            sb_base = 1
        elif hr in (4, 5):
            sb_base = 2
        elif 6 <= hr <= 8:
            sb_base = 3
        elif 9 <= hr <= 16:
            sb_base = 4
        elif hr == 17:
            sb_base = 3
        elif 18 <= hr <= 21:
            sb_base = 2
        else:
            sb_base = 1

    return nb_base, sb_base


def _validate_date_iso(date_str: str) -> str:
    """Validate YYYY-MM-DD date string to prevent SQL injection."""
    cleaned = str(date_str).strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", cleaned):
        raise ValueError(f"Invalid ISO date string '{date_str}'. Expected YYYY-MM-DD.")
    datetime.strptime(cleaned, "%Y-%m-%d")
    return cleaned


def build_ncx_timeseries_sql(
    start_date: str,
    end_date: str,
    project_id: str = GCP_PROJECT_ID,
    dataset: str = BQ_DATASET,
) -> str:
    """
    Build the 30-minute interval CTE query across `a113_roadside` (`ncx_traffic_loops`,
    `ncx_pmcs_airf`, `ncx_pmcs_jftvz_03`, `ncx_pmcs_cems`, `ncx_pmcs_vaf`, `ncx_events`).
    Enforces UTC-to-AEST conversion (`DATETIME(..., 'Australia/Sydney')`) per `a113-telemetry`.
    """
    s_date = _validate_date_iso(start_date)
    e_date = _validate_date_iso(end_date)
    start_utc = f"{s_date} 00:00:00 UTC"
    end_utc = f"{e_date} 00:00:00 UTC"
    fq_dataset = f"{project_id}.{dataset}"

    return f"""
    WITH time_windows AS (
      SELECT TIMESTAMP_SECONDS(DIV(UNIX_SECONDS(record_tstamp), 1800) * 1800) AS window_start_utc
      FROM UNNEST(GENERATE_TIMESTAMP_ARRAY('{start_utc}', '{end_utc}', INTERVAL 30 MINUTE)) AS record_tstamp
    ),
    traffic AS (
      SELECT
        TIMESTAMP_SECONDS(DIV(UNIX_SECONDS(record_tstamp), 1800) * 1800) AS window_start_utc,
        SUM(CASE WHEN registry_name IN ('$NCX://detectors/TLP0131A', '$NCX://detectors/TLP0132A', '$NCX://detectors/TLP9241A') THEN zone_datavolume ELSE 0 END) AS nb_vol,
        AVG(CASE WHEN registry_name IN ('$NCX://detectors/TLP0131A', '$NCX://detectors/TLP0132A', '$NCX://detectors/TLP9241A') THEN zone_dataspeed ELSE NULL END) AS nb_speed_kmh,
        SUM(CASE WHEN registry_name IN ('$NCX://detectors/TLP0231A', '$NCX://detectors/TLP0232A', '$NCX://detectors/TLP9141A') THEN zone_datavolume ELSE 0 END) AS sb_vol,
        AVG(CASE WHEN registry_name IN ('$NCX://detectors/TLP0231A', '$NCX://detectors/TLP0232A', '$NCX://detectors/TLP9141A') THEN zone_dataspeed ELSE NULL END) AS sb_speed_kmh
      FROM `{fq_dataset}.ncx_traffic_loops`
      WHERE record_tstamp BETWEEN '{start_utc}' AND '{end_utc}'
        AND registry_name IN (
          '$NCX://detectors/TLP0131A', '$NCX://detectors/TLP0132A', '$NCX://detectors/TLP9241A',
          '$NCX://detectors/TLP0231A', '$NCX://detectors/TLP0232A', '$NCX://detectors/TLP9141A'
        )
      GROUP BY window_start_utc
    ),
    airf AS (
      SELECT
        TIMESTAMP_SECONDS(DIV(UNIX_SECONDS(record_tstamp), 1800) * 1800) AS window_start_utc,
        AVG(air_flow3_s1) AS s1_flow,
        AVG(air_flow3_s2) AS s2_flow,
        AVG(air_flow3_s3) AS s3_flow,
        AVG(air_flow3_s4) AS s4_flow,
        AVG(air_flow3_s5) AS s5_flow,
        AVG(air_flow3_s6) AS s6_flow,
        AVG(air_flow3_s7) AS s7_flow,
        AVG(air_flow3_s8) AS s8_flow,
        AVG(air_flow5_s2) AS s2_flow5,
        AVG(air_flow5_s8) AS s8_flow5,
        AVG(air_flow3_n1) AS n1_flow,
        AVG(air_flow3_n2) AS n2_flow,
        AVG(air_flow3_n3) AS n3_flow,
        AVG(air_flow3_n4) AS n4_flow,
        AVG(air_flow3_n5) AS n5_flow,
        AVG(air_flow3_n6) AS n6_flow,
        AVG(air_flow3_n7) AS n7_flow,
        AVG(air_flow3_n8) AS n8_flow,
        AVG(air_flow5_n2) AS n2_flow5,
        AVG(air_flow5_n8) AS n8_flow5
      FROM `{fq_dataset}.ncx_pmcs_airf`
      WHERE record_tstamp BETWEEN '{start_utc}' AND '{end_utc}'
      GROUP BY window_start_utc
    ),
    fans AS (
      SELECT
        TIMESTAMP_SECONDS(DIV(UNIX_SECONDS(record_tstamp), 1800) * 1800) AS window_start_utc,
        AVG(CASE WHEN registry_name = '$NCX://pmcs/ctrJFTVZ203' THEN number_of_units_running_forward END) AS sb_fans_fwd,
        AVG(CASE WHEN registry_name = '$NCX://pmcs/ctrJFTVZ203' THEN number_of_units_run_forward_available END) AS sb_fans_avail,
        AVG(CASE WHEN registry_name = '$NCX://pmcs/ctrJFTVZ203' THEN flow_process_value END) AS sb_flow_pv,
        AVG(CASE WHEN registry_name = '$NCX://pmcs/ctrJFTVZ203' THEN flow_setpoint END) AS sb_flow_sp,
        MAX(CASE WHEN registry_name = '$NCX://pmcs/ctrJFTVZ203' THEN ventilation_level END) AS sb_vent_level,
        AVG(CASE WHEN registry_name = '$NCX://pmcs/ctrJFTVZ103' THEN number_of_units_running_forward END) AS nb_fans_fwd,
        AVG(CASE WHEN registry_name = '$NCX://pmcs/ctrJFTVZ103' THEN number_of_units_run_forward_available END) AS nb_fans_avail,
        AVG(CASE WHEN registry_name = '$NCX://pmcs/ctrJFTVZ103' THEN flow_process_value END) AS nb_flow_pv,
        AVG(CASE WHEN registry_name = '$NCX://pmcs/ctrJFTVZ103' THEN flow_setpoint END) AS nb_flow_sp,
        MAX(CASE WHEN registry_name = '$NCX://pmcs/ctrJFTVZ103' THEN ventilation_level END) AS nb_vent_level
      FROM `{fq_dataset}.ncx_pmcs_jftvz_03`
      WHERE record_tstamp BETWEEN '{start_utc}' AND '{end_utc}'
      GROUP BY window_start_utc
    ),
    cems AS (
      SELECT
        TIMESTAMP_SECONDS(DIV(UNIX_SECONDS(record_tstamp), 1800) * 1800) AS window_start_utc,
        AVG(CASE WHEN registry_name = '$NCX://pmcs/CEMS_VS01' THEN air_flow END) AS vs01_stack_flow,
        AVG(CASE WHEN registry_name = '$NCX://pmcs/CEMS_VS01' THEN air_velocity END) AS vs01_stack_vel,
        AVG(CASE WHEN registry_name = '$NCX://pmcs/CEMS_VS04' THEN air_flow END) AS vs04_stack_flow,
        AVG(CASE WHEN registry_name = '$NCX://pmcs/CEMS_VS04' THEN air_velocity END) AS vs04_stack_vel
      FROM `{fq_dataset}.ncx_pmcs_cems`
      WHERE record_tstamp BETWEEN '{start_utc}' AND '{end_utc}'
      GROUP BY window_start_utc
    ),
    vaf AS (
      SELECT
        TIMESTAMP_SECONDS(DIV(UNIX_SECONDS(record_tstamp), 1800) * 1800) AS window_start_utc,
        ROUND(AVG(CASE WHEN registry_name IN ('$NCX://pmcs/VAF011', '$NCX://pmcs/VAF012', '$NCX://pmcs/VAF013', '$NCX://pmcs/VAF014', '$NCX://pmcs/VAF015') AND (current_380 > 10.0 OR v_s_d_speed_feedback2 > 30.0) THEN 1 ELSE 0 END) * 5, 1) AS vs01_fans_running,
        ROUND(AVG(CASE WHEN registry_name IN ('$NCX://pmcs/VAF071', '$NCX://pmcs/VAF072', '$NCX://pmcs/VAF073', '$NCX://pmcs/VAF074', '$NCX://pmcs/VAF075') AND (current_380 > 10.0 OR v_s_d_speed_feedback2 > 30.0) THEN 1 ELSE 0 END) * 5, 1) AS vs04_fans_running
      FROM `{fq_dataset}.ncx_pmcs_vaf`
      WHERE record_tstamp BETWEEN '{start_utc}' AND '{end_utc}'
        AND registry_name IN (
          '$NCX://pmcs/VAF011', '$NCX://pmcs/VAF012', '$NCX://pmcs/VAF013', '$NCX://pmcs/VAF014', '$NCX://pmcs/VAF015',
          '$NCX://pmcs/VAF071', '$NCX://pmcs/VAF072', '$NCX://pmcs/VAF073', '$NCX://pmcs/VAF074', '$NCX://pmcs/VAF075'
        )
      GROUP BY window_start_utc
    ),
    alarms AS (
      SELECT
        TIMESTAMP_SECONDS(DIV(UNIX_SECONDS(event_ts), 1800) * 1800) AS window_start_utc,
        COUNT(CASE WHEN message_text LIKE '%Section S2 Portal Emissions%' THEN 1 END) AS s2_alarm_count,
        COUNT(CASE WHEN message_text LIKE '%Section S8 Portal Emissions%' THEN 1 END) AS s8_alarm_count,
        COUNT(CASE WHEN message_text LIKE '%Section N8 Portal Emissions%' THEN 1 END) AS n8_alarm_count
      FROM `{fq_dataset}.ncx_events`
      WHERE event_ts BETWEEN '{start_utc}' AND '{end_utc}'
        AND message_text LIKE '%Portal Emissions%'
      GROUP BY window_start_utc
    )
    SELECT
      t.window_start_utc,
      FORMAT_DATETIME('%Y-%m-%d %H:%M', DATETIME(t.window_start_utc, 'Australia/Sydney')) AS sydney_time,
      FORMAT_DATETIME('%Y-%m-%d', DATETIME(t.window_start_utc, 'Australia/Sydney')) AS date_syd,
      FORMAT_DATETIME('%H:%M', DATETIME(t.window_start_utc, 'Australia/Sydney')) AS time_syd,
      EXTRACT(HOUR FROM DATETIME(t.window_start_utc, 'Australia/Sydney')) AS hour_syd,
      EXTRACT(DAYOFWEEK FROM DATETIME(t.window_start_utc, 'Australia/Sydney')) AS dow_syd,
      CASE WHEN EXTRACT(HOUR FROM DATETIME(t.window_start_utc, 'Australia/Sydney')) IN (22, 23, 0, 1, 2, 3, 4, 5) THEN 1 ELSE 0 END AS is_night,
      COALESCE(tr.nb_vol, 0) AS nb_traffic_vol,
      COALESCE(tr.sb_vol, 0) AS sb_traffic_vol,
      COALESCE(tr.nb_vol, 0) + COALESCE(tr.sb_vol, 0) AS total_traffic_vol,
      ROUND(COALESCE(tr.nb_speed_kmh, 0), 1) AS nb_speed_kmh,
      ROUND(COALESCE(tr.sb_speed_kmh, 0), 1) AS sb_speed_kmh,
      ROUND(COALESCE(a.s1_flow, 0), 1) AS s1_flow,
      ROUND(COALESCE(a.s2_flow, 0), 1) AS s2_flow,
      ROUND(COALESCE(a.s3_flow, 0), 1) AS s3_flow,
      ROUND(COALESCE(a.s4_flow, 0), 1) AS s4_flow,
      ROUND(COALESCE(a.s5_flow, 0), 1) AS s5_flow,
      ROUND(COALESCE(a.s6_flow, 0), 1) AS s6_flow,
      ROUND(COALESCE(a.s7_flow, 0), 1) AS s7_flow,
      ROUND(COALESCE(a.s8_flow, 0), 1) AS s8_flow,
      ROUND(COALESCE(a.s2_flow5, 0), 1) AS s2_flow5,
      ROUND(COALESCE(a.s8_flow5, 0), 1) AS s8_flow5,
      ROUND(COALESCE(a.n1_flow, 0), 1) AS n1_flow,
      ROUND(COALESCE(a.n2_flow, 0), 1) AS n2_flow,
      ROUND(COALESCE(a.n3_flow, 0), 1) AS n3_flow,
      ROUND(COALESCE(a.n4_flow, 0), 1) AS n4_flow,
      ROUND(COALESCE(a.n5_flow, 0), 1) AS n5_flow,
      ROUND(COALESCE(a.n6_flow, 0), 1) AS n6_flow,
      ROUND(COALESCE(a.n7_flow, 0), 1) AS n7_flow,
      ROUND(COALESCE(a.n8_flow, 0), 1) AS n8_flow,
      ROUND(COALESCE(a.n2_flow5, 0), 1) AS n2_flow5,
      ROUND(COALESCE(a.n8_flow5, 0), 1) AS n8_flow5,
      ROUND(COALESCE(f.sb_flow_pv, 0), 1) AS sb_flow_pv,
      ROUND(COALESCE(f.sb_flow_sp, 0), 1) AS sb_flow_sp,
      ROUND(COALESCE(f.sb_fans_fwd, 0), 1) AS sb_fans_running,
      ROUND(COALESCE(f.sb_fans_avail, 0), 1) AS sb_fans_avail,
      COALESCE(f.sb_vent_level, 0) AS sb_vent_level,
      ROUND(COALESCE(f.nb_flow_pv, 0), 1) AS nb_flow_pv,
      ROUND(COALESCE(f.nb_flow_sp, 0), 1) AS nb_flow_sp,
      ROUND(COALESCE(f.nb_fans_fwd, 0), 1) AS nb_fans_running,
      ROUND(COALESCE(f.nb_fans_avail, 0), 1) AS nb_fans_avail,
      COALESCE(f.nb_vent_level, 0) AS nb_vent_level,
      ROUND(COALESCE(c.vs01_stack_flow, 0), 1) AS vs01_stack_flow,
      ROUND(COALESCE(c.vs01_stack_vel, 0), 1) AS vs01_stack_vel,
      COALESCE(v.vs01_fans_running, 0) AS vs01_fans_running,
      ROUND(COALESCE(c.vs04_stack_flow, 0), 1) AS vs04_stack_flow,
      ROUND(COALESCE(c.vs04_stack_vel, 0), 1) AS vs04_stack_vel,
      COALESCE(v.vs04_fans_running, 0) AS vs04_fans_running,
      COALESCE(al.s2_alarm_count, 0) AS s2_alarm_count,
      COALESCE(al.s8_alarm_count, 0) AS s8_alarm_count,
      COALESCE(al.n8_alarm_count, 0) AS n8_alarm_count
    FROM time_windows t
    LEFT JOIN traffic tr ON t.window_start_utc = tr.window_start_utc
    LEFT JOIN airf a ON t.window_start_utc = a.window_start_utc
    LEFT JOIN fans f ON t.window_start_utc = f.window_start_utc
    LEFT JOIN cems c ON t.window_start_utc = c.window_start_utc
    LEFT JOIN vaf v ON t.window_start_utc = v.window_start_utc
    LEFT JOIN alarms al ON t.window_start_utc = al.window_start_utc
    ORDER BY t.window_start_utc ASC;
    """


def build_ncx_events_sql(
    start_date: str,
    end_date: str,
    project_id: str = GCP_PROJECT_ID,
    dataset: str = BQ_DATASET,
) -> str:
    """
    Build the forensic SCADA Portal Emissions alarm event log query across `a113_roadside.ncx_events`.
    Enforces UTC-to-AEST conversion (`DATETIME(event_ts, 'Australia/Sydney')`) per `a113-telemetry`.
    """
    s_date = _validate_date_iso(start_date)
    e_date = _validate_date_iso(end_date)
    start_utc = f"{s_date} 00:00:00 UTC"
    end_utc = f"{e_date} 00:00:00 UTC"
    fq_dataset = f"{project_id}.{dataset}"

    return f"""
    SELECT
      FORMAT_DATETIME('%Y-%m-%d %H:%M:%S', DATETIME(event_ts, 'Australia/Sydney')) AS event_time_syd,
      event_id,
      registry_name,
      registry_desc,
      registry_loc,
      message_text,
      alarm_action,
      alarm_class,
      alarm_priority
    FROM `{fq_dataset}.ncx_events`
    WHERE event_ts BETWEEN '{start_utc}' AND '{end_utc}'
      AND message_text LIKE '%Portal Emissions%'
    ORDER BY event_ts ASC;
    """


def _execute_query_to_df(
    client: bigquery.Client,
    sql: str,
    job_config: bigquery.QueryJobConfig,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Execute a BigQuery query with `create_bqstorage_client=True` (Storage Read API)
    and return `(dataframe, job_stats)`.
    """
    t0 = time.perf_counter()
    query_job = client.query(sql, job_config=job_config)
    try:
        df = query_job.to_dataframe(create_bqstorage_client=True)
        used_storage_api = True
    except Exception:
        df = query_job.to_dataframe(create_bqstorage_client=False)
        used_storage_api = False

    duration_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    stats = {
        "bq_job_id": query_job.job_id,
        "bytes_billed": int(query_job.total_bytes_billed or 0),
        "bytes_processed": int(query_job.total_bytes_processed or 0),
        "cache_hit": bool(query_job.cache_hit),
        "duration_ms": duration_ms,
        "storage_read_api": used_storage_api,
    }
    return df, stats


@st.cache_data(ttl=600, max_entries=100, show_spinner=False)
def fetch_ncx_telemetry_from_bq(
    start_date: str,
    end_date: str,
    user_hash: str = "anonymous",
    access_token: str | None = None,
) -> dict[str, Any]:
    """
    Execute live BigQuery queries against `tu-data-edw-pr-1.a113_roadside` with FinOps
    guardrails (`maximum_bytes_billed`, attribution labels, 10-minute TTL cache, Storage Read API).
    """
    credential_tier = os.environ.get("BQ_CREDENTIAL_TIER", "service_account").strip().lower()
    if credential_tier == "caller_rights" and access_token:
        client = get_caller_rights_bq_client(access_token)
    else:
        client = get_bq_client()

    job_config = build_finops_job_config(user_hash=user_hash)
    sql_ts = build_ncx_timeseries_sql(start_date, end_date)
    sql_ev = build_ncx_events_sql(start_date, end_date)

    with trace_span(
        "bq.fetch_ncx_expanded_telemetry",
        user_hash=user_hash,
        attributes={"start_date": start_date, "end_date": end_date},
    ) as span_ctx:
        df_ts, stats_ts = _execute_query_to_df(client, sql_ts, job_config)
        df_ev, stats_ev = _execute_query_to_df(client, sql_ev, job_config)

        # Enrich timeseries with OMCS Time-of-Day (TOD) Baseline Setpoints
        nb_baselines: list[int] = []
        sb_baselines: list[int] = []
        overdrive_flags: list[int] = []

        for _, row in df_ts.iterrows():
            dt_syd = datetime.strptime(str(row["sydney_time"]), "%Y-%m-%d %H:%M")
            nb_base, sb_base = get_tod_baseline(dt_syd)
            nb_baselines.append(nb_base)
            sb_baselines.append(sb_base)
            is_od = 1 if (row["nb_vent_level"] > nb_base or row["sb_vent_level"] > sb_base) else 0
            overdrive_flags.append(is_od)

        df_ts["nb_tod_baseline"] = nb_baselines
        df_ts["sb_tod_baseline"] = sb_baselines
        df_ts["is_vent_overdrive"] = overdrive_flags

        total_bytes_billed = stats_ts["bytes_billed"] + stats_ev["bytes_billed"]
        total_duration_ms = round(stats_ts["duration_ms"] + stats_ev["duration_ms"], 2)
        combined_job_id = f"{stats_ts['bq_job_id']},{stats_ev['bq_job_id']}"
        both_cache_hit = bool(stats_ts["cache_hit"] and stats_ev["cache_hit"])

        span_ctx["bq_job_id"] = combined_job_id
        span_ctx["bytes_billed"] = total_bytes_billed
        span_ctx["cache_hit"] = both_cache_hit

    return {
        "metadata": {
            "title": "NorthConnex Tunnel Ventilation & Portal Emission Trend Model (Live BigQuery)",
            "source_mode": "live_bigquery",
            "time_range_utc": f"{start_date} 00:00:00 UTC to {end_date} 00:00:00 UTC",
            "start_date": start_date,
            "end_date": end_date,
            "interval_minutes": 30,
            "total_intervals": len(df_ts),
            "total_alarms": len(df_ev),
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "finops": {
                "bq_job_ids": [stats_ts["bq_job_id"], stats_ev["bq_job_id"]],
                "bytes_billed": total_bytes_billed,
                "bytes_processed": stats_ts["bytes_processed"] + stats_ev["bytes_processed"],
                "max_bytes_billed_cap": DEFAULT_MAX_BYTES_BILLED,
                "cache_hit": both_cache_hit,
                "duration_ms": total_duration_ms,
                "storage_read_api": stats_ts["storage_read_api"],
                "labels": dict(job_config.labels),
            },
        },
        "timeseries": json.loads(df_ts.to_json(orient="records")),
        "alarm_events": json.loads(df_ev.to_json(orient="records")),
    }


@st.cache_data(ttl=3600, show_spinner=False)
def load_cached_4week_snapshot(
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """
    Load the pre-verified 4-week NCX dataset (`ncx_expanded_dashboard_payload.json`)
    for instant zero-cost exploration and offline / CI `AppTest` execution.
    Optionally filters by `[start_date, end_date]`.
    """
    for candidate in SNAPSHOT_CANDIDATE_PATHS:
        if candidate.exists():
            raw = json.loads(candidate.read_text(encoding="utf-8"))
            ts = raw.get("timeseries", [])
            ev = raw.get("alarm_events", raw.get("events", []))
            if start_date and end_date:
                ts_filtered = [
                    r for r in ts if start_date <= str(r.get("date_syd", "")) <= end_date
                ]
                ev_filtered = [
                    e
                    for e in ev
                    if start_date <= str(e.get("event_time_syd", ""))[:10] <= end_date
                ]
                if ts_filtered:
                    ts = ts_filtered
                    ev = ev_filtered

            meta = dict(raw.get("metadata", {}))
            meta.update(
                {
                    "source_mode": "cached_snapshot",
                    "start_date": start_date or "2026-09-22",
                    "end_date": end_date or "2026-10-20",
                    "total_intervals": len(ts),
                    "total_alarms": len(ev),
                    "finops": {
                        "bq_job_ids": ["snapshot-cache-hit"],
                        "bytes_billed": 0,
                        "bytes_processed": 0,
                        "max_bytes_billed_cap": DEFAULT_MAX_BYTES_BILLED,
                        "cache_hit": True,
                        "duration_ms": 1.2,
                        "storage_read_api": True,
                        "labels": {
                            "app": APP_NAME,
                            "env": APP_ENV,
                            "cost_centre": COST_CENTRE,
                        },
                    },
                }
            )
            return {
                "metadata": meta,
                "timeseries": ts,
                "alarm_events": ev,
            }

    raise FileNotFoundError(
        f"NCX snapshot payload not found in any candidate path: {SNAPSHOT_CANDIDATE_PATHS}"
    )


def get_ncx_dashboard_payload(
    *,
    mode: str = "cached_snapshot",
    start_date: str = "2026-09-22",
    end_date: str = "2026-10-20",
    user_hash: str = "anonymous",
    access_token: str | None = None,
) -> dict[str, Any]:
    """
    Unified data loader supporting both `"live_bigquery"` (with automatic graceful fallback
    to snapshot if offline) and `"cached_snapshot"`.
    """
    if mode == "live_bigquery":
        try:
            return fetch_ncx_telemetry_from_bq(
                start_date=start_date,
                end_date=end_date,
                user_hash=user_hash,
                access_token=access_token,
            )
        except Exception as exc:
            log_structured_event(
                f"Live BigQuery query failed ({exc}); falling back to verified 4-week snapshot.",
                severity="WARNING",
                user_hash=user_hash,
                extra={"fallback": "cached_snapshot", "error": str(exc)},
            )
            payload = load_cached_4week_snapshot(start_date=start_date, end_date=end_date)
            payload["metadata"]["source_mode"] = "cached_snapshot_fallback"
            payload["metadata"]["fallback_reason"] = str(exc)
            return payload

    return load_cached_4week_snapshot(start_date=start_date, end_date=end_date)
