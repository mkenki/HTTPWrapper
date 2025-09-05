"""
Configuration models for HTTPWrapper using Pydantic for validation and type safety.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field, field_validator, ConfigDict


class CircuitBreakerState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class BackoffStrategy(str, Enum):
    """Available backoff strategies for retry."""
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    FIXED = "fixed"


class HTTPMethod(str, Enum):
    """HTTP methods supported."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class RetryConfig(BaseModel):
    """Configuration for retry behavior."""

    max_attempts: int = Field(default=3, gt=0, description="Maximum number of retry attempts")
    backoff_factor: float = Field(default=0.3, ge=0, description="Backoff factor for exponential backoff")
    backoff_strategy: BackoffStrategy = Field(
        default=BackoffStrategy.EXPONENTIAL,
        description="Backoff strategy to use"
    )
    jitter: bool = Field(default=True, description="Add random jitter to backoff delays")
    retry_on_status_codes: List[int] = Field(
        default=[429, 500, 502, 503, 504],
        description="HTTP status codes that trigger retries"
    )
    retry_on_exceptions: List[str] = Field(
        default=["ConnectionError", "Timeout", "TooManyRedirects"],
        description="Exception types that trigger retries"
    )
    max_delay: float = Field(default=300.0, gt=0, description="Maximum delay between retries")
    min_delay: float = Field(default=0.1, gt=0, description="Minimum delay between retries")

    @field_validator('retry_on_exceptions')
    @classmethod
    def validate_exceptions(cls, v):
        """Validate that exception names are valid Python exception types."""
        import builtins
        valid_exceptions = []
        for exc_name in v:
            if hasattr(builtins, exc_name):
                valid_exceptions.append(exc_name)
            else:
                # Try to import from common modules
                try:
                    __import__('requests.exceptions')
                    if hasattr(__import__('requests.exceptions'), exc_name):
                        valid_exceptions.append(exc_name)
                except (ImportError, AttributeError):
                    continue
        if not valid_exceptions:
            raise ValueError("No valid exception types found")
        return valid_exceptions


class CircuitBreakerConfig(BaseModel):
    """Configuration for circuit breaker behavior."""

    failure_threshold: int = Field(default=5, gt=0, description="Number of failures before opening circuit")
    recovery_timeout: float = Field(default=60.0, ge=0, description="Time in seconds to wait before attempting recovery")
    success_threshold: int = Field(default=3, gt=0, description="Number of successes needed to close circuit in half-open state")
    name: str = Field(default="default", description="Name identifier for the circuit breaker")
    expected_exception: List[str] = Field(
        default=["ConnectionError", "Timeout"],
        description="Exception types that count as failures"
    )

    @field_validator('expected_exception')
    @classmethod
    def validate_expected_exceptions(cls, v):
        """Validate that expected exception names are valid."""
        import builtins
        valid_exceptions = []
        for exc_name in v:
            if hasattr(builtins, exc_name):
                valid_exceptions.append(exc_name)
            else:
                try:
                    __import__('requests.exceptions')
                    if hasattr(__import__('requests.exceptions'), exc_name):
                        valid_exceptions.append(exc_name)
                except (ImportError, AttributeError):
                    continue
        if not valid_exceptions:
            raise ValueError("No valid exception types found for circuit breaker")
        return valid_exceptions


class HTTPConfig(BaseModel):
    """Configuration for HTTP client behavior."""

    timeout: Tuple[float, float] = Field(
        default=(10.0, 30.0),
        description="Connection timeout and read timeout in seconds"
    )
    max_redirects: int = Field(default=10, ge=0, description="Maximum number of redirects to follow")
    verify_ssl: bool = Field(default=True, description="Verify SSL certificates")
    allow_redirects: bool = Field(default=True, description="Allow automatic redirects")
    proxies: Optional[Dict[str, str]] = Field(default=None, description="Proxy configuration")
    headers: Dict[str, str] = Field(
        default_factory=lambda: {
            "User-Agent": "HTTPWrapper/0.1.0",
            "Accept": "*/*",
        },
        description="Default headers to include in requests"
    )
    connection_pool_size: int = Field(default=10, gt=0, description="Size of connection pool")
    connection_pool_maxsize: int = Field(default=20, gt=0, description="Maximum connections in pool")


class CacheConfig(BaseModel):
    """Configuration for response caching."""

    enabled: bool = Field(default=False, description="Enable response caching")
    default_ttl: float = Field(default=300.0, ge=0, description="Default time to live for cache entries in seconds")
    max_size: int = Field(default=1000, gt=0, description="Maximum number of cache entries")
    include_query_params: bool = Field(default=True, description="Include query parameters in cache key")
    include_request_body: bool = Field(default=False, description="Include request body in cache key for write operations")
    cache_key_headers: List[str] = Field(
        default_factory=lambda: ["accept", "accept-language"],
        description="Headers to include in cache key"
    )

    @field_validator('cache_key_headers')
    @classmethod
    def validate_cache_key_headers(cls, v):
        """Normalize header names to lowercase."""
        return [header.lower() for header in v]


class MetricsConfig(BaseModel):
    """Configuration for metrics collection."""

    enable_prometheus: bool = Field(default=False, description="Enable Prometheus metrics collection")
    metrics_prefix: str = Field(default="httpwrapper", description="Prefix for metric names")
    enable_structlog: bool = Field(default=True, description="Enable structured logging")
    log_level: str = Field(default="INFO", description="Logging level")


class HTTPWrapperConfig(BaseModel):
    """Main configuration container for HTTPWrapper."""

    http_config: HTTPConfig = Field(default_factory=HTTPConfig)
    retry_config: RetryConfig = Field(default_factory=RetryConfig)
    circuit_breaker_config: CircuitBreakerConfig = Field(default_factory=CircuitBreakerConfig)
    cache_config: CacheConfig = Field(default_factory=CacheConfig)
    metrics_config: MetricsConfig = Field(default_factory=MetricsConfig)

    model_config = ConfigDict(
        validate_assignment=True
    )
