"""Async retry with exponential backoff for external service calls.

Provides a decorator that retries failed async function calls with
configurable backoff, jitter, and optional circuit breaker integration.

Usage::

    from src.api.retry import async_retry
    from src.api.circuit_breaker import llm_breaker

    @async_retry(max_retries=3, base_delay=1.0, breaker=llm_breaker)
    async def call_llm(prompt: str) -> str:
        ...
"""

from __future__ import annotations

import asyncio
import functools
import logging
import random
from typing import Any, Callable, TypeVar

from src.api.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def async_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: tuple[type[BaseException], ...] = (Exception,),
    breaker: CircuitBreaker | None = None,
) -> Callable[[F], F]:
    """Decorator for async functions with exponential backoff retry.

    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay in seconds before first retry.
        max_delay: Maximum delay cap in seconds.
        exponential_base: Multiplier for each successive delay.
        jitter: Add random jitter to prevent thundering herd.
        retryable_exceptions: Exception types that trigger a retry.
        breaker: Optional circuit breaker to consult before each attempt.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: BaseException | None = None

            for attempt in range(max_retries + 1):
                # Check circuit breaker
                if breaker and not breaker.allow_request():
                    logger.warning(
                        "Circuit breaker [%s] is OPEN, skipping %s",
                        breaker.name,
                        func.__name__,
                    )
                    raise RuntimeError(
                        f"Circuit breaker [{breaker.name}] is open — "
                        f"service temporarily unavailable"
                    )

                try:
                    result = await func(*args, **kwargs)
                    if breaker:
                        breaker.record_success()
                    return result

                except retryable_exceptions as exc:
                    last_exception = exc
                    if breaker:
                        breaker.record_failure()

                    if attempt == max_retries:
                        logger.error(
                            "%s failed after %d attempts: %s",
                            func.__name__,
                            max_retries + 1,
                            exc,
                        )
                        break

                    # Calculate delay with exponential backoff
                    delay = min(
                        base_delay * (exponential_base ** attempt),
                        max_delay,
                    )
                    if jitter:
                        delay = delay * (0.5 + random.random())

                    logger.warning(
                        "%s attempt %d/%d failed (%s), retrying in %.1fs...",
                        func.__name__,
                        attempt + 1,
                        max_retries + 1,
                        type(exc).__name__,
                        delay,
                    )
                    await asyncio.sleep(delay)

            raise last_exception  # type: ignore[misc]

        return wrapper  # type: ignore[return-value]

    return decorator
