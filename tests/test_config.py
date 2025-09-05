"""
Tests for Configuration models using Pydantic.
"""

import unittest
from unittest.mock import patch

from pydantic import ValidationError

from httpwrapper.config import (
    BackoffStrategy,
    CacheConfig,
    CircuitBreakerConfig,
    CircuitBreakerState,
    HTTPConfig,
    HTTPMethod,
    HTTPWrapperConfig,
    MetricsConfig,
    RetryConfig,
)


class TestRetryConfig(unittest.TestCase):
    """Test cases for RetryConfig."""

    def test_default_values(self):
        """Test default values for RetryConfig."""
        config = RetryConfig()

        self.assertEqual(config.max_attempts, 3)
        self.assertEqual(config.backoff_factor, 0.3)
        self.assertEqual(config.backoff_strategy, BackoffStrategy.EXPONENTIAL)
        self.assertTrue(config.jitter)
        self.assertEqual(config.retry_on_status_codes, [429, 500, 502, 503, 504])
        self.assertEqual(config.max_delay, 300.0)
        self.assertEqual(config.min_delay, 0.1)

    def test_validation_positive_max_attempts(self):
        """Test that max_attempts must be positive."""
        with self.assertRaises(ValidationError):
            RetryConfig(max_attempts=-1)

    def test_validation_positive_backoff_factor(self):
        """Test that backoff_factor must be positive."""
        with self.assertRaises(ValidationError):
            RetryConfig(backoff_factor=-0.1)

    def test_validation_exception_names(self):
        """Test exception name validation."""
        # Valid exceptions
        valid_config = RetryConfig(retry_on_exceptions=["ValueError", "ConnectionError"])
        self.assertEqual(len(valid_config.retry_on_exceptions), 2)

        # Invalid exceptions (should be filtered out)
        config = RetryConfig(retry_on_exceptions=["InvalidException", "ValueError"])
        # Should contain only valid exceptions
        self.assertIn("ValueError", config.retry_on_exceptions)

    def test_custom_settings(self):
        """Test custom settings."""
        config = RetryConfig(
            max_attempts=5,
            backoff_factor=0.5,
            backoff_strategy=BackoffStrategy.FIXED,
            jitter=False,
            max_delay=60.0
        )
        self.assertEqual(config.max_attempts, 5)
        self.assertEqual(config.backoff_factor, 0.5)
        self.assertEqual(config.backoff_strategy, BackoffStrategy.FIXED)
        self.assertFalse(config.jitter)
        self.assertEqual(config.max_delay, 60.0)


class TestCircuitBreakerConfig(unittest.TestCase):
    """Test cases for CircuitBreakerConfig."""

    def test_default_values(self):
        """Test default values for CircuitBreakerConfig."""
        config = CircuitBreakerConfig()

        self.assertEqual(config.failure_threshold, 5)
        self.assertEqual(config.recovery_timeout, 60.0)
        self.assertEqual(config.success_threshold, 3)

    def test_validation_positive_thresholds(self):
        """Test that thresholds must be positive."""
        with self.assertRaises(ValidationError):
            CircuitBreakerConfig(failure_threshold=-1)

        with self.assertRaises(ValidationError):
            CircuitBreakerConfig(success_threshold=0)

    def test_validation_non_negative_timeout(self):
        """Test that recovery_timeout cannot be negative."""
        with self.assertRaises(ValidationError):
            CircuitBreakerConfig(recovery_timeout=-1)

        # Zero should be allowed for immediate recovery
        config = CircuitBreakerConfig(recovery_timeout=0)
        self.assertEqual(config.recovery_timeout, 0)


class TestHTTPConfig(unittest.TestCase):
    """Test cases for HTTPConfig."""

    def test_default_values(self):
        """Test default values for HTTPConfig."""
        config = HTTPConfig()

        self.assertEqual(config.timeout, (10.0, 30.0))
        self.assertEqual(config.max_redirects, 10)
        self.assertTrue(config.verify_ssl)
        self.assertTrue(config.allow_redirects)
        self.assertIsNone(config.proxies)
        self.assertIn("User-Agent", config.headers)
        self.assertEqual(config.connection_pool_size, 10)
        self.assertEqual(config.connection_pool_maxsize, 20)

    def test_validation_positive_max_redirects(self):
        """Test that max_redirects must be non-negative."""
        with self.assertRaises(ValidationError):
            HTTPConfig(max_redirects=-1)

    def test_validation_positive_connection_settings(self):
        """Test connection pool settings validation."""
        with self.assertRaises(ValidationError):
            HTTPConfig(connection_pool_size=0)

        with self.assertRaises(ValidationError):
            HTTPConfig(connection_pool_maxsize=-1)


class TestCacheConfig(unittest.TestCase):
    """Test cases for CacheConfig."""

    def test_default_values(self):
        """Test default values for CacheConfig."""
        config = CacheConfig()

        self.assertFalse(config.enabled)
        self.assertEqual(config.default_ttl, 300.0)
        self.assertEqual(config.max_size, 1000)
        self.assertTrue(config.include_query_params)
        self.assertFalse(config.include_request_body)
        # Default values are processed through the validator, so they should be lowercase
        self.assertEqual(config.cache_key_headers, ["accept", "accept-language"])

    def test_validation_positive_ttl(self):
        """Test that default_ttl must be non-negative."""
        with self.assertRaises(ValidationError):
            CacheConfig(default_ttl=-1)

        # Zero should be allowed for no caching
        config = CacheConfig(default_ttl=0)
        self.assertEqual(config.default_ttl, 0)

    def test_validation_positive_max_size(self):
        """Test that max_size must be positive."""
        with self.assertRaises(ValidationError):
            CacheConfig(max_size=0)

    def test_header_normalization(self):
        """Test that cache key headers are normalized to lowercase."""
        config = CacheConfig(cache_key_headers=["Accept", "Content-Type", "X-Custom"])
        self.assertEqual(config.cache_key_headers, ["accept", "content-type", "x-custom"])


class TestMetricsConfig(unittest.TestCase):
    """Test cases for MetricsConfig."""

    def test_default_values(self):
        """Test default values for MetricsConfig."""
        config = MetricsConfig()

        self.assertFalse(config.enable_prometheus)
        self.assertEqual(config.metrics_prefix, "httpwrapper")
        self.assertTrue(config.enable_structlog)
        self.assertEqual(config.log_level, "INFO")


class TestHTTPWrapperConfig(unittest.TestCase):
    """Test cases for HTTPWrapperConfig."""

    def test_default_factories(self):
        """Test that default factory configs are created properly."""
        config = HTTPWrapperConfig()

        self.assertIsInstance(config.http_config, HTTPConfig)
        self.assertIsInstance(config.retry_config, RetryConfig)
        self.assertIsInstance(config.circuit_breaker_config, CircuitBreakerConfig)
        self.assertIsInstance(config.cache_config, CacheConfig)
        self.assertIsInstance(config.metrics_config, MetricsConfig)

    def test_custom_configs(self):
        """Test setting custom configs."""
        custom_http = HTTPConfig(timeout=(5.0, 15.0))
        custom_retry = RetryConfig(max_attempts=5)

        config = HTTPWrapperConfig(
            http_config=custom_http,
            retry_config=custom_retry
        )

        self.assertEqual(config.http_config.timeout, (5.0, 15.0))
        self.assertEqual(config.retry_config.max_attempts, 5)

    def test_nested_config_access(self):
        """Test accessing nested configuration."""
        config = HTTPWrapperConfig()
        # Test that we can modify nested configs
        config.retry_config = RetryConfig(max_attempts=10)
        self.assertEqual(config.retry_config.max_attempts, 10)


class TestEnums(unittest.TestCase):
    """Test cases for enums."""

    def test_circuit_breaker_states(self):
        """Test CircuitBreakerState enum."""
        self.assertEqual(CircuitBreakerState.CLOSED.value, "closed")
        self.assertEqual(CircuitBreakerState.OPEN.value, "open")
        self.assertEqual(CircuitBreakerState.HALF_OPEN.value, "half_open")

    def test_backoff_strategies(self):
        """Test BackoffStrategy enum."""
        self.assertEqual(BackoffStrategy.EXPONENTIAL.value, "exponential")
        self.assertEqual(BackoffStrategy.LINEAR.value, "linear")
        self.assertEqual(BackoffStrategy.FIXED.value, "fixed")

    def test_http_methods(self):
        """Test HTTPMethod enum."""
        self.assertEqual(HTTPMethod.GET.value, "GET")
        self.assertEqual(HTTPMethod.POST.value, "POST")
        self.assertEqual(HTTPMethod.PUT.value, "PUT")
        self.assertEqual(HTTPMethod.DELETE.value, "DELETE")


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error handling."""

    def test_empty_config_values(self):
        """Test handling of empty or minimal config values."""
        # Minimal circuit breaker config
        cb_config = CircuitBreakerConfig(failure_threshold=1)
        self.assertEqual(cb_config.failure_threshold, 1)

    def test_empty_exception_list_validation(self):
        """Test that empty exception list raises ValidationError."""
        with self.assertRaises(ValidationError):
            RetryConfig(retry_on_exceptions=[])

    def test_large_values(self):
        """Test handling of large values."""
        config = RetryConfig(max_attempts=100)
        self.assertEqual(config.max_attempts, 100)

        cache_config = CacheConfig(max_size=10000)
        self.assertEqual(cache_config.max_size, 10000)

    @patch('builtins.__import__')
    def test_exception_validation_with_requests_module(self, mock_import):
        """Test exception validation when requests module is available."""
        mock_import.return_value = type('MockModule', (), {'ConnectionError': ConnectionError})()

        config = RetryConfig(retry_on_exceptions=["ConnectionError"])
        # Should not raise ValidationError
        self.assertIsInstance(config, RetryConfig)


if __name__ == '__main__':
    unittest.main()
