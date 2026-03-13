"""FastAPI middleware for request logging and error handling."""

from __future__ import annotations

import logging
import time
import traceback
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs every incoming request with method, path, status, and duration."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start = time.perf_counter()
        method = request.method
        path = request.url.path
        client = request.client.host if request.client else "unknown"

        logger.info("-> %s %s from %s", method, path, client)

        response = await call_next(request)

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "<- %s %s %d (%.1fms)",
            method,
            path,
            response.status_code,
            elapsed_ms,
        )

        response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.1f}"
        return response


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Catches unhandled exceptions and returns a structured JSON error response."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:
            logger.error(
                "Unhandled exception on %s %s: %s\n%s",
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
                },
            )


def register_middleware(app: FastAPI) -> None:
    """Register all middleware on the FastAPI application.

    Middleware is added in reverse order because Starlette processes
    them as a stack (last added = outermost).

    Args:
        app: The FastAPI application instance.
    """
    # Error handling is outermost so it catches middleware errors too
    app.add_middleware(ErrorHandlingMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
