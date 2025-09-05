"""
Tests for Retry Manager implementation.
"""

import time
import unittest
from unittest.mock import patch

from httpwrapper.config import BackoffStrategy, RetryConfig
from httpwrapper.retry_manager import RetryManager


class TestRetryManager(unittest.TestCase):
    """Test cases for Retry Manager functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = RetryConfig(
            max_attempts=3,
            backoff_factor=0.1,
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            jitter=True,
            min_delay=0.01,
            max_delay=10.0
        )
        self.rm = RetryManager(self.config)

    def test_calculate_delay_exponential_no_jitter(self):
        """Test exponential backoff delay calculation without jitter."""
        config = RetryConfig(
            backoff_factor=0.1,
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            jitter=False
        )
        rm = RetryManager(config)

        # First attempt (attempt 0): 0.1 * 2^0 = 0.1
        delay = rm.calculate_delay(0)
        self.assertEqual(delay, 0.1)

        # Second attempt (attempt 1): 0.1 * 2^1 = 0.2
        delay = rm.calculate_delay(1)
        self.assertEqual(delay, 0.2)

        # Third attempt (attempt 2): 0.1 * 2^2 = 0.4
        delay = rm.calculate_delay(2)
        self.assertEqual(delay, 0.4)

    def test_calculate_delay_linear(self):
        """Test linear backoff delay calculation."""
        config = RetryConfig(
            max_attempts=4,
            backoff_factor=0.2,
            backoff_strategy=BackoffStrategy.LINEAR,
            jitter=False
        )
        rm = RetryManager(config)

        # attempt 0: 0.2 * (0 + 1) = 0.2
        self.assertAlmostEqual(rm.calculate_delay(0), 0.2, places=7)

        # attempt 1: 0.2 * (1 + 1) = 0.4
        self.assertAlmostEqual(rm.calculate_delay(1), 0.4, places=7)

        # attempt 2: 0.2 * (2 + 1) = 0.6
        self.assertAlmostEqual(rm.calculate_delay(2), 0.6, places=7)

    def test_calculate_delay_fixed(self):
        """Test fixed delay calculation."""
        config = RetryConfig(
            backoff_factor=0.5,
            backoff_strategy=BackoffStrategy.FIXED,
            jitter=False
        )
        rm = RetryManager(config)

        # All attempts should have same delay
        for attempt in range(5):
            self.assertEqual(rm.calculate_delay(attempt), 0.5)

    def test_delay_clamping(self):
        """Test that delays are properly clamped to min/max values."""
        config = RetryConfig(
            backoff_factor=100.0,  # Very large to test max clamping
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            jitter=False,
            min_delay=0.1,
            max_delay=5.0
        )
        rm = RetryManager(config)

        delay = rm.calculate_delay(10)  # 100 * 2^10 = 102400, should be clamped to 5.0
        self.assertEqual(delay, 5.0)

    @patch('random.uniform')
    def test_jitter_application(self, mock_uniform):
        """Test jitter is applied correctly."""
        mock_uniform.return_value = 1.1  # 110% of base delay

        config = RetryConfig(
            backoff_factor=1.0,
            backoff_strategy=BackoffStrategy.FIXED,
            jitter=True
        )
        rm = RetryManager(config)

        delay = rm.calculate_delay(0)
        mock_uniform.assert_called_once_with(0.75, 1.25)
        self.assertEqual(delay, 1.1)  # 1.0 * 1.1

    def test_get_retry_delays(self):
        """Test getting list of all retry delays."""
        config = RetryConfig(
            max_attempts=3,
            backoff_factor=0.1,
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            jitter=False
        )
        rm = RetryManager(config)

        delays = rm.get_retry_delays()

        # Should return delays for max_attempts
        self.assertEqual(len(delays), 3)
        self.assertEqual(delays[0], 0.1)  # 0.1 * 2^0
        self.assertEqual(delays[1], 0.2)  # 0.1 * 2^1
        self.assertEqual(delays[2], 0.4)  # 0.1 * 2^2

    def test_calculate_total_expected_delay(self):
        """Test total expected delay calculation."""
        config = RetryConfig(
            max_attempts=3,
            backoff_factor=0.1,
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            jitter=False
        )
        rm = RetryManager(config)

        min_delay, max_delay = rm.calculate_total_expected_delay()

        # With jitter=False, min should equal max
        expected_total = 0.1 + 0.2 + 0.4  # 0.7
        self.assertEqual(min_delay, expected_total)
        self.assertEqual(max_delay, expected_total)

    def test_calculate_total_expected_delay_with_jitter(self):
        """Test total expected delay calculation with jitter."""
        config = RetryConfig(
            max_attempts=2,
            backoff_factor=1.0,
            backoff_strategy=BackoffStrategy.FIXED,
            jitter=True,
            min_delay=0.01,
            max_delay=100.0
        )
        rm = RetryManager(config)

        min_delay, max_delay = rm.calculate_total_expected_delay()

        # With jitter, the total delay range will vary based on random jitter
        # We just check that we get reasonable values and max > min
        self.assertGreater(min_delay, 1.0)  # At least some delay
        self.assertLess(min_delay, 3.0)     # Not too much
        self.assertGreater(max_delay, min_delay)  # Max should be greater than min

    def test_should_retry_logic(self):
        """Test should_retry logic."""
        config = RetryConfig(max_attempts=3)
        rm = RetryManager(config)

        # Should retry for attempts 0 and 1 (when max_attempts=3)
        self.assertTrue(rm.should_retry(0))
        self.assertTrue(rm.should_retry(1))
        self.assertFalse(rm.should_retry(2))  # Attempt 2 is the last one

    def test_wait_before_retry(self):
        """Test wait_before_retry sleeps for correct duration."""
        config = RetryConfig(
            backoff_factor=0.1,  # Delay for testing
            backoff_strategy=BackoffStrategy.FIXED,
            jitter=False
        )
        rm = RetryManager(config)

        start_time = time.time()
        rm.wait_before_retry(0)
        end_time = time.time()

        elapsed = end_time - start_time
        self.assertAlmostEqual(elapsed, 0.1, delta=0.01)

    def test_get_retry_info(self):
        """Test getting detailed retry attempt information."""
        config = RetryConfig(
            max_attempts=3,
            backoff_factor=0.1,
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            jitter=False
        )
        rm = RetryManager(config)

        info = rm.get_retry_info(1)  # Second attempt (attempt 1)

        expected = {
            'attempt': 2,  # 1-based indexing
            'delay': 0.2,  # 0.1 * 2^1
            'total_attempts': 3,
            'backoff_strategy': 'exponential',
            'jitter_enabled': False,
            'should_retry_next': True,
            'remaining_attempts': 1
        }

        self.assertEqual(info, expected)

    def test_get_retry_info_last_attempt(self):
        """Test retry info for last attempt."""
        rm = RetryManager(self.config)
        info = rm.get_retry_info(2)  # Last attempt

        self.assertEqual(info['attempt'], 3)
        self.assertFalse(info['should_retry_next'])
        self.assertEqual(info['remaining_attempts'], 0)

    def test_negative_attempt_raises_error(self):
        """Test that negative attempt numbers raise ValueError."""
        with self.assertRaises(ValueError):
            self.rm.calculate_delay(-1)

    def test_custom_max_attempts_parameter(self):
        """Test using custom max_attempts parameter in methods."""
        delays = self.rm.get_retry_delays(max_attempts=5)
        self.assertEqual(len(delays), 5)

        # Create config without jitter for predictable sum calculation
        test_config = RetryConfig(
            max_attempts=3,
            backoff_factor=0.1,
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            jitter=False,  # No jitter for predictable results
            min_delay=0.01,
            max_delay=10.0
        )
        test_rm = RetryManager(test_config)

        min_delay, max_delay = test_rm.calculate_total_expected_delay(max_attempts=4)
        config_delays = test_rm.get_retry_delays(max_attempts=4)
        expected_min = sum(config_delays)
        self.assertAlmostEqual(min_delay, expected_min, places=7)

    def test_edge_case_zero_backoff_factor(self):
        """Test edge case with zero backoff factor."""
        config = RetryConfig(
            backoff_factor=0.0,
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            jitter=False
        )
        rm = RetryManager(config)

        # All delays should be 0
        for attempt in range(3):
            delay = rm.calculate_delay(attempt)
            # Should be clamped to min_delay
            self.assertEqual(delay, config.min_delay)

    def test_edge_case_very_large_exponential(self):
        """Test handling of very large exponential values."""
        config = RetryConfig(
            backoff_factor=10.0,
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            jitter=False,
            max_delay=100.0
        )
        rm = RetryManager(config)

        # Very large delays should be clamped
        delay = rm.calculate_delay(10)  # 10 * 2^10 = 10240
        self.assertEqual(delay, 100.0)  # Clamped to max_delay

    def test_different_backoff_strategies_comparison(self):
        """Test different backoff strategies produce different delays."""
        base_config = RetryConfig(
            backoff_factor=0.1,
            jitter=False,
            max_attempts=4
        )

        configs = {
            'exponential': RetryConfig(**{**base_config.model_dump(), 'backoff_strategy': BackoffStrategy.EXPONENTIAL}),
            'linear': RetryConfig(**{**base_config.model_dump(), 'backoff_strategy': BackoffStrategy.LINEAR}),
            'fixed': RetryConfig(**{**base_config.model_dump(), 'backoff_strategy': BackoffStrategy.FIXED})
        }

        results = {}
        for strategy, config in configs.items():
            rm = RetryManager(config)
            results[strategy] = rm.get_retry_delays()

        # Exponential should grow exponentially
        exp_delays = results['exponential']
        self.assertTrue(exp_delays[1] > exp_delays[0])
        self.assertTrue(exp_delays[2] > exp_delays[1] * 1.5)  # Roughly exponential

        # Linear should grow linearly
        lin_delays = results['linear']
        self.assertAlmostEqual(lin_delays[1] - lin_delays[0], lin_delays[2] - lin_delays[1], places=7)

        # Fixed should be constant
        fixed_delays = results['fixed']
        self.assertEqual(len(set(fixed_delays)), 1)  # All delays should be same

    def tearDown(self):
        """Clean up after tests."""
        self.rm = None


if __name__ == '__main__':
    unittest.main()
