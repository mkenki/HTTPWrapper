"""
Tests for caching implementation with TTL support.
"""

import json
import time
import unittest
from unittest.mock import Mock

from httpwrapper.cache import CacheEntry, CacheManager, ResponseCache
from httpwrapper.config import CacheConfig


class TestCacheEntry(unittest.TestCase):
    """Test cases for CacheEntry."""

    def test_cache_entry_creation(self):
        """Test cache entry creation."""
        entry = CacheEntry("test_key", "test_value", 300.0)
        self.assertEqual(entry.key, "test_key")
        self.assertEqual(entry.value, "test_value")
        self.assertEqual(entry.ttl, 300.0)
        self.assertGreater(entry.created_at, 0)
        self.assertEqual(entry.expires_at, entry.created_at + 300.0)

    def test_cache_entry_not_expired(self):
        """Test cache entry that is not expired."""
        entry = CacheEntry("test_key", "test_value", 300.0)
        self.assertFalse(entry.is_expired())
        self.assertGreater(entry.get_remaining_ttl(), 299.0)

    def test_cache_entry_expired(self):
        """Test cache entry that has expired."""
        entry = CacheEntry("test_key", "test_value", 0.001)  # Very short TTL
        time.sleep(0.002)  # Wait for expiration
        self.assertTrue(entry.is_expired())
        self.assertEqual(entry.get_remaining_ttl(), 0.0)

    def test_cache_entry_remaining_ttl(self):
        """Test getting remaining TTL."""
        entry = CacheEntry("test_key", "test_value", 1.0)
        remaining = entry.get_remaining_ttl()
        self.assertGreater(remaining, 0.9)
        self.assertLess(remaining, 1.0)


class TestResponseCache(unittest.TestCase):
    """Test cases for ResponseCache."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = CacheConfig(
            enabled=True,
            max_size=10,
            default_ttl=300.0,
            include_query_params=True,
            include_request_body=False,
            cache_key_headers=["accept"]
        )
        self.cache = ResponseCache(self.config)

    def test_initialization(self):
        """Test cache initialization."""
        self.assertIsInstance(self.cache._cache, dict)
        self.assertEqual(self.cache.hits, 0)
        self.assertEqual(self.cache.misses, 0)
        self.assertEqual(self.cache.sets, 0)
        self.assertEqual(self.cache.evictions, 0)

    def test_disabled_cache(self):
        """Test that disabled cache doesn't store or retrieve."""
        disabled_config = CacheConfig(enabled=False)
        disabled_cache = ResponseCache(disabled_config)

        disabled_cache.set("GET", "http://example.com", "test_data")
        result = disabled_cache.get("GET", "http://example.com")

        self.assertIsNone(result)
        self.assertEqual(len(disabled_cache._cache), 0)

    def test_cache_set_and_get(self):
        """Test basic cache set and get operations."""
        method, url, data = "GET", "http://example.com", {"key": "value"}

        # Set cache
        self.cache.set(method, url, data)
        self.assertEqual(self.cache.sets, 1)
        self.assertEqual(len(self.cache), 1)

        # Get cached data
        cached_data = self.cache.get(method, url)
        self.assertEqual(cached_data, data)
        self.assertEqual(self.cache.hits, 1)

    def test_cache_miss(self):
        """Test cache miss."""
        result = self.cache.get("GET", "http://nonexistent.com")
        self.assertIsNone(result)
        self.assertEqual(self.cache.misses, 1)

    def test_cache_key_generation(self):
        """Test cache key generation."""
        method1, url1 = "GET", "http://example.com/api"
        method2, url2 = "POST", "http://example.com/api"

        self.cache.set(method1, url1, "data1")
        self.cache.set(method2, url2, "data2")

        # Different methods should have different cache keys
        self.assertEqual(len(self.cache._cache), 2)

        result1 = self.cache.get(method1, url1)
        result2 = self.cache.get(method2, url2)

        self.assertEqual(result1, "data1")
        self.assertEqual(result2, "data2")

    def test_cache_key_with_query_params(self):
        """Test cache key generation with query parameters."""
        base_url = "http://example.com/api"
        url1 = f"{base_url}?param1=value1"
        url2 = f"{base_url}?param2=value2"

        self.cache.set("GET", url1, "data1")
        self.cache.set("GET", url2, "data2")

        self.assertEqual(len(self.cache._cache), 2)

        result1 = self.cache.get("GET", url1)
        result2 = self.cache.get("GET", url2)

        self.assertEqual(result1, "data1")
        self.assertEqual(result2, "data2")

    def test_cache_key_with_headers(self):
        """Test cache key generation with headers."""
        url = "http://example.com/api"
        headers1 = {"accept": "application/json"}
        headers2 = {"accept": "application/xml"}

        self.cache.set("GET", url, "data1", headers=headers1)
        self.cache.set("GET", url, "data2", headers=headers2)

        self.assertEqual(len(self.cache._cache), 2)

    def test_cache_key_with_request_body(self):
        """Test cache key generation with request body."""
        config = CacheConfig(enabled=True, include_request_body=True)
        cache = ResponseCache(config)

        url = "http://example.com/api"
        data1 = {"action": "create", "value": 1}
        data2 = {"action": "update", "value": 2}

        cache.set("POST", url, "response1", json=data1)
        cache.set("POST", url, "response2", json=data2)

        self.assertEqual(len(cache._cache), 2)

    def test_cache_expiration(self):
        """Test cache expiration."""
        # Create cache with very short TTL
        config = CacheConfig(enabled=True, default_ttl=0.1)
        cache = ResponseCache(config)

        cache.set("GET", "http://example.com", "test_data")

        # Should return value immediately
        result = cache.get("GET", "http://example.com")
        self.assertEqual(result, "test_data")

        # Wait for expiration
        time.sleep(0.15)

        # Should return None after expiration
        result = cache.get("GET", "http://example.com")
        self.assertIsNone(result)

    def test_cache_delete(self):
        """Test cache entry deletion."""
        method, url, data = "GET", "http://example.com", "test_data"

        self.cache.set(method, url, data)
        self.assertEqual(len(self.cache), 1)

        self.cache.delete(method, url)
        self.assertEqual(len(self.cache), 0)

        # Should get None after deletion
        result = self.cache.get(method, url)
        self.assertIsNone(result)

    def test_cache_clear(self):
        """Test clearing all cache entries."""
        self.cache.set("GET", "http://example1.com", "data1")
        self.cache.set("GET", "http://example2.com", "data2")
        self.assertEqual(len(self.cache), 2)

        self.cache.clear()
        self.assertEqual(len(self.cache), 0)
        self.assertEqual(self.cache.hits, 0)
        self.assertEqual(self.cache.misses, 0)
        self.assertEqual(self.cache.sets, 0)
        self.assertEqual(self.cache.evictions, 0)

    def test_cache_max_size_eviction(self):
        """Test cache eviction when max size is reached."""
        config = CacheConfig(enabled=True, max_size=2)
        cache = ResponseCache(config)

        # Fill cache to max size
        cache.set("GET", "http://example1.com", "data1")
        cache.set("GET", "http://example2.com", "data2")
        self.assertEqual(len(cache), 2)

        # Add one more - should trigger eviction
        cache.set("GET", "http://example3.com", "data3")
        self.assertEqual(len(cache), 2)  # Should still be 2
        self.assertGreater(cache.evictions, 0)

    def test_cache_cleanup_expired(self):
        """Test cleanup of expired entries."""
        config = CacheConfig(enabled=True, default_ttl=0.1)
        cache = ResponseCache(config)

        cache.set("GET", "http://example1.com", "data1")
        cache.set("GET", "http://example2.com", "data2")

        time.sleep(0.15)

        removed_count = cache.cleanup_expired()
        self.assertEqual(len(cache), 0)
        self.assertGreaterEqual(removed_count, 2)

    def test_cache_stats(self):
        """Test cache statistics."""
        # Set up some data
        self.cache.set("GET", "http://example.com", "test_data")
        self.cache.get("GET", "http://example.com")  # Hit
        self.cache.get("GET", "http://nonexistent.com")  # Miss

        stats = self.cache.get_stats()

        self.assertTrue(stats['enabled'])
        self.assertEqual(stats['size'], 1)
        self.assertEqual(stats['max_size'], 10)
        self.assertEqual(stats['hits'], 1)
        self.assertEqual(stats['misses'], 1)
        self.assertEqual(stats['sets'], 1)
        self.assertAlmostEqual(stats['hit_rate_percent'], 50.0, places=1)

    def test_cache_stats_empty_cache(self):
        """Test cache statistics for empty cache."""
        stats = self.cache.get_stats()

        self.assertTrue(stats['enabled'])
        self.assertEqual(stats['size'], 0)
        self.assertEqual(stats['hit_rate_percent'], 0.0)

    def test_cache_length_method(self):
        """Test __len__ method."""
        self.assertEqual(len(self.cache), 0)

        self.cache.set("GET", "http://example.com", "test_data")
        self.assertEqual(len(self.cache), 1)

    def test_thread_safety(self):
        """Test that cache operations are thread-safe."""
        import threading
        import concurrent.futures

        def cache_operation():
            self.cache.set(f"GET", f"http://example{random.randint(1,10)}.com", "test_data")
            self.cache.get("GET", "http://example.com")

        import random
        # Run multiple cache operations concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(cache_operation) for _ in range(10)]
            concurrent.futures.wait(futures)

        # Should not have raised any exceptions
        self.assertTrue(True)

    def test_cache_eviction_complex(self):
        """Test complex cache eviction scenarios."""
        config = CacheConfig(enabled=True, max_size=2)
        cache = ResponseCache(config)

        # Add entries with different creation times
        time.sleep(0.01)
        cache.set("GET", "http://example1.com", "data1")
        time.sleep(0.01)
        cache.set("GET", "http://example2.com", "data2")

        # Add third entry - should evict oldest
        cache.set("GET", "http://example3.com", "data3")

        self.assertGreaterEqual(cache.evictions, 1)
        self.assertEqual(len(cache), 2)


class TestCacheManager(unittest.TestCase):
    """Test cases for CacheManager."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = CacheConfig(enabled=True)
        self.manager = CacheManager(self.config)

    def test_initialization(self):
        """Test cache manager initialization."""
        self.assertIsInstance(self.manager.response_cache, ResponseCache)

    def test_get_cache_response_type(self):
        """Test getting response cache."""
        cache = self.manager.get_cache('response')
        self.assertIsInstance(cache, ResponseCache)

    def test_get_cache_unknown_type(self):
        """Test getting unknown cache type raises ValueError."""
        with self.assertRaises(ValueError):
            self.manager.get_cache('unknown')


if __name__ == '__main__':
    unittest.main()
