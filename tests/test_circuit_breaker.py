"""
Tests for Circuit Breaker implementation.
"""

import time
import unittest
from unittest.mock import patch

from httpwrapper.circuit_breaker import CircuitBreaker
from httpwrapper.config import CircuitBreakerConfig, CircuitBreakerState
from httpwrapper.exceptions import CircuitBreakerOpenError


class TestCircuitBreaker(unittest.TestCase):
    """Test cases for Circuit Breaker functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=2.0,  # 2 seconds for testing
            success_threshold=2,
            name="test_circuit"
        )
        self.cb = CircuitBreaker(self.config)

    def test_initial_state_closed(self):
        """Test that circuit breaker starts in closed state."""
        self.assertEqual(self.cb.get_state("testhost"), CircuitBreakerState.CLOSED)
        self.assertTrue(self.cb.can_proceed("testhost"))
        self.assertEqual(self.cb.failure_count("testhost"), 0)

    def test_success_record_closed_state(self):
        """Test recording success in closed state."""
        # Record a failure first
        self.cb.record_failure("testhost")
        self.assertEqual(self.cb.failure_count("testhost"), 1)

        # Record success
        self.cb.record_success("testhost")
        self.assertEqual(self.cb.failure_count("testhost"), 0)
        self.assertEqual(self.cb.get_state("testhost"), CircuitBreakerState.CLOSED)

    def test_failure_threshold_opens_circuit(self):
        """Test that circuit opens after reaching failure threshold."""
        host = "testhost"

        # Record failures up to threshold
        for i in range(self.config.failure_threshold):
            self.assertEqual(self.cb.get_state(host), CircuitBreakerState.CLOSED)
            self.assertTrue(self.cb.can_proceed(host))
            self.cb.record_failure(host)

        # Circuit should now be open
        self.assertEqual(self.cb.get_state(host), CircuitBreakerState.OPEN)
        self.assertFalse(self.cb.can_proceed(host))

    def test_open_circuit_blocks_requests(self):
        """Test that open circuit blocks all requests."""
        host = "testhost"

        # Force circuit open by recording failures
        for _ in range(self.config.failure_threshold):
            self.cb.record_failure(host)

        # Verify circuit is open
        self.assertEqual(self.cb.get_state(host), CircuitBreakerState.OPEN)

        # Should return False (circuit is open)
        self.assertFalse(self.cb.can_proceed(host))

    def test_open_to_half_open_transition(self):
        """Test transition from open to half-open after recovery timeout."""
        host = "testhost"

        # Open the circuit
        for _ in range(self.config.failure_threshold):
            self.cb.record_failure(host)
        self.assertEqual(self.cb.get_state(host), CircuitBreakerState.OPEN)

        # Wait for recovery timeout
        time.sleep(self.config.recovery_timeout + 0.1)

        # Next request should move to half-open and be allowed
        self.assertTrue(self.cb.can_proceed(host))
        self.assertEqual(self.cb.get_state(host), CircuitBreakerState.HALF_OPEN)

    def test_half_open_failure_returns_to_open(self):
        """Test that any failure in half-open state returns circuit to open."""
        host = "testhost"

        # Get to half-open state
        for _ in range(self.config.failure_threshold):
            self.cb.record_failure(host)
        time.sleep(self.config.recovery_timeout + 0.1)
        self.cb.can_proceed(host)  # This moves to half-open

        # Record failure in half-open
        self.cb.record_failure(host)
        self.assertEqual(self.cb.get_state(host), CircuitBreakerState.OPEN)
        self.assertEqual(self.cb.failure_count(host), self.config.failure_threshold)

    def test_half_open_success_threshold_closes_circuit(self):
        """Test that sufficient successes in half-open close the circuit."""
        host = "testhost"

        # Get to half-open state
        for _ in range(self.config.failure_threshold):
            self.cb.record_failure(host)
        time.sleep(self.config.recovery_timeout + 0.1)
        self.cb.can_proceed(host)  # This moves to half-open

        # Record enough successes
        for _ in range(self.config.success_threshold):
            self.cb.record_success(host)

        self.assertEqual(self.cb.get_state(host), CircuitBreakerState.CLOSED)
        self.assertEqual(self.cb.failure_count(host), 0)

    def test_manual_reset(self):
        """Test manual circuit breaker reset."""
        host = "testhost"

        # Open the circuit
        for _ in range(self.config.failure_threshold):
            self.cb.record_failure(host)
        self.assertEqual(self.cb.get_state(host), CircuitBreakerState.OPEN)

        # Reset
        self.cb.reset(host)
        self.assertEqual(self.cb.get_state(host), CircuitBreakerState.CLOSED)
        self.assertEqual(self.cb.failure_count(host), 0)

    def test_per_host_state_isolation(self):
        """Test that circuit breaker state is isolated per host."""
        host1 = "host1"
        host2 = "host2"

        # Fail host1
        for _ in range(self.config.failure_threshold):
            self.cb.record_failure(host1)
        self.assertEqual(self.cb.get_state(host1), CircuitBreakerState.OPEN)
        self.assertEqual(self.cb.get_state(host2), CircuitBreakerState.CLOSED)

        # host2 should still work
        self.assertTrue(self.cb.can_proceed(host2))

    def test_stats_functionality(self):
        """Test circuit breaker statistics functionality."""
        host = "testhost"
        stats = self.cb.get_stats(host)

        # Should have basic stats structure
        self.assertIn('state', stats)
        self.assertIn('failure_count', stats)
        self.assertIn('success_count', stats)
        self.assertIn('last_failure_time', stats)
        self.assertIn('last_attempt_time', stats)
        self.assertIn('config', stats)

        # Verify state
        self.assertEqual(stats['state'], CircuitBreakerState.CLOSED.value)

    @patch('time.time')
    def test_time_based_transitions(self, mock_time):
        """Test time-based transitions work correctly."""
        host = "testhost"
        base_time = 1000.0
        mock_time.return_value = base_time

        # Open circuit
        for _ in range(self.config.failure_threshold):
            self.cb.record_failure(host)
        self.assertEqual(self.cb.get_state(host), CircuitBreakerState.OPEN)

        # Advance time by less than recovery timeout
        mock_time.return_value = base_time + self.config.recovery_timeout - 0.1
        self.assertFalse(self.cb.can_proceed(host))

        # Advance time past recovery timeout
        mock_time.return_value = base_time + self.config.recovery_timeout + 0.1
        self.assertTrue(self.cb.can_proceed(host))
        self.assertEqual(self.cb.get_state(host), CircuitBreakerState.HALF_OPEN)

    def test_thread_safety(self):
        """Test that circuit breaker operations are thread-safe."""
        import threading
        import concurrent.futures

        host = "testhost"
        success_count = [0]  # Use list for mutable shared state
        lock = threading.Lock()

        def record_success():
            self.cb.record_success(host)
            with lock:
                success_count[0] += 1

        # Open circuit first
        for _ in range(self.config.failure_threshold):
            self.cb.record_failure(host)

        # Move to half-open
        time.sleep(self.config.recovery_timeout + 0.1)
        self.cb.can_proceed(host)

        # Run multiple success recordings concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(record_success) for _ in range(5)]
            concurrent.futures.wait(futures)

        # All operations should complete without errors
        self.assertEqual(success_count[0], 5)

    def test_edge_case_single_failure_threshold(self):
        """Test edge case where failure threshold is 1."""
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=1.0)
        cb = CircuitBreaker(config)
        host = "testhost"

        # Single failure should open circuit
        cb.record_failure(host)
        self.assertEqual(cb.get_state(host), CircuitBreakerState.OPEN)

    def test_edge_case_zero_recovery_timeout(self):
        """Test edge case with zero recovery timeout."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.0,
            success_threshold=1
        )
        cb = CircuitBreaker(config)
        host = "testhost"

        # Open circuit
        cb.record_failure(host)
        cb.record_failure(host)
        self.assertEqual(cb.get_state(host), CircuitBreakerState.OPEN)

        # With zero timeout, should immediately go to half-open
        self.assertTrue(cb.can_proceed(host))
        self.assertEqual(cb.get_state(host), CircuitBreakerState.HALF_OPEN)

    def tearDown(self):
        """Clean up after tests."""
        # Reset circuit breaker for isolation
        self.cb = None


if __name__ == '__main__':
    unittest.main()
