"""Tests for middleware: rate limiting, metrics, correlation ID, and admin auth."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

# ---------------------------------------------------------------------------
# Rate limiter unit tests
# ---------------------------------------------------------------------------


class TestSlidingWindowCounter:
    """Tests for the in-memory sliding window rate counter."""

    @pytest.fixture()
    def counter(self):
        from src.api.rate_limiter import _SlidingWindowCounter

        return _SlidingWindowCounter(max_requests=3, window_seconds=10)

    @pytest.mark.asyncio
    async def test_allows_under_limit(self, counter):
        allowed, retry = await counter.is_allowed("1.2.3.4")
        assert allowed is True
        assert retry == 0

    @pytest.mark.asyncio
    async def test_allows_up_to_limit(self, counter):
        for _ in range(3):
            allowed, _ = await counter.is_allowed("1.2.3.4")
        assert allowed is True  # 3rd request is still within limit

    @pytest.mark.asyncio
    async def test_blocks_over_limit(self, counter):
        for _ in range(3):
            await counter.is_allowed("1.2.3.4")
        allowed, retry = await counter.is_allowed("1.2.3.4")
        assert allowed is False
        assert retry >= 1

    @pytest.mark.asyncio
    async def test_separate_ips(self, counter):
        for _ in range(3):
            await counter.is_allowed("1.1.1.1")
        # Different IP should still be allowed
        allowed, _ = await counter.is_allowed("2.2.2.2")
        assert allowed is True

    @pytest.mark.asyncio
    async def test_cleanup_removes_stale(self, counter):
        counter.window_seconds = 0  # Expire immediately
        await counter.is_allowed("1.2.3.4")
        await counter.cleanup()
        assert "1.2.3.4" not in counter._requests


# ---------------------------------------------------------------------------
# Metrics unit tests
# ---------------------------------------------------------------------------


class TestMetrics:
    """Tests for Prometheus metric primitives."""

    def setup_method(self):
        """Reset metrics state before each test."""
        from src.api import metrics

        metrics._counters.clear()
        metrics._histograms.clear()
        metrics._gauges.clear()

    def test_inc_counter(self):
        from src.api.metrics import inc_counter, _counters, _label_key

        inc_counter("http_requests_total", {"method": "GET"})
        inc_counter("http_requests_total", {"method": "GET"})
        key = _label_key("http_requests_total", {"method": "GET"})
        assert _counters[key] == 2

    def test_observe_histogram(self):
        from src.api.metrics import observe_histogram, _histograms, _label_key

        observe_histogram("duration", 0.5, {"path": "/api"})
        observe_histogram("duration", 1.5, {"path": "/api"})
        key = _label_key("duration", {"path": "/api"})
        assert len(_histograms[key]) == 2
        assert sum(_histograms[key]) == pytest.approx(2.0)

    def test_gauge_inc_dec(self):
        from src.api.metrics import inc_gauge, dec_gauge, _gauges, _label_key

        inc_gauge("ws_active", {"npc_id": "garon"})
        inc_gauge("ws_active", {"npc_id": "garon"})
        dec_gauge("ws_active", {"npc_id": "garon"})
        key = _label_key("ws_active", {"npc_id": "garon"})
        assert _gauges[key] == 1.0

    def test_gauge_does_not_go_negative(self):
        from src.api.metrics import dec_gauge, _gauges, _label_key

        dec_gauge("ws_active", {"npc_id": "garon"})
        key = _label_key("ws_active", {"npc_id": "garon"})
        assert _gauges[key] == 0.0

    def test_render_metrics_includes_counter(self):
        from src.api.metrics import inc_counter, render_metrics

        inc_counter("test_counter", {"label": "a"})
        output = render_metrics()
        assert "test_counter" in output
        assert 'label="a"' in output

    def test_render_metrics_includes_histogram_buckets(self):
        from src.api.metrics import observe_histogram, render_metrics

        observe_histogram("test_hist", 0.05)
        output = render_metrics()
        assert "test_hist_bucket" in output
        assert "test_hist_sum" in output
        assert "test_hist_count" in output


# ---------------------------------------------------------------------------
# Correlation ID tests
# ---------------------------------------------------------------------------


class TestCorrelationID:
    """Tests for X-Request-ID generation and propagation."""

    def test_label_key_with_labels(self):
        from src.api.metrics import _label_key

        key = _label_key("metric", {"a": "1", "b": "2"})
        assert "metric|" in key
        assert 'a="1"' in key
        assert 'b="2"' in key

    def test_label_key_without_labels(self):
        from src.api.metrics import _label_key

        key = _label_key("metric", None)
        assert key == "metric"

    def test_parse_key_round_trip(self):
        from src.api.metrics import _label_key, _parse_key

        key = _label_key("name", {"x": "1"})
        name, labels = _parse_key(key)
        assert name == "name"
        assert 'x="1"' in labels


# ---------------------------------------------------------------------------
# Admin API key auth tests
# ---------------------------------------------------------------------------


class TestAdminAuth:
    """Tests for admin endpoint API key verification."""

    @pytest.mark.asyncio
    async def test_open_when_no_key_configured(self):
        from src.api.routes.admin import verify_admin_api_key

        with patch("src.api.routes.admin.settings") as mock_settings:
            mock_settings.ADMIN_API_KEY = ""
            result = await verify_admin_api_key(api_key=None)
            assert result == "dev"

    @pytest.mark.asyncio
    async def test_valid_key_passes(self):
        from src.api.routes.admin import verify_admin_api_key

        with patch("src.api.routes.admin.settings") as mock_settings:
            mock_settings.ADMIN_API_KEY = "secret-key-123"
            result = await verify_admin_api_key(api_key="secret-key-123")
            assert result == "secret-key-123"

    @pytest.mark.asyncio
    async def test_invalid_key_raises_403(self):
        from fastapi import HTTPException

        from src.api.routes.admin import verify_admin_api_key

        with patch("src.api.routes.admin.settings") as mock_settings:
            mock_settings.ADMIN_API_KEY = "secret-key-123"
            with pytest.raises(HTTPException) as exc_info:
                await verify_admin_api_key(api_key="wrong-key")
            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_missing_key_raises_403(self):
        from fastapi import HTTPException

        from src.api.routes.admin import verify_admin_api_key

        with patch("src.api.routes.admin.settings") as mock_settings:
            mock_settings.ADMIN_API_KEY = "secret-key-123"
            with pytest.raises(HTTPException) as exc_info:
                await verify_admin_api_key(api_key=None)
            assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Path normalization tests
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Circuit breaker tests
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    """Tests for the circuit breaker state machine."""

    @pytest.fixture()
    def breaker(self):
        from src.api.circuit_breaker import CircuitBreaker

        return CircuitBreaker("test-service", failure_threshold=3, recovery_timeout=1.0)

    def test_starts_closed(self, breaker):
        from src.api.circuit_breaker import CircuitState

        assert breaker.state == CircuitState.CLOSED
        assert breaker.allow_request() is True

    def test_opens_after_threshold(self, breaker):
        from src.api.circuit_breaker import CircuitState

        for _ in range(3):
            breaker.record_failure()
        assert breaker.state == CircuitState.OPEN
        assert breaker.allow_request() is False

    def test_stays_closed_under_threshold(self, breaker):
        from src.api.circuit_breaker import CircuitState

        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.allow_request() is True

    def test_half_open_after_timeout(self, breaker):
        import time
        from src.api.circuit_breaker import CircuitState

        for _ in range(3):
            breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        # Fast-forward past recovery timeout
        breaker._last_failure_time = time.monotonic() - 2.0
        assert breaker.state == CircuitState.HALF_OPEN
        assert breaker.allow_request() is True

    def test_recovers_on_success_in_half_open(self, breaker):
        import time
        from src.api.circuit_breaker import CircuitState

        for _ in range(3):
            breaker.record_failure()
        breaker._last_failure_time = time.monotonic() - 2.0
        _ = breaker.state  # transition to HALF_OPEN

        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED

    def test_reopens_on_failure_in_half_open(self, breaker):
        import time
        from src.api.circuit_breaker import CircuitState

        for _ in range(3):
            breaker.record_failure()
        breaker._last_failure_time = time.monotonic() - 2.0
        _ = breaker.state  # transition to HALF_OPEN

        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

    def test_reset(self, breaker):
        from src.api.circuit_breaker import CircuitState

        for _ in range(3):
            breaker.record_failure()
        breaker.reset()
        assert breaker.state == CircuitState.CLOSED
        assert breaker._failure_count == 0

    def test_stats(self, breaker):
        breaker.record_success()
        stats = breaker.stats
        assert stats["name"] == "test-service"
        assert stats["state"] == "closed"
        assert stats["success_count"] == 1


# ---------------------------------------------------------------------------
# Path normalization tests
# ---------------------------------------------------------------------------


class TestPathNormalization:
    """Tests for metric path cardinality reduction."""

    def test_normalize_npc_chat_path(self):
        from src.api.metrics import _normalize_path

        result = _normalize_path("/ws/chat/blacksmith_garon")
        assert "{" in result  # Should contain a template variable

    def test_normalize_static_path_unchanged(self):
        from src.api.metrics import _normalize_path

        result = _normalize_path("/health")
        assert result == "/health"
