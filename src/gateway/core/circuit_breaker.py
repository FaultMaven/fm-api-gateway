"""Circuit breaker for upstream service protection.

Prevents cascading failures by:
- Tracking failures per service
- Opening circuit after threshold failures
- Returning 503 immediately when circuit is open
- Automatically resetting after timeout

Pattern: In-memory circuit breaking (per gateway pod).
For distributed breaking across pods, use Redis backend.
"""

import logging
import time
from enum import Enum
from typing import Dict, Optional
from dataclasses import dataclass
from threading import Lock

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitStats:
    """Circuit breaker statistics for a service."""
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: Optional[float] = None
    opened_at: Optional[float] = None
    success_count_in_half_open: int = 0


class CircuitBreaker:
    """
    Circuit breaker for protecting against cascading failures.

    Logic:
    - CLOSED: Normal operation. Track failures.
    - OPEN: After fail_threshold failures, reject requests for reset_timeout seconds.
    - HALF_OPEN: After timeout, allow one test request.
        - If succeeds: Close circuit
        - If fails: Reopen circuit

    Example:
        breaker = CircuitBreaker(fail_threshold=5, reset_timeout=30)

        if breaker.is_open("fm-knowledge-service"):
            return 503 error

        try:
            response = await call_service()
            breaker.record_success("fm-knowledge-service")
        except Exception:
            breaker.record_failure("fm-knowledge-service")
    """

    def __init__(
        self,
        fail_threshold: int = 5,
        reset_timeout: int = 30,
        half_open_max_calls: int = 1,
        enabled: bool = True,
    ):
        """
        Initialize circuit breaker.

        Args:
            fail_threshold: Number of failures before opening circuit
            reset_timeout: Seconds to wait before attempting recovery
            half_open_max_calls: Number of test requests in HALF_OPEN state
            enabled: Whether circuit breaking is enabled
        """
        self.fail_threshold = fail_threshold
        self.reset_timeout = reset_timeout
        self.half_open_max_calls = half_open_max_calls
        self.enabled = enabled

        # Per-service circuit stats
        self._circuits: Dict[str, CircuitStats] = {}
        self._lock = Lock()

        logger.info(
            f"Circuit breaker initialized: "
            f"fail_threshold={fail_threshold}, "
            f"reset_timeout={reset_timeout}s, "
            f"enabled={enabled}"
        )

    def is_call_allowed(self, service_name: str) -> bool:
        """
        Check if call is allowed for service.

        Args:
            service_name: Service identifier (e.g., "fm-knowledge-service")

        Returns:
            True if call is allowed, False if circuit is open
        """
        if not self.enabled:
            return True

        with self._lock:
            circuit = self._get_or_create_circuit(service_name)

            # CLOSED: Allow call
            if circuit.state == CircuitState.CLOSED:
                return True

            # OPEN: Check if should transition to HALF_OPEN
            if circuit.state == CircuitState.OPEN:
                if self._should_attempt_reset(circuit):
                    logger.info(
                        f"Circuit {service_name}: OPEN -> HALF_OPEN (testing recovery)"
                    )
                    circuit.state = CircuitState.HALF_OPEN
                    circuit.success_count_in_half_open = 0
                    return True
                else:
                    # Still in open state
                    logger.warning(
                        f"Circuit {service_name}: OPEN, rejecting request "
                        f"(opened {int(time.time() - circuit.opened_at)}s ago)"
                    )
                    return False

            # HALF_OPEN: Allow limited test requests
            if circuit.state == CircuitState.HALF_OPEN:
                return True

            return True  # Fallback

    def record_success(self, service_name: str) -> None:
        """
        Record successful response from service.

        Args:
            service_name: Service identifier
        """
        if not self.enabled:
            return

        with self._lock:
            circuit = self._get_or_create_circuit(service_name)

            if circuit.state == CircuitState.HALF_OPEN:
                circuit.success_count_in_half_open += 1
                if circuit.success_count_in_half_open >= self.half_open_max_calls:
                    logger.info(
                        f"Circuit {service_name}: HALF_OPEN -> CLOSED (service recovered)"
                    )
                    circuit.state = CircuitState.CLOSED
                    circuit.failure_count = 0
                    circuit.success_count_in_half_open = 0

            elif circuit.state == CircuitState.CLOSED:
                # Reset failure count on success
                if circuit.failure_count > 0:
                    logger.debug(
                        f"Circuit {service_name}: Reset failure count "
                        f"(was {circuit.failure_count})"
                    )
                    circuit.failure_count = 0

    def record_failure(self, service_name: str) -> None:
        """
        Record failed response from service.

        Args:
            service_name: Service identifier
        """
        if not self.enabled:
            return

        with self._lock:
            circuit = self._get_or_create_circuit(service_name)
            circuit.failure_count += 1
            circuit.last_failure_time = time.time()

            if circuit.state == CircuitState.HALF_OPEN:
                # Failure during test -> reopen circuit
                logger.warning(
                    f"Circuit {service_name}: HALF_OPEN -> OPEN (test failed)"
                )
                circuit.state = CircuitState.OPEN
                circuit.opened_at = time.time()
                circuit.success_count_in_half_open = 0

            elif circuit.state == CircuitState.CLOSED:
                # Check if should open circuit
                if circuit.failure_count >= self.fail_threshold:
                    logger.error(
                        f"Circuit {service_name}: CLOSED -> OPEN "
                        f"({circuit.failure_count} consecutive failures)"
                    )
                    circuit.state = CircuitState.OPEN
                    circuit.opened_at = time.time()
                else:
                    logger.warning(
                        f"Circuit {service_name}: Failure recorded "
                        f"({circuit.failure_count}/{self.fail_threshold})"
                    )

    def get_state(self, service_name: str) -> CircuitState:
        """Get current circuit state for service."""
        with self._lock:
            circuit = self._get_or_create_circuit(service_name)
            return circuit.state

    def get_stats(self, service_name: str) -> dict:
        """Get circuit statistics for service."""
        with self._lock:
            circuit = self._get_or_create_circuit(service_name)
            return {
                "state": circuit.state.value,
                "failure_count": circuit.failure_count,
                "last_failure_time": circuit.last_failure_time,
                "opened_at": circuit.opened_at,
            }

    def _get_or_create_circuit(self, service_name: str) -> CircuitStats:
        """Get or create circuit stats for service."""
        if service_name not in self._circuits:
            self._circuits[service_name] = CircuitStats()
        return self._circuits[service_name]

    def _should_attempt_reset(self, circuit: CircuitStats) -> bool:
        """Check if enough time has passed to attempt circuit reset."""
        if not circuit.opened_at:
            return False
        time_open = time.time() - circuit.opened_at
        return time_open >= self.reset_timeout


# Global circuit breaker instance
_circuit_breaker: Optional[CircuitBreaker] = None


def get_circuit_breaker() -> CircuitBreaker:
    """Get or create circuit breaker singleton."""
    global _circuit_breaker
    if _circuit_breaker is None:
        # Read configuration from environment
        import os
        enabled = os.getenv("CIRCUIT_BREAKER_ENABLED", "true").lower() == "true"
        fail_threshold = int(os.getenv("CIRCUIT_BREAKER_FAIL_THRESHOLD", "5"))
        reset_timeout = int(os.getenv("CIRCUIT_BREAKER_RESET_TIMEOUT", "30"))

        _circuit_breaker = CircuitBreaker(
            fail_threshold=fail_threshold,
            reset_timeout=reset_timeout,
            enabled=enabled,
        )
    return _circuit_breaker
