"""
Asynchronous HTTP client wrapper with retry and circuit breaker functionality.
"""

import asyncio
import time
from typing import Any, Dict, Optional, Union
from urllib.parse import urlparse

import aiohttp
from aiohttp import ClientResponse as AsyncResponse

from .cache import CacheManager
from .config import (
    CacheConfig,
    CircuitBreakerConfig,
    CircuitBreakerState,
    HTTPConfig,
    RetryConfig,
)
from .exceptions import (
    CircuitBreakerOpenError,
    RetryError,
)
from .circuit_breaker import CircuitBreaker
from .retry_manager import RetryManager
from .metrics_collector import MetricsCollector


class AsyncHTTPClient:
    """
    Asynchronous HTTP client wrapper with retry and circuit breaker patterns.

    Provides resilient HTTP requests with automatic retries, exponential backoff,
    and circuit breaker protection against failing services.
    """

    def __init__(
        self,
        retry_config: Optional[RetryConfig] = None,
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
        http_config: Optional[HTTPConfig] = None,
        cache_config: Optional[CacheConfig] = None,
        session: Optional[aiohttp.ClientSession] = None,
    ):
        """
        Initialize the asynchronous HTTP client.

        Args:
            retry_config: Configuration for retry behavior
            circuit_breaker_config: Configuration for circuit breaker
            http_config: Configuration for HTTP client behavior
            cache_config: Configuration for response caching
            session: Custom aiohttp session to use
        """
        # Create default configurations if not provided
        self.retry_config = retry_config or RetryConfig()
        self.circuit_breaker_config = circuit_breaker_config or CircuitBreakerConfig()
        self.http_config = http_config or HTTPConfig()
        self.cache_config = cache_config or CacheConfig()

        # Initialize core components
        self.session = session  # Session will be created in context manager
        self.session_owner = session is None
        self.circuit_breaker = CircuitBreaker(self.circuit_breaker_config)
        self.retry_manager = RetryManager(self.retry_config)
        self.metrics = MetricsCollector()
        self.cache = CacheManager(self.cache_config)

        # Session creation lock for thread safety
        self._session_lock = asyncio.Lock()

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None:
            async with self._session_lock:
                if self.session is None:
                    # Create connector with connection pooling
                    connector = aiohttp.TCPConnector(
                        limit=self.http_config.connection_pool_maxsize,
                        limit_per_host=self.http_config.connection_pool_size,
                        ttl_dns_cache=300,  # 5 minutes DNS cache
                        use_dns_cache=True,
                    )

                    # Create timeout object
                    timeout = aiohttp.ClientTimeout(
                        total=self.http_config.timeout[1],  # Read timeout
                        connect=self.http_config.timeout[0],  # Connect timeout
                    )

                    self.session = aiohttp.ClientSession(
                        connector=connector,
                        timeout=timeout,
                        headers=self.http_config.headers,
                        trust_env=True,  # Use environment proxy settings
                    )
        return self.session

    def _should_retry(self, response: Optional[AsyncResponse], exception: Optional[Exception]) -> bool:
        """
        Determine if a request should be retried based on response or exception.

        Args:
            response: HTTP response object
            exception: Exception that occurred

        Returns:
            True if the request should be retried
        """
        # Check HTTP status codes
        if response and response.status in self.retry_config.retry_on_status_codes:
            return True

        # Check exceptions
        if exception:
            exception_name = type(exception).__name__
            if exception_name in self.retry_config.retry_on_exceptions:
                return True

        return False

    async def _execute_request(
        self,
        method: str,
        url: str,
        **kwargs: Any
    ) -> AsyncResponse:
        """
        Execute a single HTTP request.

        Args:
            method: HTTP method
            url: Request URL
            **kwargs: Additional request parameters

        Returns:
            Response object
        """
        # Extract host for circuit breaker identification
        parsed_url = urlparse(url)
        host = parsed_url.netloc or url

        # Check circuit breaker state
        if not self.circuit_breaker.can_proceed(host):
            self.metrics.record_circuit_breaker_rejection(host)
            raise CircuitBreakerOpenError(
                circuit_breaker_name=host,
                failures_count=self.circuit_breaker.failure_count(host),
                last_failure_time=self.circuit_breaker.last_failure_time(host),
            )

        # Check cache for GET/HEAD requests
        if method.upper() in ['GET', 'HEAD'] and self.cache_config.enabled:
            cached_response = self.cache.response_cache.get(method, url, **kwargs)
            if cached_response is not None:
                # Record cache hit metric
                self.metrics.record_request(
                    method=method,
                    url=url,
                    status_code=cached_response.status,
                    duration=0.0  # No actual request made
                )
                return cached_response

        session = await self._get_session()
        # Make the request
        start_time = time.time()
        try:
            async with session.request(method, url, **kwargs) as response:
                # Read response to ensure it's fully consumed
                await response.read()

                request_time = time.time() - start_time

                # Record metrics
                self.metrics.record_request(
                    method=method,
                    url=url,
                    status_code=response.status,
                    duration=request_time
                )

                # Record success in circuit breaker
                self.circuit_breaker.record_success(host)

                # Cache successful GET/HEAD responses
                if (method.upper() in ['GET', 'HEAD'] and
                    self.cache_config.enabled and
                    200 <= response.status < 300):
                    self.cache.response_cache.set(method, url, response, **kwargs)

                # Invalidate cache for write operations
                elif method.upper() in ['POST', 'PUT', 'PATCH', 'DELETE']:
                    if self.cache_config.enabled:
                        # For specific resource operations, we could be more selective
                        # For now, just invalidate any cached entries for this URL
                        self.cache.response_cache.delete(method, url, **kwargs)

                return response

        except Exception as e:
            request_time = time.time() - start_time

            # Record metrics
            self.metrics.record_error(
                method=method,
                url=url,
                exception=e,
                duration=request_time
            )

            # Record failure in circuit breaker
            self.circuit_breaker.record_failure(host)

            raise

    async def request(
        self,
        method: str,
        url: str,
        retry_on_failure: bool = True,
        **kwargs: Any
    ) -> AsyncResponse:
        """
        Make an HTTP request with retry and circuit breaker logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            retry_on_failure: Whether to retry on failures
            **kwargs: Additional request parameters

        Returns:
            Response object

        Raises:
            RetryError: When all retry attempts are exhausted
            CircuitBreakerOpenError: When circuit breaker is open
        """
        if not retry_on_failure:
            return await self._execute_request(method, url, **kwargs)

        last_exception = None

        for attempt in range(self.retry_config.max_attempts):
            try:
                return await self._execute_request(method, url, **kwargs)

            except (aiohttp.ClientError, CircuitBreakerOpenError) as e:
                last_exception = e

                # Don't retry circuit breaker errors
                if isinstance(e, CircuitBreakerOpenError):
                    self.metrics.record_retry_aborted(method, url, attempt + 1)
                    raise

                # Check if we should retry
                if attempt < self.retry_config.max_attempts - 1 and self._should_retry(None, e):
                    delay = self.retry_manager.calculate_delay(attempt)
                    self.metrics.record_retry_attempt(method, url, attempt + 1, delay)
                    await asyncio.sleep(delay)
                    continue
                else:
                    # No more retries or shouldn't retry
                    break

        # All retries exhausted
        self.metrics.record_retry_exhausted(method, url, self.retry_config.max_attempts)
        raise RetryError(
            f"Request failed after {self.retry_config.max_attempts} attempts",
            attempts=self.retry_config.max_attempts,
            last_exception=last_exception,
        )

    async def get(self, url: str, **kwargs: Any) -> AsyncResponse:
        """Make a GET request."""
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> AsyncResponse:
        """Make a POST request."""
        return await self.request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs: Any) -> AsyncResponse:
        """Make a PUT request."""
        return await self.request("PUT", url, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> AsyncResponse:
        """Make a DELETE request."""
        return await self.request("DELETE", url, **kwargs)

    async def patch(self, url: str, **kwargs: Any) -> AsyncResponse:
        """Make a PATCH request."""
        return await self.request("PATCH", url, **kwargs)

    async def head(self, url: str, **kwargs: Any) -> AsyncResponse:
        """Make a HEAD request."""
        return await self.request("HEAD", url, **kwargs)

    async def options(self, url: str, **kwargs: Any) -> AsyncResponse:
        """Make an OPTIONS request."""
        return await self.request("OPTIONS", url, **kwargs)

    def get_circuit_breaker_state(self, host: str) -> CircuitBreakerState:
        """
        Get the current state of the circuit breaker for a host.

        Args:
            host: Host name

        Returns:
            Circuit breaker state
        """
        return self.circuit_breaker.get_state(host)

    async def areset_circuit_breaker(self, host: str) -> None:
        """
        Asynchronously reset the circuit breaker for a host.

        Args:
            host: Host name
        """
        self.circuit_breaker.reset(host)
        self.metrics.record_circuit_breaker_reset(host)

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current metrics for the client.

        Returns:
            Dictionary containing metrics data
        """
        return self.metrics.get_metrics()

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary containing cache statistics
        """
        return self.cache.response_cache.get_stats()

    def clear_cache(self) -> None:
        """
        Clear all cached responses.
        """
        self.cache.response_cache.clear()

    def cache_cleanup_expired(self) -> int:
        """
        Clean up expired cache entries.

        Returns:
            Number of expired entries removed
        """
        return self.cache.response_cache.cleanup_expired()

    async def aclose(self) -> None:
        """Asynchronously close the HTTP client and clean up resources."""
        async with self._session_lock:
            if self.session and self.session_owner:
                await self.session.close()
                self.session = None

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.aclose()
