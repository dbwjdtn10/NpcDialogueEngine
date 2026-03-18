"""Sliding-window rate limiter middleware for FastAPI.

Implements per-client IP rate limiting using an in-memory sliding window
counter. Exceeding the configured threshold returns HTTP 429 with a
``Retry-After`` header indicating when the client may retry.

Design decisions:
- In-memory storage keeps the implementation dependency-free; for
  horizontally-scaled deployments, swap to a Redis-backed backend.
- The sliding window algorithm provides smoother rate enforcement
  compared to fixed-window counters.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from src.config import settings

logger = logging.getLogger(__name__)


class _SlidingWindowCounter:
    """Thread-safe sliding window rate counter.

    Each client IP maps to a list of request timestamps. On every
    incoming request the window is pruned of expired entries before
    the count is checked.
    """

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def is_allowed(self, client_ip: str) -> tuple[bool, int]:
        """Check whether *client_ip* is within the rate limit.

        Returns:
            A tuple of ``(allowed, retry_after_seconds)``.  When
            ``allowed`` is ``True``, ``retry_after_seconds`` is ``0``.
        """
        now = time.monotonic()
        window_start = now - self.window_seconds

        async with self._lock:
            # Prune expired timestamps
            timestamps = self._requests[client_ip]
            self._requests[client_ip] = [
                ts for ts in timestamps if ts > window_start
            ]
            timestamps = self._requests[client_ip]

            if len(timestamps) >= self.max_requests:
                # Calculate when the oldest request in the window expires
                retry_after = int(timestamps[0] - window_start) + 1
                return False, max(retry_after, 1)

            timestamps.append(now)
            return True, 0

    async def cleanup(self) -> None:
        """Remove stale entries to prevent unbounded memory growth."""
        now = time.monotonic()
        window_start = now - self.window_seconds

        async with self._lock:
            stale_keys = [
                ip
                for ip, timestamps in self._requests.items()
                if not timestamps or timestamps[-1] <= window_start
            ]
            for key in stale_keys:
                del self._requests[key]


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware enforcing per-IP sliding-window rate limits.

    Requests exceeding the limit receive a ``429 Too Many Requests``
    response with standard rate-limit headers.

    Skipped paths (e.g. ``/health``, ``/metrics``) are excluded from
    enforcement so that monitoring probes are never throttled.
    """

    SKIP_PATHS: set[str] = {"/health", "/health/detailed", "/metrics", "/docs", "/openapi.json"}

    def __init__(self, app: Callable, **kwargs) -> None:  # type: ignore[type-arg]
        super().__init__(app, **kwargs)
        self._counter = _SlidingWindowCounter(
            max_requests=settings.RATE_LIMIT_MAX_REQUESTS,
            window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
        )
        self._cleanup_task: asyncio.Task | None = None  # type: ignore[type-arg]

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Skip health/monitoring endpoints
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        allowed, retry_after = await self._counter.is_allowed(client_ip)

        if not allowed:
            logger.warning(
                "Rate limit exceeded for %s on %s %s",
                client_ip,
                request.method,
                request.url.path,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests. Please try again later.",
                    "retry_after": retry_after,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(settings.RATE_LIMIT_MAX_REQUESTS),
                    "X-RateLimit-Window": str(settings.RATE_LIMIT_WINDOW_SECONDS),
                },
            )

        response = await call_next(request)

        # Attach informational rate-limit headers
        response.headers["X-RateLimit-Limit"] = str(settings.RATE_LIMIT_MAX_REQUESTS)
        response.headers["X-RateLimit-Window"] = str(settings.RATE_LIMIT_WINDOW_SECONDS)

        return response
