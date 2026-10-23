"""HTML/SVG/Chart.js Template Injection Engine for NCX Portal Emission Dashboard.

Loads the verified zero-CDN interactive NCX Portal Emission Dashboard HTML template
(with embedded Chart.js, Hammer.js, chartjs-plugin-zoom, and interactive 16-zone
SVG schematic + 60fps time-scrubber) and dynamically injects live BigQuery or
cached snapshot telemetry payloads (`RAW_TIMESERIES`, `RAW_EVENTS`, `METADATA`).
"""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
from typing import Any

DEFAULT_TEMPLATE_PATHS = [
    Path(__file__).resolve().parent / "assets" / "ncx_portal_emission_dashboard.html",
    Path(r"C:\Users\amuhammad\Documents\AM Agents\NCX Portal Emission Analysis\ncx_portal_emission_dashboard.html"),
]


@lru_cache(maxsize=2)
def load_base_html_template(template_path: str | None = None) -> str:
    """Read and cache the base standalone HTML template from disk."""
    candidates = [Path(template_path)] if template_path else DEFAULT_TEMPLATE_PATHS
    for path in candidates:
        if path.exists():
            return path.read_text(encoding="utf-8")
    raise FileNotFoundError(
        f"NCX HTML template not found in any candidate path: {[str(p) for p in candidates]}"
    )


def render_dashboard_html(
    payload: dict[str, Any],
    template_path: str | None = None,
) -> str:
    """Inject live or snapshot telemetry into the interactive HTML/JS/SVG template.

    Replaces `RAW_TIMESERIES`, `RAW_EVENTS`, and `METADATA` in-memory and adapts
    date-range inputs and time-scrubber bounds so custom BigQuery windows render
    cleanly without breaking 60fps client-side scrubbing.
    """
    base_html = load_base_html_template(template_path)

    timeseries = payload.get("timeseries", [])
    events = payload.get("alarm_events", payload.get("events", []))
    metadata = payload.get("metadata", {})

    if timeseries:
        min_date = str(timeseries[0].get("date_syd", "2026-09-22"))
        max_date = str(timeseries[-1].get("date_syd", "2026-10-20"))
        default_step = next(
            (
                idx
                for idx, row in enumerate(timeseries)
                if row.get("sydney_time") == "2026-10-16 23:00"
            ),
            max(0, len(timeseries) - 1),
        )
    else:
        min_date = "2026-09-22"
        max_date = "2026-10-20"
        default_step = 0

    ts_json = json.dumps(timeseries, separators=(",", ":"))
    ev_json = json.dumps(events, separators=(",", ":"))
    meta_json = json.dumps(metadata, separators=(",", ":"))

    lines = base_html.splitlines()
    out_lines: list[str] = []

    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("const RAW_TIMESERIES = "):
            out_lines.append(f"    const RAW_TIMESERIES = {ts_json};")
        elif stripped.startswith("const RAW_EVENTS = "):
            out_lines.append(f"    const RAW_EVENTS = {ev_json};")
        elif stripped.startswith("const METADATA = "):
            out_lines.append(f"    const METADATA = {meta_json};")
        elif stripped.startswith("let customStartDate = "):
            out_lines.append(f"    let customStartDate = '{min_date}';")
        elif stripped.startswith("let customEndDate = "):
            out_lines.append(f"    let customEndDate = '{max_date}';")
        elif stripped.startswith("let currentStepIndex = "):
            out_lines.append(
                f"    let currentStepIndex = {default_step}; // Dynamically bound to payload window"
            )
        elif stripped.startswith("buildSectionPills();"):
            out_lines.append(
                "        const startInputEl = document.getElementById('startDateInput');"
            )
            out_lines.append(
                f"        if (startInputEl) {{ startInputEl.value = '{min_date}'; startInputEl.min = '{min_date}'; startInputEl.max = '{max_date}'; }}"
            )
            out_lines.append(
                "        const endInputEl = document.getElementById('endDateInput');"
            )
            out_lines.append(
                f"        if (endInputEl) {{ endInputEl.value = '{max_date}'; endInputEl.min = '{min_date}'; endInputEl.max = '{max_date}'; }}"
            )
            out_lines.append(
                "        const sliderEl = document.getElementById('timeSlider');"
            )
            out_lines.append(
                "        if (sliderEl && RAW_TIMESERIES.length > 0) { sliderEl.max = RAW_TIMESERIES.length - 1; sliderEl.value = currentStepIndex; }"
            )
            out_lines.append(line)
        else:
            out_lines.append(line)

    return "\n".join(out_lines)
