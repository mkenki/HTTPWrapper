#!/usr/bin/env python3
"""
Example usage of HTTPWrapper with retry and circuit breaker functionality.
"""

import asyncio
import sys
import time
from datetime import datetime

# Add src to Python path for local development
sys.path.insert(0, 'src')

from httpwrapper import HTTPClient, AsyncHTTPClient
from httpwrapper.config import RetryConfig, CircuitBreakerConfig, BackoffStrategy


def demo_sync_client():
    """Demonstrate synchronous HTTP client with retry and circuit breaker."""
    print("\n" + "="*60)
    print("🎯 SYNCHRONOUS HTTP CLIENT DEMO")
    print("="*60)

    # Configure retry with exponential backoff and jitter
    retry_config = RetryConfig(
        max_attempts=3,
        backoff_factor=0.5,
        backoff_strategy=BackoffStrategy.EXPONENTIAL,
        jitter=True,
        retry_on_status_codes=[429, 500, 502, 503, 504],
        retry_on_exceptions=["ConnectionError", "Timeout"]
    )

    # Configure circuit breaker
    circuit_config = CircuitBreakerConfig(
        failure_threshold=2,
        recovery_timeout=30.0,
        success_threshold=1
    )

    # Create HTTP client
    client = HTTPClient(
        retry_config=retry_config,
        circuit_breaker_config=circuit_config
    )

    urls_to_test = [
        "https://httpbin.org/status/200",  # Should succeed
        "https://httpbin.org/status/429",  # Should trigger retry
        "https://httpbin.org/status/500",  # Should trigger retry
        "https://httpbin.org/status/200",  # Should succeed
    ]

    print(f"📊 Starting requests at {datetime.now().strftime('%H:%M:%S')}")
    print(f"🔄 Retry Config: {retry_config.max_attempts} attempts, exponential backoff")
    print(f"🔒 Circuit Breaker: {circuit_config.failure_threshold} failures -> OPEN")
    print()

    for i, url in enumerate(urls_to_test, 1):
        start_time = time.time()

        try:
            print(f"🌐 Request {i}: {url}")
            response = client.get(url, timeout=(1, 5))

            elapsed = time.time() - start_time
            status_info = f"✅ {response.status_code}"
            circuit_state = client.get_circuit_breaker_state("httpbin.org")

            print(f"   └─ {status_info} ({elapsed:.2f}s) | Circuit: {circuit_state.value}")

        except Exception as e:
            elapsed = time.time() - start_time
            print(f"   └─ ❌ ERROR: {type(e).__name__} ({elapsed:.2f}s)")

        print()

    # Show metrics
    metrics = client.get_metrics()
    if metrics['summary']['total_requests'] > 0:
        print("📈 METRICS SUMMARY:")
        print(f"   • Total Requests: {metrics['summary']['total_requests']}")
        print(f"   • Success Rate: {metrics['summary']['success_rate_percent']:.2f}%")
        print(f"   • Average Duration: {metrics['summary']['average_duration_seconds']:.3f}s")
        print(f"   • Total Errors: {metrics['summary']['total_errors']}")

        if 'hosts' in metrics and 'host_httpbin.org' in metrics['hosts']:
            host_data = metrics['hosts']['host_httpbin.org']
            print(f"   • HTTPBin.org Requests: {host_data['requests']}")
            print(f"   • HTTPBin.org Errors: {host_data['errors']}")
            print(f"   • HTTPBin.org Avg Duration: {host_data['average_duration']:.3f}s")


async def demo_async_client():
    """Demonstrate asynchronous HTTP client."""
    print("\n" + "="*60)
    print("🎯 ASYNCHRONOUS HTTP CLIENT DEMO")
    print("="*60)

    retry_config = RetryConfig(
        max_attempts=2,
        backoff_factor=0.3,
        backoff_strategy=BackoffStrategy.LINEAR,
        jitter=False
    )

    async with AsyncHTTPClient(retry_config=retry_config) as client:
        urls = [
            "https://httpbin.org/status/200",
            "https://httpbin.org/delay/1",  # 1 second delay
            "https://httpbin.org/status/200",
        ]

        print(f"🚀 Making {len(urls)} concurrent requests...")
        start_time = time.time()

        # Make concurrent requests
        tasks = [client.get(url, timeout=(1, 10)) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        elapsed = time.time() - start_time

        print("\n📋 RESULTS:")
        for i, result in enumerate(results, 1):
            if isinstance(result, Exception):
                print(f"   {i}. ❌ {type(result).__name__}: {result}")
            else:
                print(f"   {i}. ✅ {result.status} ({result.url})")

        print(f"\n⏱️  Total time: {elapsed:.2f}s")
        print("\n📊 ASYNC METRICS:")
        metrics = client.get_metrics()
        print(f"   • Total Requests: {metrics['summary']['total_requests']}")
        print(f"   • Success Rate: {metrics['summary']['success_rate_percent']:.1f}%")


def main():
    """Main demonstration function."""
    print("🚀 HTTPWrapper - Resilient HTTP Client Demo")
    print("Features: Retry patterns, Circuit breaker, Async support")
    print("="*60)

    # Run synchronous demo
    demo_sync_client()

    # Run asynchronous demo
    asyncio.run(demo_async_client())

    print("\n" + "="*60)
    print("🎉 Demo completed! HTTPWrapper provides:")
    print("   ✅ Advanced retry with exponential/linear backoff")
    print("   ✅ Circuit breaker protection against failing services")
    print("   ✅ Comprehensive error handling and metrics")
    print("   ✅ Both synchronous and asynchronous support")
    print("   ✅ Enterprise-grade resilience patterns")
    print("="*60)


if __name__ == "__main__":
    main()
