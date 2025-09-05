"""
Response caching implementation with TTL support.
"""

import hashlib
import json
import threading
import time
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from .config import CacheConfig


class CacheEntry:
    """Represents a cached response entry."""

    def __init__(self, key: str, value: Any, ttl: float):
        """
        Initialize cache entry.

        Args:
            key: Cache key
            value: Cached value
            ttl: Time to live in seconds
        """
        self.key = key
        self.value = value
        self.created_at = time.time()
        self.ttl = ttl
        self.expires_at = self.created_at + ttl

    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        return time.time() > self.expires_at

    def get_remaining_ttl(self) -> float:
        """Get remaining TTL in seconds."""
        return max(0, self.expires_at - time.time())


class ResponseCache:
    """
    Simple in-memory response cache with TTL support.

    Features:
    - TTL-based expiration
    - Thread-safe operations
    - Configurable max size
    - LRU eviction when full
    - Cache statistics
    """

    def __init__(self, config: CacheConfig):
        """
        Initialize response cache.

        Args:
            config: Cache configuration
        """
        self.config = config
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()

        # Statistics
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.sets = 0

    def _generate_key(self, method: str, url: str, **kwargs: Any) -> str:
        """
        Generate a unique cache key for the request.

        Args:
            method: HTTP method
            url: Request URL
            **kwargs: Additional request parameters that affect caching

        Returns:
            Cache key string
        """
        # Include relevant parameters in key generation
        key_parts = [method.upper(), url]

        # Include query parameters if configured
        parsed_url = urlparse(url)
        if parsed_url.query and self.config.include_query_params:
            key_parts.append(parsed_url.query)

        # Include specific headers if configured
        if self.config.cache_key_headers:
            headers = kwargs.get('headers', {})
            for header in self.config.cache_key_headers:
                if header in headers:
                    key_parts.append(f"{header}:{headers[header]}")

        # Include request body for POST/PUT/PATCH if configured
        if method.upper() in ['POST', 'PUT', 'PATCH'] and self.config.include_request_body:
            data = kwargs.get('data', kwargs.get('json', ''))
            if data:
                if isinstance(data, dict):
                    data = json.dumps(data, sort_keys=True)
                key_parts.append(str(data))

        # Create hash of the key parts
        key_string = '|'.join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()

    def get(self, method: str, url: str, **kwargs: Any) -> Optional[Any]:
        """
        Get cached response if available and not expired.

        Args:
            method: HTTP method
            url: Request URL
            **kwargs: Additional request parameters

        Returns:
            Cached response or None if not found/expired
        """
        if not self.config.enabled:
            return None

        key = self._generate_key(method, url, **kwargs)

        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self.misses += 1
                return None

            if entry.is_expired():
                # Remove expired entry
                del self._cache[key]
                self.misses += 1
                return None

            self.hits += 1
            return entry.value

    def set(self, method: str, url: str, value: Any, **kwargs: Any) -> None:
        """
        Cache a response.

        Args:
            method: HTTP method
            url: Request URL
            value: Response to cache
            **kwargs: Additional request parameters
        """
        if not self.config.enabled:
            return

        key = self._generate_key(method, url, **kwargs)

        with self._lock:
            # Check if we need to evict old entries
            if len(self._cache) >= self.config.max_size:
                self._evict_lru()

            # Create new entry
            entry = CacheEntry(key, value, self.config.default_ttl)
            self._cache[key] = entry
            self.sets += 1

    def delete(self, method: str, url: str, **kwargs: Any) -> None:
        """
        Delete a cached response.

        Args:
            method: HTTP method
            url: Request URL
            **kwargs: Additional request parameters
        """
        key = self._generate_key(method, url, **kwargs)

        with self._lock:
            if key in self._cache:
                del self._cache[key]

    def clear(self) -> None:
        """Clear all cached responses."""
        with self._lock:
            self._cache.clear()
            self.hits = 0
            self.misses = 0
            self.evictions = 0
            self.sets = 0

    def _evict_lru(self) -> None:
        """Evict least recently used entries when cache is full."""
        if not self._cache:
            return

        # Simple LRU: evict a few expired entries first
        expired_keys = [k for k, v in self._cache.items() if v.is_expired()]
        for key in expired_keys:
            del self._cache[key]
            self.evictions += 1

        # If still full, evict oldest entries
        if len(self._cache) >= self.config.max_size:
            # Get entries sorted by creation time (oldest first)
            sorted_entries = sorted(
                self._cache.items(),
                key=lambda x: x[1].created_at
            )

            # Evict oldest 10% of entries or at least 1
            evict_count = max(1, len(self._cache) // 10)
            for i in range(evict_count):
                del self._cache[sorted_entries[i][0]]
                self.evictions += 1

    def cleanup_expired(self) -> int:
        """
        Remove all expired entries from cache.

        Returns:
            Number of expired entries removed
        """
        with self._lock:
            expired_keys = [k for k, v in self._cache.items() if v.is_expired()]
            for key in expired_keys:
                del self._cache[key]

            self.evictions += len(expired_keys)
            return len(expired_keys)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        with self._lock:
            total_requests = self.hits + self.misses
            hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0

            return {
                'enabled': self.config.enabled,
                'size': len(self._cache),
                'max_size': self.config.max_size,
                'hit_rate_percent': round(hit_rate, 2),
                'hits': self.hits,
                'misses': self.misses,
                'sets': self.sets,
                'evictions': self.evictions,
                'default_ttl': self.config.default_ttl,
            }

    def __len__(self) -> int:
        """Return current cache size."""
        return len(self._cache)


class CacheManager:
    """
    Manages multiple caches for different purposes.
    """

    def __init__(self, config: CacheConfig):
        """
        Initialize cache manager.

        Args:
            config: Cache configuration
        """
        self.response_cache = ResponseCache(config)

    def get_cache(self, cache_type: str = 'response') -> ResponseCache:
        """
        Get a specific cache instance.

        Args:
            cache_type: Type of cache to retrieve

        Returns:
            Cache instance
        """
        if cache_type == 'response':
            return self.response_cache
        else:
            raise ValueError(f"Unknown cache type: {cache_type}")
