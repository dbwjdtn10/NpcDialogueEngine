"""FastAPI middleware for request logging, error handling, and observability.

Middleware stack (outermost → innermost):

1. **GZipMiddleware**           – response compression (≥500 bytes)
2. **ErrorHandlingMiddleware**  – catches unhandled exceptions
3. **SecurityHeadersMiddleware** – OWASP recommended response headers
4. **RateLimitMiddleware**      – per-IP sliding-window throttling
5. **MetricsMiddleware**        – Prometheus request counters / histograms
6. **RequestLoggingMiddleware** – structured logging with correlation ID
"""

from __future__ import annotations

import logging
import time
import traceback
import uuid
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs every incoming request with method, path, status, duration, and correlation ID.

    A unique ``X-Request-ID`` is attached to every request/response pair
    so that individual transactions can be traced across distributed logs.
    If the caller supplies an ``X-Request-ID`` header the value is reused;
    otherwise a new UUID-4 is generated.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # --- Correlation ID ---
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        # Store on request state so downstream handlers can access it
        request.state.request_id = request_id

        start = time.perf_counter()
        method = request.method
        path = request.url.path
        client = request.client.host if request.client else "unknown"

        logger.info(
            "[%s] -> %s %s from %s",
            request_id[:8],
            method,
            path,
            client,
        )

        response = await call_next(request)

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "[%s] <- %s %s %d (%.1fms)",
            request_id[:8],
            method,
            path,
            response.status_code,
            elapsed_ms,
        )

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.1f}"
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach OWASP-recommended security headers to every response.

    These headers instruct browsers to enable built-in protections
    against common web vulnerabilities (XSS, clickjacking, MIME
    sniffing, etc.).
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"

        return response


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Catches unhandled exceptions and returns a structured JSON error response.

    The correlation ID (if present) is included in the error payload so
    that operators can cross-reference user reports with server logs.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:
            request_id = getattr(request.state, "request_id", "unknown")
            logger.error(
                "[%s] Unhandled exception on %s %s: %s\n%s",
                request_id[:8] if request_id != "unknown" else "????????",
                request.method,
                request.url.path,
                exc,
                traceback.format_exc(),
            )
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal server error",
                    "type": type(exc).__name__,
                    "request_id": request_id,
                },
            )


def register_middleware(app: FastAPI) -> None:
    """Register all middleware on the FastAPI application.

    Middleware is added in reverse order because Starlette processes
    them as a stack (last added = outermost).

    Execution order for an incoming request::

        GZip → ErrorHandling → SecurityHeaders → RateLimit
             → Metrics → RequestLogging → Route handler

    Args:
        app: The FastAPI application instance.
    """
    from starlette.middleware.gzip import GZipMiddleware

    from src.api.metrics import MetricsMiddleware
    from src.api.rate_limiter import RateLimitMiddleware

    # Outermost → innermost (added in reverse)
    app.add_middleware(GZipMiddleware, minimum_size=500)
    app.add_middleware(ErrorHandlingMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
