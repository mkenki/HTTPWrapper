"""
Performance Benchmark for HTTPWrapper.

This script benchmarks various aspects of HTTPWrapper performance including:
- Basic request handling
- Caching performance
- Circuit breaker overhead
- Retry mechanism efficiency
- Memory usage patterns
"""

import asyncio
import time
import tracemalloc
from typing import Dict, List, Any
import statistics
from concurrent.futures import ThreadPoolExecutor
import requests
from unittest.mock import Mock, patch

from httpwrapper.config import HTTPWrapperConfig, CacheConfig
from httpwrapper.client import HTTPClient
from httpwrapper.async_client import AsyncHTTPClient


class PerformanceBenchmark:
    """Performance benchmarking suite for HTTPWrapper."""

    def __init__(self):
        """Initialize benchmark suite."""
        self.results = {}

    def run_all_benchmarks(self) -> Dict[str, Any]:
        """Run all benchmarking tests."""
        print("Running HTTPWrapper Performance Benchmarks...\n")

        # Initialize results
        results = {}

        # Run synchronous benchmarks
        results.update(self.benchmark_basic_requests())
        results.update(self.benchmark_caching())
        results.update(self.benchmark_circuit_breaker())
        results.update(self.benchmark_retry_mechanism())
        results.update(self.benchmark_memory_usage())

        # Run asynchronous benchmarks
        results.update(asyncio.run(self.benchmark_async_requests()))
        results.update(asyncio.run(self.benchmark_concurrent_requests()))

        self.results = results
        return results

    def benchmark_basic_requests(self) -> Dict[str, Any]:
        """Benchmark basic HTTP request handling."""
        print("📊 Benchmarking basic requests...")

        config = HTTPWrapperConfig()
        client = HTTPClient(
            retry_config=config.retry_config,
            circuit_breaker_config=config.circuit_breaker_config,
            http_config=config.http_config,
            cache_config=config.cache_config
        )

        # Mock a simple response
        with patch('requests.Session.request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"success": True}
            mock_request.return_value = mock_response

            # Benchmark multiple requests
            num_requests = 1000
            start_time = time.time()

            for _ in range(num_requests):
                client.get("http://example.com/api")

            end_time = time.time()

            req_per_sec = num_requests / (end_time - start_time)

            return {
                "basic_requests": {
                    "requests_per_second": req_per_sec,
                    "total_requests": num_requests,
                    "total_time": end_time - start_time,
                    "avg_response_time": (end_time - start_time) / num_requests * 1000  # ms
                }
            }

    async def benchmark_async_requests(self) -> Dict[str, Any]:
        """Benchmark asynchronous request handling."""
        print("📊 Benchmarking async requests...")

        config = HTTPWrapperConfig()
        async_client = AsyncHTTPClient(
            retry_config=config.retry_config,
            circuit_breaker_config=config.circuit_breaker_config,
            http_config=config.http_config,
            cache_config=config.cache_config
        )

        # Mock async response
        async def mock_async_request(*args, **kwargs):
            await asyncio.sleep(0.001)  # Small delay to simulate network
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"success": True}
            return mock_response

        with patch.object(async_client.session, 'request', side_effect=mock_async_request):
            # Benchmark async requests
            num_requests = 1000
            start_time = time.time()

            tasks = []
            for _ in range(num_requests):
                tasks.append(async_client.get("http://example.com/api"))

            await asyncio.gather(*tasks)

            end_time = time.time()

            req_per_sec = num_requests / (end_time - start_time)

            return {
                "async_requests": {
                    "requests_per_second": req_per_sec,
                    "total_requests": num_requests,
                    "total_time": end_time - start_time,
                    "avg_response_time": (end_time - start_time) / num_requests * 1000  # ms
                }
            }

    async def benchmark_concurrent_requests(self) -> Dict[str, Any]:
        """Benchmark concurrent request handling."""
        print("📊 Benchmarking concurrent requests...")

        config = HTTPWrapperConfig()
        async_client = AsyncHTTPClient(
            retry_config=config.retry_config,
            circuit_breaker_config=config.circuit_breaker_config,
            http_config=config.http_config,
            cache_config=config.cache_config
        )

        # Mock async response
        async def mock_async_request(*args, **kwargs):
            await asyncio.sleep(0.01)  # Simulate network delay
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"success": True}
            return mock_response

        with patch.object(async_client.session, 'request', side_effect=mock_async_request):
            # Benchmark concurrent requests
            concurrent_levels = [10, 50, 100]
            results = {}

            for concurrent in concurrent_levels:
                start_time = time.time()

                # Create batches of concurrent requests
                for batch in range(0, 500, concurrent):
                    tasks = []
                    batch_size = min(concurrent, 500 - batch)

                    for _ in range(batch_size):
                        tasks.append(async_client.get("http://example.com/api"))

                    await asyncio.gather(*tasks)

                end_time = time.time()

                total_requests = 500
                req_per_sec = total_requests / (end_time - start_time)

                results[f"concurrent_{concurrent}"] = {
                    "concurrent_requests": concurrent,
                    "requests_per_second": req_per_sec,
                    "total_requests": total_requests,
                    "total_time": end_time - start_time
                }

            return {"concurrent_performance": results}

    def benchmark_caching(self) -> Dict[str, Any]:
        """Benchmark caching performance."""
        print("📊 Benchmarking caching performance...")

        # Benchmark with cache enabled
        cache_config = CacheConfig(enabled=True, max_size=1000)
        config_with_cache = HTTPWrapperConfig(cache_config=cache_config)
        client_with_cache = HTTPClient(
            retry_config=config_with_cache.retry_config,
            circuit_breaker_config=config_with_cache.circuit_breaker_config,
            http_config=config_with_cache.http_config,
            cache_config=config_with_cache.cache_config
        )

        # Benchmark without cache
        config_no_cache = HTTPWrapperConfig()
        client_no_cache = HTTPClient(
            retry_config=config_no_cache.retry_config,
            circuit_breaker_config=config_no_cache.circuit_breaker_config,
            http_config=config_no_cache.http_config,
            cache_config=config_no_cache.cache_config
        )

        # Mock responses
        with patch('requests.Session.request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"success": True}
            mock_request.return_value = mock_response

            num_requests = 1000
            url = "http://example.com/api"

            # Test without cache
            start_time = time.time()
            for _ in range(num_requests):
                client_no_cache.get(url)
            no_cache_time = time.time() - start_time

            # Test with cache (first requests will cache, subsequent will hit cache)
            start_time = time.time()
            for _ in range(num_requests):
                client_with_cache.get(url)
            cache_time = time.time() - start_time

            return {
                "caching_performance": {
                    "no_cache_time": no_cache_time,
                    "cache_time": cache_time,
                    "speedup_ratio": no_cache_time / cache_time if cache_time > 0 else 1,
                    "requests_per_second_no_cache": num_requests / no_cache_time,
                    "requests_per_second_with_cache": num_requests / cache_time
                }
            }

    def benchmark_circuit_breaker(self) -> Dict[str, Any]:
        """Benchmark circuit breaker overhead."""
        print("📊 Benchmarking circuit breaker overhead...")

        # Standard config
        config_standard = HTTPWrapperConfig()
        client_standard = HTTPClient(
            retry_config=config_standard.retry_config,
            circuit_breaker_config=config_standard.circuit_breaker_config,
            http_config=config_standard.http_config,
            cache_config=config_standard.cache_config
        )

        # Config with circuit breaker
        config_cb = HTTPWrapperConfig()
        # Circuit breaker would be used, but we don't want it to trigger
        client_cb = HTTPClient(
            retry_config=config_cb.retry_config,
            circuit_breaker_config=config_cb.circuit_breaker_config,
            http_config=config_cb.http_config,
            cache_config=config_cb.cache_config
        )

        with patch('requests.Session.request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"success": True}
            mock_request.return_value = mock_response

            num_requests = 1000
            url = "http://example.com/api"

            # Test standard client
            start_time = time.time()
            for _ in range(num_requests):
                client_standard.get(url)
            standard_time = time.time() - start_time

            # Test with circuit breaker
            start_time = time.time()
            for _ in range(num_requests):
                client_cb.get(url)
            cb_time = time.time() - start_time

            overhead_percentage = ((cb_time - standard_time) / standard_time) * 100

            return {
                "circuit_breaker_overhead": {
                    "standard_time": standard_time,
                    "circuit_breaker_time": cb_time,
                    "overhead_percentage": overhead_percentage,
                    "overhead_ms_per_request": (cb_time - standard_time) / num_requests * 1000
                }
            }

    def benchmark_retry_mechanism(self) -> Dict[str, Any]:
        """Benchmark retry mechanism performance."""
        print("📊 Benchmarking retry mechanism...")

        # Config with retries
        config = HTTPWrapperConfig()
        client = HTTPClient(
            retry_config=config.retry_config,
            circuit_breaker_config=config.circuit_breaker_config,
            http_config=config.http_config,
            cache_config=config.cache_config
        )

        # Mock responses that fail then succeed
        call_count = 0
        def mock_failing_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_response = Mock()

            if call_count % 3 == 0:  # Every 3rd call succeeds
                mock_response.status_code = 200
                mock_response.json.return_value = {"success": True}
            else:  # Fail with 500 error
                mock_response.status_code = 500
                mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")

            return mock_response

        with patch('requests.Session.request', side_effect=mock_failing_request):
            num_requests = 300  # This will result in retries
            start_time = time.time()

            successful_requests = 0
            for _ in range(num_requests):
                try:
                    client.get("http://example.com/api")
                    successful_requests += 1
                except Exception:
                    pass  # Expected failures

            end_time = time.time()

            return {
                "retry_performance": {
                    "total_time": end_time - start_time,
                    "successful_requests": successful_requests,
                    "total_api_calls": call_count,  # Includes retries
                    "retries_per_successful_request": (call_count / successful_requests) - 1 if successful_requests > 0 else 0,
                    "requests_per_second": successful_requests / (end_time - start_time)
                }
            }

    def benchmark_memory_usage(self) -> Dict[str, Any]:
        """Benchmark memory usage patterns."""
        print("📊 Benchmarking memory usage...")

        tracemalloc.start()

        config = HTTPWrapperConfig()
        client = HTTPClient(
            retry_config=config.retry_config,
            circuit_breaker_config=config.circuit_breaker_config,
            http_config=config.http_config,
            cache_config=config.cache_config
        )

        # Get initial memory
        initial_memory = tracemalloc.get_traced_memory()[0]

        with patch('requests.Session.request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"success": True}
            mock_request.return_value = mock_response

            # Make requests to see memory impact
            for i in range(1000):
                client.get(f"http://example.com/api/{i}")

            final_memory = tracemalloc.get_traced_memory()[0]

        tracemalloc.stop()

        memory_used = final_memory - initial_memory
        memory_per_request = memory_used / 1000

        return {
            "memory_usage": {
                "initial_memory_kb": initial_memory / 1024,
                "final_memory_kb": final_memory / 1024,
                "memory_used_kb": memory_used / 1024,
                "memory_per_request_kb": memory_per_request / 1024
            }
        }

    def print_results(self):
        """Print benchmark results in a readable format."""
        print("\n" + "="*60)
        print("📈 HTTPWRAPPER PERFORMANCE BENCHMARK RESULTS")
        print("="*60)

        for category, data in self.results.items():
            print(f"\n🔹 {category.replace('_', ' ').title()}:")

            if isinstance(data, dict):
                for metric, value in data.items():
                    if isinstance(value, dict):
                        print(f"  📊 {metric.replace('_', ' ').title()}:")
                        for sub_metric, sub_value in value.items():
                            if isinstance(sub_value, float):
                                print(".2f")
                            else:
                                print(f"    • {sub_metric}: {sub_value}")
                    elif isinstance(value, float):
                        if 'time' in metric or 'delay' in metric:
                            print(".4f")
                        elif 'percentage' in metric or 'ratio' in metric:
                            print(".2f")
                        else:
                            print(".2f")
                    else:
                        print(f"  📊 {metric}: {value}")

        print("\n" + "="*60)


def main():
    """Run all performance benchmarks."""
    benchmark = PerformanceBenchmark()
    results = benchmark.run_all_benchmarks()
    benchmark.print_results()

    # Save results to file
    import json
    with open('benchmark_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)

    print("\n📄 Results saved to benchmark_results.json")


if __name__ == "__main__":
    main()
