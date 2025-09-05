"""
Custom exceptions for HTTPWrapper.
"""

from typing import Any, Dict, Optional


class HTTPWrapperError(Exception):
    """Base exception for HTTPWrapper."""

    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}

    def __str__(self):
        if self.status_code:
            return f"{self.message} (Status: {self.status_code})"
        return self.message


class RetryError(HTTPWrapperError):
    """Raised when all retry attempts are exhausted."""

    def __init__(
        self,
        message: str,
        attempts: int,
        last_exception: Optional[Exception] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, details=details)
        self.attempts = attempts
        self.last_exception = last_exception

    def __str__(self):
        base_msg = super().__str__()
        return f"{base_msg} after {self.attempts} attempts"


class CircuitBreakerError(HTTPWrapperError):
    """Raised when circuit breaker is open and prevents requests."""

    def __init__(
        self,
        message: str,
        circuit_breaker_name: str,
        state: str,
        failures_count: int,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, details=details)
        self.circuit_breaker_name = circuit_breaker_name
        self.state = state
        self.failures_count = failures_count

    def __str__(self):
        base_msg = super().__str__()
        return f"{base_msg} [Circuit: {self.circuit_breaker_name}, State: {self.state}, Failures: {self.failures_count}]"


class CircuitBreakerOpenError(CircuitBreakerError):
    """Raised when circuit breaker is in open state."""

    def __init__(
        self,
        circuit_breaker_name: str,
        failures_count: int,
        last_failure_time: float,
        details: Optional[Dict[str, Any]] = None
    ):
        message = f"Circuit breaker '{circuit_breaker_name}' is OPEN"
        super().__init__(
            message=message,
            circuit_breaker_name=circuit_breaker_name,
            state="open",
            failures_count=failures_count,
            details=details
        )
        self.last_failure_time = last_failure_time


class ConfigurationError(HTTPWrapperError):
    """Raised when there's a configuration error."""

    def __init__(self, message: str, config_key: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details=details)
        self.config_key = config_key

    def __str__(self):
        base_msg = super().__str__()
        if self.config_key:
            return f"{base_msg} (Config: {self.config_key})"
        return base_msg


class TimeoutError(HTTPWrapperError):
    """Raised when request times out."""

    def __init__(
        self,
        message: str,
        timeout: float,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, details=details)
        self.timeout = timeout

    def __str__(self):
        base_msg = super().__str__()
        return f"{base_msg} (Timeout: {self.timeout}s)"


class ConnectionError(HTTPWrapperError):
    """Raised when there's a connection error."""

    def __init__(
        self,
        message: str,
        host: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, details=details)
        self.host = host

    def __str__(self):
        base_msg = super().__str__()
        if self.host:
            return f"{base_msg} (Host: {self.host})"
        return base_msg


class AuthenticationError(HTTPWrapperError):
    """Raised when authentication fails."""

    def __init__(
        self,
        message: str,
        auth_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, details=details)
        self.auth_type = auth_type

    def __str__(self):
        base_msg = super().__str__()
        if self.auth_type:
            return f"{base_msg} (Auth: {self.auth_type})"
        return base_msg


class RateLimitError(HTTPWrapperError):
    """Raised when rate limit is exceeded."""

    def __init__(
        self,
        message: str,
        retry_after: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, details=details)
        self.retry_after = retry_after

    def __str__(self):
        base_msg = super().__str__()
        if self.retry_after:
            return f"{base_msg} (Retry after: {self.retry_after}s)"
        return base_msg
