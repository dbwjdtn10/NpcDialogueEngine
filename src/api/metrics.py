"""Prometheus-compatible application metrics.

Collects request counts, latency histograms, and gauge values and
exposes them via a ``/metrics`` endpoint in the Prometheus text
exposition format.  No external dependency on ``prometheus_client``
is required -- metrics are rendered manually so the deployment
footprint stays minimal.

Metric catalogue
----------------
- ``http_requests_total``          counter   (method, path, status)
- ``http_request_duration_seconds`` histogram (method, path)
- ``websocket_connections_active``  gauge
- ``dialogue_pipeline_duration_seconds`` histogram (npc_id)
- ``rag_retrieval_duration_seconds``     histogram
- ``rate_limit_rejections_total``        counter   (client_ip)
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Low-level metric primitives
# ---------------------------------------------------------------------------

_lock = threading.Lock()

# Counters: key → count
_counters: dict[str, int] = defaultdict(int)

# Histograms: key → list[float]  (raw observations)
_histograms: dict[str, list[float]] = defaultdict(list)

# Gauges: key → float
_gauges: dict[str, float] = defaultdict(float)

# Histogram bucket boundaries (seconds)
_LATENCY_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)


def inc_counter(name: str, labels: dict[str, str] | None = None) -> None:
    """Increment a counter metric by 1."""
    key = _label_key(name, labels)
    with _lock:
        _counters[key] += 1


def observe_histogram(name: str, value: float, labels: dict[str, str] | None = None) -> None:
    """Record an observation in a histogram metric."""
    key = _label_key(name, labels)
    with _lock:
        _histograms[key].append(value)


def set_gauge(name: str, value: float, labels: dict[str, str] | None = None) -> None:
    """Set a gauge metric to *value*."""
    key = _label_key(name, labels)
    with _lock:
        _gauges[key] = value


def inc_gauge(name: str, labels: dict[str, str] | None = None) -> None:
    """Increment a gauge metric by 1."""
    key = _label_key(name, labels)
    with _lock:
        _gauges[key] += 1


def dec_gauge(name: str, labels: dict[str, str] | None = None) -> None:
    """Decrement a gauge metric by 1."""
    key = _label_key(name, labels)
    with _lock:
        _gauges[key] = max(0, _gauges[key] - 1)


# ---------------------------------------------------------------------------
# Prometheus exposition
# ---------------------------------------------------------------------------

def render_metrics() -> str:
    """Return all metrics in Prometheus text exposition format."""
    lines: list[str] = []

    with _lock:
        # Counters
        _render_counter_family(lines, _counters)

        # Gauges
        for key, value in sorted(_gauges.items()):
            name, labels = _parse_key(key)
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name}{{{labels}}} {value}")

        # Histograms
        _render_histogram_family(lines, _histograms)

    lines.append("")
    return "\n".join(lines)


def _render_counter_family(lines: list[str], counters: dict[str, int]) -> None:
    seen_names: set[str] = set()
    for key, count in sorted(counters.items()):
        name, labels = _parse_key(key)
        if name not in seen_names:
            lines.append(f"# TYPE {name} counter")
            seen_names.add(name)
        lines.append(f"{name}{{{labels}}} {count}")


def _render_histogram_family(lines: list[str], histograms: dict[str, list[float]]) -> None:
    seen_names: set[str] = set()
    for key, observations in sorted(histograms.items()):
        name, labels = _parse_key(key)
        if name not in seen_names:
            lines.append(f"# TYPE {name} histogram")
            seen_names.add(name)

        total = sum(observations)
        count = len(observations)

        for bucket in _LATENCY_BUCKETS:
            bucket_count = sum(1 for o in observations if o <= bucket)
            lines.append(f'{name}_bucket{{{labels},le="{bucket}"}} {bucket_count}')
        lines.append(f'{name}_bucket{{{labels},le="+Inf"}} {count}')
        lines.append(f"{name}_sum{{{labels}}} {total:.6f}")
        lines.append(f"{name}_count{{{labels}}} {count}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _label_key(name: str, labels: dict[str, str] | None) -> str:
    if not labels:
        return name
    label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
    return f"{name}|{label_str}"


def _parse_key(key: str) -> tuple[str, str]:
    if "|" in key:
        name, labels = key.split("|", 1)
        return name, labels
    return key, ""


# ---------------------------------------------------------------------------
# FastAPI middleware for automatic HTTP metrics
# ---------------------------------------------------------------------------

def _normalize_path(path: str) -> str:
    """Collapse dynamic path segments to reduce cardinality.

    ``/ws/chat/blacksmith_garon`` → ``/ws/chat/{npc_id}``
    ``/api/v1/npcs/blacksmith_garon/profile`` → ``/api/v1/npcs/{npc_id}/profile``
    """
    parts = path.strip("/").split("/")
    normalised: list[str] = []
    for i, part in enumerate(parts):
        if i > 0 and parts[i - 1] in ("chat", "npcs", "quests"):
            normalised.append(f"{{{parts[i - 1][:-1] + '_id' if parts[i - 1].endswith('s') else parts[i - 1] + '_id'}}}")
        else:
            normalised.append(part)
    return "/" + "/".join(normalised)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Collect HTTP request count and latency metrics automatically."""

    SKIP_PATHS: set[str] = {"/metrics"}

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        method = request.method
        path = _normalize_path(request.url.path)

        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        status = str(response.status_code)

        inc_counter(
            "http_requests_total",
            {"method": method, "path": path, "status": status},
        )
        observe_histogram(
            "http_request_duration_seconds",
            duration,
            {"method": method, "path": path},
        )

        return response
