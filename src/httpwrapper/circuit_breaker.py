"""
Circuit Breaker implementation with closed, open, and half-open states.
"""

import threading
import time
from typing import Dict, Optional

from .config import CircuitBreakerConfig, CircuitBreakerState
from .exceptions import CircuitBreakerOpenError


class CircuitBreaker:
    """
    Circuit breaker implementation following the classic pattern.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Failing service, requests fail immediately
    - HALF_OPEN: Testing recovery, limited requests allowed

    Transitions:
    - CLOSED -> OPEN: After failure_threshold failures
    - OPEN -> HALF_OPEN: After recovery_timeout
    - HALF_OPEN -> CLOSED: After success_threshold successes
    - HALF_OPEN -> OPEN: After first failure in half-open
    """

    def __init__(self, config: CircuitBreakerConfig):
        """
        Initialize circuit breaker.

        Args:
            config: Circuit breaker configuration
        """
        self.config = config
        self._lock = threading.RLock()

        # Per-host state storage
        self._states: Dict[str, CircuitBreakerState] = {}
        self._failure_counts: Dict[str, int] = {}
        self._success_counts: Dict[str, int] = {}
        self._last_failure_times: Dict[str, float] = {}
        self._last_attempt_times: Dict[str, float] = {}

    def _get_host_state(self, host: str) -> CircuitBreakerState:
        """Get current state for a host."""
        return self._states.get(host, CircuitBreakerState.CLOSED)

    def _set_host_state(self, host: str, state: CircuitBreakerState) -> None:
        """Set state for a host."""
        self._states[host] = state

    def _get_failure_count(self, host: str) -> int:
        """Get failure count for a host."""
        return self._failure_counts.get(host, 0)

    def _set_failure_count(self, host: str, count: int) -> None:
        """Set failure count for a host."""
        self._failure_counts[host] = count

    def _get_success_count(self, host: str) -> int:
        """Get success count for a host."""
        return self._success_counts.get(host, 0)

    def _set_success_count(self, host: str, count: int) -> None:
        """Set success count for a host."""
        self._success_counts[host] = count

    def _get_last_failure_time(self, host: str) -> float:
        """Get last failure time for a host."""
        return self._last_failure_times.get(host, 0.0)

    def _set_last_failure_time(self, host: str, timestamp: float) -> None:
        """Set last failure time for a host."""
        self._last_failure_times[host] = timestamp

    def _get_last_attempt_time(self, host: str) -> float:
        """Get last attempt time for a host."""
        return self._last_attempt_times.get(host, 0.0)

    def _set_last_attempt_time(self, host: str, timestamp: float) -> None:
        """Set last attempt time for a host."""
        self._last_attempt_times[host] = timestamp

    def can_proceed(self, host: str) -> bool:
        """
        Check if a request can proceed based on circuit breaker state.

        Args:
            host: The host to check

        Returns:
            True if request can proceed, False otherwise
        """
        with self._lock:
            state = self._get_host_state(host)
            current_time = time.time()

            if state == CircuitBreakerState.CLOSED:
                return True

            elif state == CircuitBreakerState.OPEN:
                # Check if enough time has passed to move to half-open
                last_failure_time = self._get_last_failure_time(host)
                if current_time - last_failure_time >= self.config.recovery_timeout:
                    # Move to half-open and allow this request
                    self._set_host_state(host, CircuitBreakerState.HALF_OPEN)
                    self._set_success_count(host, 0)
                    return True
                else:
                    return False

            elif state == CircuitBreakerState.HALF_OPEN:
                # In half-open state, allow requests but track carefully
                return True

            return False

    def record_success(self, host: str) -> None:
        """
        Record a successful request.

        Args:
            host: The host for which success was recorded
        """
        with self._lock:
            state = self._get_host_state(host)
            current_time = time.time()

            if state == CircuitBreakerState.HALF_OPEN:
                # In half-open, increment success count
                success_count = self._get_success_count(host) + 1
                self._set_success_count(host, success_count)

                # Check if we've reached success threshold
                if success_count >= self.config.success_threshold:
                    # Move back to closed state
                    self._set_host_state(host, CircuitBreakerState.CLOSED)
                    self._set_failure_count(host, 0)
                    self._set_success_count(host, 0)

            elif state == CircuitBreakerState.CLOSED:
                # Reset failure count on success in closed state
                self._set_failure_count(host, 0)
                self._set_success_count(host, 0)

            # Always update attempt time
            self._set_last_attempt_time(host, current_time)

    def record_failure(self, host: str) -> None:
        """
        Record a failed request.

        Args:
            host: The host for which failure was recorded
        """
        with self._lock:
            state = self._get_host_state(host)
            current_time = time.time()

            if state == CircuitBreakerState.HALF_OPEN:
                # Any failure in half-open immediately trips back to open
                self._set_host_state(host, CircuitBreakerState.OPEN)
                self._set_failure_count(host, self.config.failure_threshold)
                self._set_success_count(host, 0)

            elif state == CircuitBreakerState.CLOSED:
                # Increment failure count in closed state
                failure_count = self._get_failure_count(host) + 1
                self._set_failure_count(host, failure_count)

                # Check if we've reached failure threshold
                if failure_count >= self.config.failure_threshold:
                    # Trip the circuit
                    self._set_host_state(host, CircuitBreakerState.OPEN)

            # Update failure time
            self._set_last_failure_time(host, current_time)
            self._set_last_attempt_time(host, current_time)

    def get_state(self, host: str) -> CircuitBreakerState:
        """
        Get the current state of the circuit breaker for a host.

        Args:
            host: The host to check

        Returns:
            Current circuit breaker state
        """
        with self._lock:
            return self._get_host_state(host)

    def failure_count(self, host: str) -> int:
        """
        Get the current failure count for a host.

        Args:
            host: The host to check

        Returns:
            Current failure count
        """
        with self._lock:
            return self._get_failure_count(host)

    def last_failure_time(self, host: str) -> float:
        """
        Get the last failure timestamp for a host.

        Args:
            host: The host to check

        Returns:
            Last failure timestamp
        """
        with self._lock:
            return self._get_last_failure_time(host)

    def reset(self, host: str) -> None:
        """
        Manually reset the circuit breaker for a host to closed state.

        Args:
            host: The host to reset
        """
        with self._lock:
            self._set_host_state(host, CircuitBreakerState.CLOSED)
            self._set_failure_count(host, 0)
            self._set_success_count(host, 0)

    def get_stats(self, host: str) -> Dict[str, any]:
        """
        Get statistics for a host.

        Args:
            host: The host to get stats for

        Returns:
            Dictionary with circuit breaker statistics
        """
        with self._lock:
            return {
                'state': self._get_host_state(host).value,
                'failure_count': self._get_failure_count(host),
                'success_count': self._get_success_count(host),
                'last_failure_time': self._get_last_failure_time(host),
                'last_attempt_time': self._get_last_attempt_time(host),
                'config': {
                    'failure_threshold': self.config.failure_threshold,
                    'recovery_timeout': self.config.recovery_timeout,
                    'success_threshold': self.config.success_threshold,
                }
            }
