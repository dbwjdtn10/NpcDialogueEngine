"""Standardized API error responses and exception handlers.

All API errors return a consistent JSON envelope::

    {
        "error": {
            "code": "NPC_NOT_FOUND",
            "message": "NPC 'unknown_npc' not found.",
            "request_id": "a1b2c3d4-..."
        }
    }

Register handlers on the FastAPI app via :func:`register_exception_handlers`.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Error codes
# ---------------------------------------------------------------------------

class ErrorCode:
    """Catalogue of machine-readable error codes."""

    # Client errors
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NPC_NOT_FOUND = "NPC_NOT_FOUND"
    QUEST_NOT_FOUND = "QUEST_NOT_FOUND"
    RATE_LIMITED = "RATE_LIMITED"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"

    # Server errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
    SERVICE_DEGRADED = "SERVICE_DEGRADED"


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class APIError(Exception):
    """Application-level error with structured code and HTTP status."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_error_body(
    code: str,
    message: str,
    request_id: str = "unknown",
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the standard error envelope."""
    body: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
        }
    }
    if details:
        body["error"]["details"] = details
    return body


def _get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

async def _handle_api_error(request: Request, exc: APIError) -> JSONResponse:
    """Handle our custom APIError exceptions."""
    request_id = _get_request_id(request)
    return JSONResponse(
        status_code=exc.status_code,
        content=_build_error_body(
            code=exc.code,
            message=exc.message,
            request_id=request_id,
            details=exc.details,
        ),
    )


async def _handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
    """Wrap FastAPI's HTTPException in our standard envelope."""
    request_id = _get_request_id(request)

    # Map common HTTP statuses to error codes
    code_map = {
        400: ErrorCode.VALIDATION_ERROR,
        403: ErrorCode.FORBIDDEN,
        404: ErrorCode.NPC_NOT_FOUND,
        429: ErrorCode.RATE_LIMITED,
    }
    code = code_map.get(exc.status_code, ErrorCode.INTERNAL_ERROR)

    return JSONResponse(
        status_code=exc.status_code,
        content=_build_error_body(
            code=code,
            message=str(exc.detail),
            request_id=request_id,
        ),
    )


async def _handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic / query-param validation errors."""
    request_id = _get_request_id(request)

    errors = []
    for error in exc.errors():
        errors.append({
            "field": " → ".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        })

    return JSONResponse(
        status_code=422,
        content=_build_error_body(
            code=ErrorCode.VALIDATION_ERROR,
            message="Request validation failed.",
            request_id=request_id,
            details={"errors": errors},
        ),
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register_exception_handlers(app: FastAPI) -> None:
    """Register all custom exception handlers on the app."""
    app.add_exception_handler(APIError, _handle_api_error)  # type: ignore[arg-type]
    app.add_exception_handler(HTTPException, _handle_http_exception)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _handle_validation_error)  # type: ignore[arg-type]
