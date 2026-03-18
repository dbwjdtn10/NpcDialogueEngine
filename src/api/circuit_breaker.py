"""Lightweight circuit breaker for graceful degradation.

Wraps calls to external services (Redis, PostgreSQL, LLM APIs) so
that repeated failures trigger a fast-fail state instead of waiting
for timeouts on every request.

States:
    CLOSED  → normal operation, all calls pass through.
    OPEN    → service presumed down, calls fail immediately.
    HALF_OPEN → after a cooldown period one probe call is allowed
                through to test recovery.

Usage::

    redis_breaker = CircuitBreaker("redis", failure_threshold=3, recovery_timeout=30)

    async def get_from_redis(key: str):
        if not redis_breaker.allow_request():
            return None  # fallback
        try:
            value = await redis.get(key)
            redis_breaker.record_success()
            return value
        except Exception:
            redis_breaker.record_failure()
            return None  # fallback
"""

from __future__ import annotations

import enum
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class CircuitState(enum.Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Per-service circuit breaker with configurable thresholds.

    Parameters:
        name: Human-readable service name (used in log messages).
        failure_threshold: Consecutive failures before opening the circuit.
        recovery_timeout: Seconds to wait before allowing a probe request.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._success_count = 0

    @property
    def state(self) -> CircuitState:
        """Current circuit state (may transition on read)."""
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                logger.info(
                    "Circuit breaker [%s]: OPEN → HALF_OPEN (probing)",
                    self.name,
                )
        return self._state

    def allow_request(self) -> bool:
        """Return ``True`` if the call should proceed."""
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.HALF_OPEN:
            return True  # allow one probe
        return False  # OPEN

    def record_success(self) -> None:
        """Notify the breaker that a call succeeded."""
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            logger.info(
                "Circuit breaker [%s]: HALF_OPEN → CLOSED (recovered)",
                self.name,
            )
        self._success_count += 1

    def record_failure(self) -> None:
        """Notify the breaker that a call failed."""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        if self._state == CircuitState.HALF_OPEN:
            # Probe failed → go back to OPEN
            self._state = CircuitState.OPEN
            logger.warning(
                "Circuit breaker [%s]: HALF_OPEN → OPEN (probe failed)",
                self.name,
            )
        elif self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(
                "Circuit breaker [%s]: CLOSED → OPEN after %d failures",
                self.name,
                self._failure_count,
            )

    def reset(self) -> None:
        """Force-reset to CLOSED state (e.g. for testing)."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0

    @property
    def stats(self) -> dict[str, Any]:
        """Return current breaker statistics."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
        }


# ---------------------------------------------------------------------------
# Pre-configured breakers for each external service
# ---------------------------------------------------------------------------

redis_breaker = CircuitBreaker("redis", failure_threshold=3, recovery_timeout=15.0)
postgres_breaker = CircuitBreaker("postgresql", failure_threshold=3, recovery_timeout=30.0)
llm_breaker = CircuitBreaker("llm_api", failure_threshold=5, recovery_timeout=60.0)
