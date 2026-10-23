"""Integration, Streamlit AppTest & FinOps Governance Tests (`ENG-2081` - `ENG-2085`).

Compatible with both `python -m unittest discover -s tests -v` and `pytest`.
"""

from __future__ import annotations

from datetime import datetime
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from src.agent_sidekick import compute_telemetry_summary, generate_engineering_response
from src.bq import (
    DEFAULT_MAX_BYTES_BILLED,
    build_finops_job_config,
    build_ncx_events_sql,
    build_ncx_timeseries_sql,
    get_tod_baseline,
    load_cached_4week_snapshot,
)
from src.telemetry import compute_user_hash, trace_span
from src.template_engine import render_dashboard_html


class TestGoldenPathGovernanceAndApp(unittest.TestCase):
    """Test suite for ENG-2081, ENG-2083, ENG-2084, and ENG-2085."""

    def test_finops_governed_job_config_enforces_5gib_cap_and_labels(self) -> None:
        """ENG-2083: QueryJobConfig must enforce 5 GiB maximum_bytes_billed and FinOps labels."""
        u_hash = compute_user_hash("amuhammad@transurban.com")
        cfg = build_finops_job_config(user_hash=u_hash)
        self.assertEqual(cfg.maximum_bytes_billed, DEFAULT_MAX_BYTES_BILLED)
        self.assertEqual(cfg.maximum_bytes_billed, 5 * 1024 * 1024 * 1024)
        self.assertEqual(cfg.labels["app"], "ncx-portal-emissions")
        self.assertEqual(cfg.labels["user_hash"], u_hash)

    def test_ncx_sql_enforces_australia_sydney_timezone(self) -> None:
        """a113-telemetry skill: SQL queries must convert UTC timestamps to Australia/Sydney."""
        sql_ts = build_ncx_timeseries_sql("2026-09-22", "2026-10-20")
        sql_ev = build_ncx_events_sql("2026-09-22", "2026-10-20")
        self.assertIn("tu-data-edw-pr-1.a113_roadside", sql_ts)
        self.assertIn("Australia/Sydney", sql_ts)
        self.assertIn("Australia/Sydney", sql_ev)

    def test_omcs_tod_baseline_matches_spec(self) -> None:
        """Verify OMCS Table 30-14 / 30-15 Time-of-Day baseline level lookup."""
        # Weekday 00:00 -> NB=1, SB=2
        self.assertEqual(get_tod_baseline(datetime(2026, 9, 22, 0, 0)), (1, 2))
        # Weekday 10:00 -> NB=4, SB=5
        self.assertEqual(get_tod_baseline(datetime(2026, 9, 22, 10, 0)), (4, 5))
        # Weekday 19:00 -> NB=3, SB=3
        self.assertEqual(get_tod_baseline(datetime(2026, 9, 22, 19, 0)), (3, 3))

    def test_snapshot_loader_and_html_template_injection(self) -> None:
        """ENG-2081: Verify 4-week snapshot loads and injects cleanly into the HTML/SVG template."""
        payload = load_cached_4week_snapshot()
        self.assertEqual(len(payload["timeseries"]), 1345)
        self.assertEqual(len(payload["alarm_events"]), 938)
        self.assertEqual(payload["metadata"]["finops"]["bytes_billed"], 0)

        compiled_html = render_dashboard_html(payload)
        self.assertIn("const RAW_TIMESERIES = [", compiled_html)
        self.assertIn("const RAW_EVENTS = [", compiled_html)
        self.assertIn("2026-10-16 23:00", compiled_html)

    def test_agent_sidekick_rca_and_agentspace_card(self) -> None:
        """ENG-2085: Verify ADK sidekick RCA synthesis and .well-known/agent.json validity."""
        payload = load_cached_4week_snapshot()
        summary = compute_telemetry_summary(payload)
        self.assertEqual(summary["windows"], 1345)
        self.assertEqual(summary["s2_alarms"], 339)

        resp_2k = generate_engineering_response("Explain TQ158 Rule 2k asymmetry on S6 vs S2", summary)
        self.assertIn("TQ158", resp_2k)
        self.assertIn("S6", resp_2k)

        resp_test = generate_engineering_response("What happened during the Oct 16 Level 3 test?", summary)
        self.assertIn("2026-10-16 23:00", resp_test)

        agent_card_path = Path(__file__).resolve().parent.parent / ".well-known" / "agent.json"
        card = json.loads(agent_card_path.read_text(encoding="utf-8"))
        self.assertEqual(card["protocol"], "A2A")
        self.assertTrue(card["authentication"]["workforcePool"].endswith("agentspace-entra-id-p-oidc-exnat"))

    def test_structured_cloud_logging_and_otel_span(self) -> None:
        """ENG-2084: Verify structured JSON logging and trace_span context manager."""
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            with trace_span("test_bq_span", user_hash="abc123456789") as meta:
                meta["bq_job_id"] = "job_123"
                meta["bytes_billed"] = 1024
        captured = buf.getvalue().strip()
        record = json.loads(captured)
        self.assertEqual(record["span_name"], "test_bq_span")
        self.assertEqual(record["bq_job_id"], "job_123")
        self.assertEqual(record["bytes_billed"], 1024)

    def test_streamlit_apptest_renders_without_exception(self) -> None:
        """ENG-2081 & ENG-2082: Headless Streamlit AppTest execution."""
        app_path = str(Path(__file__).resolve().parent.parent / "src" / "app.py")
        with patch.dict(os.environ, {"ALLOW_LOCAL_DEV_AUTH": "true"}, clear=False):
            at = AppTest.from_file(app_path, default_timeout=30)
            at.run()
            self.assertEqual(len(at.exception), 0, f"AppTest raised exception: {at.exception}")


if __name__ == "__main__":
    unittest.main()
