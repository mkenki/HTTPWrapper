"""
Retry manager with various backoff strategies and jitter support.
"""

import math
import random
import time
from typing import Union

from .config import BackoffStrategy, RetryConfig


class RetryManager:
    """
    Manages retry behavior with configurable backoff strategies.

    Supports:
    - Exponential backoff with jitter
    - Linear backoff
    - Fixed delay backoff
    - Custom backoff functions
    """

    def __init__(self, config: RetryConfig):
        """
        Initialize retry manager.

        Args:
            config: Retry configuration
        """
        self.config = config

    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for a given retry attempt.

        Args:
            attempt: Zero-based attempt number

        Returns:
            Delay in seconds before next retry
        """
        if attempt < 0:
            raise ValueError("Attempt number cannot be negative")

        # Calculate base delay based on strategy
        if self.config.backoff_strategy == BackoffStrategy.EXPONENTIAL:
            base_delay = self.config.backoff_factor * (2 ** attempt)
        elif self.config.backoff_strategy == BackoffStrategy.LINEAR:
            base_delay = self.config.backoff_factor * (attempt + 1)
        elif self.config.backoff_strategy == BackoffStrategy.FIXED:
            base_delay = self.config.backoff_factor
        else:
            raise ValueError(f"Unsupported backoff strategy: {self.config.backoff_strategy}")

        # Clamp to min/max delays
        delay = max(self.config.min_delay, min(base_delay, self.config.max_delay))

        # Add jitter if enabled
        if self.config.jitter:
            delay = self._add_jitter(delay)

        return delay

    def _add_jitter(self, delay: float) -> float:
        """
        Add random jitter to delay to prevent thundering herd.

        Args:
            delay: Base delay

        Returns:
            Delay with jitter applied
        """
        # Use random jitter between 75% and 125% of original delay
        jitter_factor = random.uniform(0.75, 1.25)
        return delay * jitter_factor

    def get_retry_delays(self, max_attempts: Union[int, None] = None) -> list[float]:
        """
        Get list of delays for all retry attempts.

        Args:
            max_attempts: Maximum attempts to calculate (uses config default if None)

        Returns:
            List of delay times in seconds
        """
        attempts = max_attempts or self.config.max_attempts
        delays = []

        for attempt in range(attempts):
            delay = self.calculate_delay(attempt)
            delays.append(delay)

        return delays

    def should_retry(self, attempt: int, max_attempts: Union[int, None] = None) -> bool:
        """
        Check if another retry attempt should be made.

        Args:
            attempt: Zero-based attempt number that just failed
            max_attempts: Maximum attempts allowed (uses config default if None)

        Returns:
            True if should retry, False otherwise
        """
        attempts = max_attempts or self.config.max_attempts
        return attempt < attempts - 1

    def calculate_total_expected_delay(self, max_attempts: Union[int, None] = None) -> tuple[float, float]:
        """
        Calculate expected total delay for retries (min and max bounds).

        Args:
            max_attempts: Maximum attempts to consider (uses config default if None)

        Returns:
            Tuple of (min_total_delay, max_total_delay)
        """
        attempts = max_attempts or self.config.max_attempts
        delays = self.get_retry_delays(attempts)

        total_min = sum(delays)
        total_max = total_min  # Without jitter, min = max

        if self.config.jitter:
            # With jitter, max could be up to 25% higher
            total_max = total_min * 1.25

        return total_min, total_max

    def wait_before_retry(self, attempt: int) -> None:
        """
        Sleep for the calculated delay before next retry attempt.

        Args:
            attempt: Zero-based attempt number
        """
        delay = self.calculate_delay(attempt)
        time.sleep(delay)

    def get_retry_info(self, attempt: int) -> dict:
        """
        Get detailed information about a retry attempt.

        Args:
            attempt: Zero-based attempt number

        Returns:
            Dictionary with retry attempt details
        """
        delay = self.calculate_delay(attempt)
        should_retry_next = self.should_retry(attempt)

        return {
            'attempt': attempt + 1,  # 1-based for display
            'delay': delay,
            'total_attempts': self.config.max_attempts,
            'backoff_strategy': self.config.backoff_strategy.value,
            'jitter_enabled': self.config.jitter,
            'should_retry_next': should_retry_next,
            'remaining_attempts': max(0, self.config.max_attempts - attempt - 1)
        }
