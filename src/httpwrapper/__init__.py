"""
HTTPWrapper - A resilient HTTP client wrapper with advanced retry mechanisms
and circuit breaker pattern implementation.
"""

import logging
from typing import Any, Dict, List, Optional

from .async_client import AsyncHTTPClient
from .client import HTTPClient
from .config import CacheConfig, CircuitBreakerConfig, HTTPConfig, RetryConfig
from .exceptions import CircuitBreakerError, RetryError

# Set up module-level logger
logger = logging.getLogger(__name__)

__version__ = "0.1.0"
__author__ = "HTTPWrapper Team"
__email__ = "team@httpwrapper.com"

__all__ = [
    "AsyncHTTPClient",
    "HTTPClient",
    "HTTPConfig",
    "RetryConfig",
    "CacheConfig",
    "CircuitBreakerConfig",
    "CircuitBreakerError",
    "RetryError",
    "__version__",
]
