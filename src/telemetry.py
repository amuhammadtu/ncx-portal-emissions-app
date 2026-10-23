"""
Structured Cloud Logging & OpenTelemetry Span Instrumentation (`ENG-2084`).

Emits structured JSON log payloads to stdout compatible with Google Cloud Logging
and OpenTelemetry trace correlation (`logging.googleapis.com/trace`), enabling the
SEAL Platform Streamlit Fleet Overview dashboard and FinOps attribution alerts.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import sys
import time
import uuid
from datetime import UTC, datetime
from typing import Any, Generator

APP_NAME = os.environ.get("APP_NAME", "ncx-portal-emissions")
APP_ENV = os.environ.get("APP_ENV", "dev")
COST_CENTRE = os.environ.get("COST_CENTRE", "cc-am-tunnel-ops")
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "tu-data-edw-pr-1")


def compute_user_hash(identifier: str) -> str:
    """Return a privacy-preserving 12-char SHA-256 hex digest for user attribution."""
    normalized = (identifier or "anonymous").strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]


def parse_trace_header(cloud_trace_context: str | None) -> str | None:
    """
    Convert X-Cloud-Trace-Context (`TRACE_ID/SPAN_ID;o=TRACE_TRUE`) into
    `projects/{GCP_PROJECT_ID}/traces/{TRACE_ID}` for Cloud Logging correlation.
    """
    if not cloud_trace_context:
        return None
    trace_id = cloud_trace_context.split("/")[0].strip()
    if not trace_id:
        return None
    return f"projects/{GCP_PROJECT_ID}/traces/{trace_id}"


def log_structured_event(
    message: str,
    *,
    severity: str = "INFO",
    page: str = "ncx_portal_emissions",
    user_hash: str = "anonymous",
    bq_job_id: str | None = None,
    bytes_billed: int | None = None,
    duration_ms: float | None = None,
    cache_hit: bool | None = None,
    trace_context: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Emit a single-line structured JSON log record to stdout for Cloud Run / Cloud Logging.
    """
    payload: dict[str, Any] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "severity": severity.upper(),
        "message": message,
        "app": APP_NAME,
        "env": APP_ENV,
        "cost_centre": COST_CENTRE,
        "page": page,
        "user_hash": user_hash,
    }

    trace_path = parse_trace_header(trace_context)
    if trace_path:
        payload["logging.googleapis.com/trace"] = trace_path

    if bq_job_id is not None:
        payload["bq_job_id"] = bq_job_id
    if bytes_billed is not None:
        payload["bytes_billed"] = int(bytes_billed)
    if duration_ms is not None:
        payload["duration_ms"] = round(float(duration_ms), 2)
    if cache_hit is not None:
        payload["cache_hit"] = bool(cache_hit)
    if extra:
        payload.update(extra)

    sys.stdout.write(json.dumps(payload, default=str) + "\n")
    sys.stdout.flush()
    return payload


@contextlib.contextmanager
def trace_span(
    span_name: str,
    *,
    page: str = "ncx_portal_emissions",
    user_hash: str = "anonymous",
    attributes: dict[str, Any] | None = None,
) -> Generator[dict[str, Any], None, None]:
    """
    Lightweight OpenTelemetry-compatible span context manager (`ENG-2084`).
    Records duration_ms and emits a structured trace completion event.
    """
    span_id = uuid.uuid4().hex[:16]
    start_ns = time.perf_counter_ns()
    span_ctx: dict[str, Any] = {
        "span_id": span_id,
        "span_name": span_name,
        **(attributes or {}),
    }
    try:
        yield span_ctx
    except Exception as exc:
        elapsed_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0
        log_structured_event(
            f"Span failed: {span_name} ({exc})",
            severity="ERROR",
            page=page,
            user_hash=user_hash,
            duration_ms=elapsed_ms,
            extra={"span_id": span_id, "span_name": span_name, "error": str(exc)},
        )
        raise
    else:
        elapsed_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0
        span_ctx["duration_ms"] = round(elapsed_ms, 2)
        log_structured_event(
            f"Span completed: {span_name}",
            severity="INFO",
            page=page,
            user_hash=user_hash,
            bq_job_id=span_ctx.get("bq_job_id"),
            bytes_billed=span_ctx.get("bytes_billed"),
            duration_ms=elapsed_ms,
            cache_hit=span_ctx.get("cache_hit"),
            extra={k: v for k, v in span_ctx.items() if k not in {"bq_job_id", "bytes_billed", "cache_hit", "duration_ms"}},
        )
