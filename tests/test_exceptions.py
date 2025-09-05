"""
Tests for custom exceptions in HTTPWrapper.
"""

import unittest

from httpwrapper.exceptions import (
    AuthenticationError,
    CircuitBreakerError,
    CircuitBreakerOpenError,
    ConfigurationError,
    ConnectionError,
    HTTPWrapperError,
    RateLimitError,
    RetryError,
    TimeoutError,
)


class TestHTTPWrapperError(unittest.TestCase):
    """Test cases for base HTTPWrapperError."""

    def test_basic_exception(self):
        """Test basic exception without optional parameters."""
        error = HTTPWrapperError("Something went wrong")
        self.assertEqual(str(error), "Something went wrong")
        self.assertIsNone(error.status_code)
        self.assertEqual(error.details, {})

    def test_exception_with_status_code(self):
        """Test exception with status code."""
        error = HTTPWrapperError("Not found", status_code=404)
        self.assertEqual(str(error), "Not found (Status: 404)")
        self.assertEqual(error.status_code, 404)

    def test_exception_with_details(self):
        """Test exception with details dictionary."""
        details = {"url": "https://example.com", "method": "GET"}
        error = HTTPWrapperError("Request failed", status_code=500, details=details)
        self.assertEqual(error.details, details)
        self.assertEqual(str(error), "Request failed (Status: 500)")

    def test_exception_with_status_and_details(self):
        """Test exception with status code and details."""
        details = {"component": "circuit_breaker"}
        error = HTTPWrapperError("Service unavailable", status_code=503, details=details)
        self.assertEqual(error.status_code, 503)
        self.assertEqual(error.details, details)
        self.assertEqual(str(error), "Service unavailable (Status: 503)")


class TestRetryError(unittest.TestCase):
    """Test cases for RetryError."""

    def test_basic_retry_error(self):
        """Test basic retry error."""
        error = RetryError("All retries exhausted", attempts=3)
        self.assertEqual(error.attempts, 3)
        self.assertIsNone(error.last_exception)
        self.assertEqual(str(error), "All retries exhausted after 3 attempts")

    def test_retry_error_with_last_exception(self):
        """Test retry error with last exception."""
        last_exc = ValueError("Connection timeout")
        error = RetryError("Retries failed", attempts=5, last_exception=last_exc)
        self.assertEqual(error.attempts, 5)
        self.assertEqual(error.last_exception, last_exc)

    def test_retry_error_with_details(self):
        """Test retry error with details."""
        details = {"last_method": "GET", "last_url": "/api/data"}
        error = RetryError("Server error", attempts=2, details=details)
        self.assertEqual(error.attempts, 2)
        self.assertEqual(error.details, details)


class TestCircuitBreakerError(unittest.TestCase):
    """Test cases for CircuitBreakerError."""

    def test_basic_circuit_breaker_error(self):
        """Test basic circuit breaker error."""
        error = CircuitBreakerError(
            "Circuit breaker activated",
            circuit_breaker_name="api_circuit",
            state="open",
            failures_count=5
        )
        self.assertEqual(error.circuit_breaker_name, "api_circuit")
        self.assertEqual(error.state, "open")
        self.assertEqual(error.failures_count, 5)
        self.assertEqual(str(error), "Circuit breaker activated [Circuit: api_circuit, State: open, Failures: 5]")

    def test_circuit_breaker_error_with_details(self):
        """Test circuit breaker error with details."""
        details = {"service": "database"}
        error = CircuitBreakerError(
            "Overload protection",
            circuit_breaker_name="db_circuit",
            state="half_open",
            failures_count=10,
            details=details
        )
        self.assertEqual(error.details, details)


class TestCircuitBreakerOpenError(unittest.TestCase):
    """Test cases for CircuitBreakerOpenError."""

    def test_basic_circuit_breaker_open_error(self):
        """Test basic circuit breaker open error."""
        error = CircuitBreakerOpenError(
            circuit_breaker_name="payment_circuit",
            failures_count=8,
            last_failure_time=1234567890.123
        )
        self.assertEqual(error.circuit_breaker_name, "payment_circuit")
        self.assertEqual(error.state, "open")
        self.assertEqual(error.failures_count, 8)
        self.assertEqual(error.last_failure_time, 1234567890.123)
        expected_msg = "Circuit breaker 'payment_circuit' is OPEN [Circuit: payment_circuit, State: open, Failures: 8]"
        self.assertEqual(str(error), expected_msg)

    def test_circuit_breaker_open_error_inheritance(self):
        """Test that CircuitBreakerOpenError inherits properly."""
        error = CircuitBreakerOpenError("test_name", 1, 123.0)
        self.assertIsInstance(error, CircuitBreakerError)


class TestConfigurationError(unittest.TestCase):
    """Test cases for ConfigurationError."""

    def test_basic_config_error(self):
        """Test basic configuration error."""
        error = ConfigurationError("Invalid configuration")
        self.assertIsNone(error.config_key)
        self.assertEqual(str(error), "Invalid configuration")

    def test_config_error_with_key(self):
        """Test configuration error with config key."""
        error = ConfigurationError("Missing required field", config_key="api_key")
        self.assertEqual(error.config_key, "api_key")
        self.assertEqual(str(error), "Missing required field (Config: api_key)")

    def test_config_error_with_details(self):
        """Test configuration error with details."""
        details = {"expected_type": "str", "received_type": "int"}
        error = ConfigurationError("Type mismatch", config_key="timeout", details=details)
        self.assertEqual(error.config_key, "timeout")
        self.assertEqual(error.details, details)


class TestTimeoutError(unittest.TestCase):
    """Test cases for TimeoutError."""

    def test_basic_timeout_error(self):
        """Test basic timeout error."""
        error = TimeoutError("Request timed out", timeout=30.0)
        self.assertEqual(error.timeout, 30.0)
        self.assertEqual(str(error), "Request timed out (Timeout: 30.0s)")

    def test_timeout_error_with_details(self):
        """Test timeout error with details."""
        details = {"timeout_type": "connect"}
        error = TimeoutError("Gateway timeout", timeout=60.0, details=details)
        self.assertEqual(error.timeout, 60.0)
        self.assertEqual(error.details, details)


class TestConnectionError(unittest.TestCase):
    """Test cases for ConnectionError."""

    def test_basic_connection_error(self):
        """Test basic connection error."""
        error = ConnectionError("Connection failed")
        self.assertIsNone(error.host)
        self.assertEqual(str(error), "Connection failed")

    def test_connection_error_with_host(self):
        """Test connection error with host."""
        error = ConnectionError("Cannot connect", host="api.example.com")
        self.assertEqual(error.host, "api.example.com")
        self.assertEqual(str(error), "Cannot connect (Host: api.example.com)")

    def test_connection_error_with_details(self):
        """Test connection error with details."""
        details = {"connection_type": "tcp"}
        error = ConnectionError("Network unreachable", host="192.168.1.1", details=details)
        self.assertEqual(error.host, "192.168.1.1")
        self.assertEqual(error.details, details)


class TestAuthenticationError(unittest.TestCase):
    """Test cases for AuthenticationError."""

    def test_basic_auth_error(self):
        """Test basic authentication error."""
        error = AuthenticationError("Authentication failed")
        self.assertIsNone(error.auth_type)
        self.assertEqual(str(error), "Authentication failed")

    def test_auth_error_with_type(self):
        """Test authentication error with auth type."""
        error = AuthenticationError("Invalid token", auth_type="Bearer")
        self.assertEqual(error.auth_type, "Bearer")
        self.assertEqual(str(error), "Invalid token (Auth: Bearer)")

    def test_auth_error_with_details(self):
        """Test authentication error with details."""
        details = {"auth_method": "oauth2"}
        error = AuthenticationError("Unauthorized", auth_type="JWT", details=details)
        self.assertEqual(error.auth_type, "JWT")
        self.assertEqual(error.details, details)


class TestRateLimitError(unittest.TestCase):
    """Test cases for RateLimitError."""

    def test_basic_rate_limit_error(self):
        """Test basic rate limit error."""
        error = RateLimitError("Rate limit exceeded")
        self.assertIsNone(error.retry_after)
        self.assertEqual(str(error), "Rate limit exceeded")

    def test_rate_limit_error_with_retry_after(self):
        """Test rate limit error with retry_after."""
        error = RateLimitError("Too many requests", retry_after=60.0)
        self.assertEqual(error.retry_after, 60.0)
        self.assertEqual(str(error), "Too many requests (Retry after: 60.0s)")

    def test_rate_limit_error_with_details(self):
        """Test rate limit error with details."""
        details = {"limit_type": "daily"}
        error = RateLimitError("API quota exceeded", retry_after=30.0, details=details)
        self.assertEqual(error.retry_after, 30.0)
        self.assertEqual(error.details, details)


class TestExceptionHierarchy(unittest.TestCase):
    """Test exception hierarchy."""

    def test_exception_inheritance(self):
        """Test that custom exceptions inherit from HTTPWrapperError."""
        exceptions = [
            RetryError("test", attempts=1),
            CircuitBreakerError("test", "name", "state", 1),
            CircuitBreakerOpenError("name", 1, 123.0),
            ConfigurationError("test"),
            TimeoutError("test", 1.0),
            ConnectionError("test"),
            AuthenticationError("test"),
            RateLimitError("test"),
        ]
        
        for exc in exceptions:
            with self.subTest(exception=type(exc).__name__):
                self.assertIsInstance(exc, HTTPWrapperError)
                self.assertIsInstance(exc, Exception)

    def test_base_exception_properties(self):
        """Test that all exceptions maintain base exception properties."""
        retry_error = RetryError("test", attempts=1)
        self.assertIsNone(retry_error.status_code)
        self.assertEqual(retry_error.message, "test")
        self.assertEqual(len(retry_error.details), 0)

    def test_exception_details_modification(self):
        """Test that exception details can be modified."""
        error = HTTPWrapperError("test")
        error.details["new_key"] = "new_value"
        self.assertEqual(error.details["new_key"], "new_value")


if __name__ == '__main__':
    unittest.main()
