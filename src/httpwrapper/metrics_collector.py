"""
Metrics collection and monitoring for HTTP requests, circuit breaker, and retry events.
"""

import threading
import time
from collections import defaultdict
from typing import Any, Dict, Optional

from .config import BackoffStrategy, CircuitBreakerState


class MetricsCollector:
    """
    Collects and manages metrics for HTTP client operations.

    Supports:
    - Request/response metrics (count, duration, status codes)
    - Circuit breaker state transitions
    - Retry attempt tracking
    - Error classification
    - Performance statistics
    """

    def __init__(self):
        """Initialize metrics collector."""
        self._lock = threading.RLock()

        # Request metrics
        self.request_count = defaultdict(int)
        self.request_duration_sum = defaultdict(float)
        self.request_duration_count = defaultdict(int)
        self.status_code_count = defaultdict(int)
        self.method_count = defaultdict(int)

        # Error metrics
        self.error_count = defaultdict(int)
        self.error_type_count = defaultdict(int)

        # Circuit breaker metrics
        self.circuit_breaker_state_changes = defaultdict(int)
        self.circuit_breaker_rejections = defaultdict(int)
        self.circuit_breaker_resets = defaultdict(int)

        # Retry metrics
        self.retry_attempts = defaultdict(int)
        self.retry_successes = defaultdict(int)
        self.retry_exhausted = defaultdict(int)
        self.retry_aborted = defaultdict(int)

        # Host-level metrics
        self.host_request_count = defaultdict(int)
        self.host_error_count = defaultdict(int)
        self.host_average_duration = defaultdict(float)

    def record_request(self, method: str, url: str, status_code: int, duration: float) -> None:
        """
        Record a successful HTTP request.

        Args:
            method: HTTP method
            url: Request URL
            status_code: Response status code
            duration: Request duration in seconds
        """
        with self._lock:
            from urllib.parse import urlparse
            host = urlparse(url).netloc or url

            # General metrics
            self.request_count['total'] += 1
            self.request_duration_sum['total'] += duration
            self.request_duration_count['total'] += 1
            self.status_code_count[str(status_code)] += 1
            self.method_count[method] += 1

            # Method-specific metrics
            method_key = f"method_{method.lower()}"
            self.request_count[method_key] += 1
            self.request_duration_sum[method_key] += duration
            self.request_duration_count[method_key] += 1

            # Status code specific metrics
            if status_code >= 200 and status_code < 300:
                self.request_count['success'] += 1
            elif status_code >= 400 and status_code < 500:
                self.request_count['client_error'] += 1
            elif status_code >= 500:
                self.request_count['server_error'] += 1

            # Host-specific metrics
            host_key = f"host_{host}"
            self.host_request_count[host_key] += 1
            self._update_host_average_duration(host_key, duration)

    def record_error(
        self,
        method: str,
        url: str,
        exception: Exception,
        duration: float
    ) -> None:
        """
        Record an error/retry event.

        Args:
            method: HTTP method
            url: Request URL
            exception: Exception that occurred
            duration: Request duration in seconds
        """
        with self._lock:
            from urllib.parse import urlparse
            host = urlparse(url).netloc or url

            # General error metrics
            self.error_count['total'] += 1
            self.request_duration_sum['error_total'] += duration
            self.request_duration_count['error_total'] += 1

            # Exception type metrics
            exception_type = type(exception).__name__
            self.error_type_count[exception_type] += 1

            # Method-specific error metrics
            method_error_key = f"method_{method.lower()}_error"
            self.error_count[method_error_key] += 1

            # Host-specific error metrics
            host_key = f"host_{host}"
            self.host_error_count[host_key] += 1
            self._update_host_average_duration(host_key, duration)

    def record_circuit_breaker_state_change(
        self,
        host: str,
        old_state: CircuitBreakerState,
        new_state: CircuitBreakerState
    ) -> None:
        """
        Record circuit breaker state change.

        Args:
            host: Host name
            old_state: Previous state
            new_state: New state
        """
        with self._lock:
            key = f"{old_state.value}_to_{new_state.value}"
            self.circuit_breaker_state_changes[key] += 1

            # Record current state
            state_key = f"state_{new_state.value}"
            self.circuit_breaker_state_changes[state_key] += 1

    def record_circuit_breaker_rejection(self, host: str) -> None:
        """
        Record circuit breaker rejection.

        Args:
            host: Host name
        """
        with self._lock:
            self.circuit_breaker_rejections['total'] += 1
            host_key = f"host_{host}"
            self.circuit_breaker_rejections[host_key] += 1

    def record_circuit_breaker_reset(self, host: str) -> None:
        """
        Record circuit breaker reset.

        Args:
            host: Host name
        """
        with self._lock:
            self.circuit_breaker_resets['total'] += 1
            host_key = f"host_{host}"
            self.circuit_breaker_resets[host_key] += 1

    def record_retry_attempt(
        self,
        method: str,
        url: str,
        attempt: int,
        delay: float
    ) -> None:
        """
        Record a retry attempt.

        Args:
            method: HTTP method
            url: Request URL
            attempt: Retry attempt number
            delay: Delay before this attempt
        """
        with self._lock:
            self.retry_attempts['total'] += 1

            # Bucket by attempt number
            attempt_bucket = min(attempt + 1, 10)  # Cap at 10 for aggregation
            attempt_key = f"attempt_{attempt_bucket}"
            self.retry_attempts[attempt_key] += 1

    def record_retry_success(self, method: str, url: str, attempts: int) -> None:
        """
        Record successful retry.

        Args:
            method: HTTP method
            url: Request URL
            attempts: Number of attempts used
        """
        with self._lock:
            self.retry_successes['total'] += 1
            retry_count_key = f"retries_{min(attempts - 1, 10)}"
            self.retry_successes[retry_count_key] += 1

    def record_retry_exhausted(
        self,
        method: str,
        url: str,
        max_attempts: int
    ) -> None:
        """
        Record exhausted retry attempts.

        Args:
            method: HTTP method
            url: Request URL
            max_attempts: Maximum retry attempts
        """
        with self._lock:
            from urllib.parse import urlparse
            host = urlparse(url).netloc or url

            self.retry_exhausted['total'] += 1
            host_key = f"host_{host}"
            self.retry_exhausted[host_key] += 1

    def record_retry_aborted(
        self,
        method: str,
        url: str,
        attempt: int
    ) -> None:
        """
        Record aborted retry (e.g., circuit breaker).

        Args:
            method: HTTP method
            url: Request URL
            attempt: Retry attempt number when aborted
        """
        with self._lock:
            from urllib.parse import urlparse
            host = urlparse(url).netloc or url

            self.retry_aborted['total'] += 1
            host_key = f"host_{host}"
            self.retry_aborted[host_key] += 1

    def _update_host_average_duration(self, host_key: str, duration: float) -> None:
        """Update running average duration for a host."""
        current_count = self.host_request_count.get(host_key, 0)
        current_avg = self.host_average_duration.get(host_key, 0.0)

        # Calculate new average using running average formula
        new_count = current_count + 1
        new_avg = ((current_avg * current_count) + duration) / new_count

        self.host_average_duration[host_key] = new_avg

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive metrics summary.

        Returns:
            Dictionary containing all metrics
        """
        with self._lock:
            # Calculate averages
            total_requests = self.request_duration_count.get('total', 0)
            avg_duration_total = (
                self.request_duration_sum.get('total', 0.0) / total_requests
                if total_requests > 0 else 0.0
            )

            # Success rate
            success_count = self.request_count.get('success', 0)
            success_rate = (
                success_count / total_requests * 100
                if total_requests > 0 else 0.0
            )

            return {
                'timestamp': time.time(),
                'summary': {
                    'total_requests': self.request_count.get('total', 0),
                    'success_rate_percent': round(success_rate, 2),
                    'average_duration_seconds': round(avg_duration_total, 3),
                    'total_errors': self.error_count.get('total', 0),
                },
                'requests': dict(self.request_count),
                'status_codes': dict(self.status_code_count),
                'methods': dict(self.method_count),
                'errors': {
                    'total': dict(self.error_count),
                    'by_type': dict(self.error_type_count),
                },
                'circuit_breaker': {
                    'rejections': dict(self.circuit_breaker_rejections),
                    'resets': dict(self.circuit_breaker_resets),
                    'state_changes': dict(self.circuit_breaker_state_changes),
                },
                'retries': {
                    'attempts': dict(self.retry_attempts),
                    'successes': dict(self.retry_successes),
                    'exhausted': dict(self.retry_exhausted),
                    'aborted': dict(self.retry_aborted),
                },
                'hosts': {
                    host: {
                        'requests': self.host_request_count.get(host, 0),
                        'errors': self.host_error_count.get(host, 0),
                        'average_duration': round(self.host_average_duration.get(host, 0.0), 3),
                    }
                    for host in set(self.host_request_count.keys()) | set(self.host_error_count.keys())
                    if host.startswith('host_')
                }
            }

    def reset(self) -> None:
        """Reset all metrics to zero."""
        with self._lock:
            self.request_count.clear()
            self.request_duration_sum.clear()
            self.request_duration_count.clear()
            self.status_code_count.clear()
            self.method_count.clear()
            self.error_count.clear()
            self.error_type_count.clear()
            self.circuit_breaker_state_changes.clear()
            self.circuit_breaker_rejections.clear()
            self.circuit_breaker_resets.clear()
            self.retry_attempts.clear()
            self.retry_successes.clear()
            self.retry_exhausted.clear()
            self.retry_aborted.clear()
            self.host_request_count.clear()
            self.host_error_count.clear()
            self.host_average_duration.clear()
