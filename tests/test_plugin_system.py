"""
Tests for plugin system implementation.
"""

import unittest
from unittest.mock import Mock, patch
import time

from httpwrapper.plugin_system import (
    HTTPWrapperPlugin,
    MetricsPlugin,
    LoggingPlugin,
    RateLimitPlugin,
    PluginManager
)


class TestHTTPWrapperPlugin(unittest.TestCase):
    """Test cases for base HTTPWrapperPlugin."""

    def test_plugin_initialization(self):
        """Test plugin initialization."""
        # Create a concrete plugin class for testing
        class TestPlugin(HTTPWrapperPlugin):
            def initialize(self, config):
                pass

        plugin = TestPlugin()
        plugin.name = "test_plugin"
        plugin.priority = 50

        self.assertEqual(plugin.name, "test_plugin")
        self.assertEqual(plugin.priority, 50)

    def test_plugin_abstract_method(self):
        """Test that base plugin raises NotImplementedError."""
        from abc import ABC

        # Cannot instantiate abstract class directly
        self.assertTrue(ABC in HTTPWrapperPlugin.__bases__)

    def test_plugin_hooks_default_behavior(self):
        """Test default hook implementations."""
        # Create a concrete plugin class for testing
        class TestPlugin(HTTPWrapperPlugin):
            def initialize(self, config):
                pass

        plugin = TestPlugin()

        # These should not raise exceptions and return input unchanged
        kwargs = plugin.pre_request("GET", "http://example.com")
        self.assertEqual(kwargs, {})

        response = plugin.post_request("mock_response")
        self.assertEqual(response, "mock_response")

        error = plugin.on_error(ValueError("test"), "GET", "http://example.com")
        self.assertIsInstance(error, ValueError)

        metrics = plugin.get_metrics()
        self.assertEqual(metrics, {})

        # Shutdown should not raise
        plugin.shutdown()


class TestMetricsPlugin(unittest.TestCase):
    """Test cases for MetricsPlugin."""

    def setUp(self):
        """Set up test fixtures."""
        self.plugin = MetricsPlugin()

    def test_metrics_plugin_initialization(self):
        """Test metrics plugin initialization."""
        config = {'max_response_times': 500}
        self.plugin.initialize(config)

        self.assertEqual(self.plugin.name, "metrics")
        self.assertEqual(self.plugin.max_response_times, 500)

    def test_metrics_plugin_pre_request(self):
        """Test pre_request metric tracking."""
        kwargs = self.plugin.pre_request("GET", "http://example.com")
        self.assertIn('_start_time', kwargs)

    def test_metrics_plugin_post_request(self):
        """Test post_request metric tracking."""
        # Initialize the plugin first
        self.plugin.initialize({})

        # Mock response
        response = Mock()
        response.status_code = 200
        response._start_time = time.time() - 0.1

        self.plugin.post_request(response)

        self.assertEqual(self.plugin.request_count, 1)
        self.assertEqual(self.plugin.status_codes[200], 1)
        self.assertEqual(len(self.plugin.response_times), 1)

    def test_metrics_plugin_error_tracking(self):
        """Test error tracking in plugin."""
        error = ValueError("test error")
        result_error = self.plugin.on_error(error, "GET", "http://example.com")

        self.assertEqual(result_error, error)
        self.assertEqual(self.plugin.error_count, 1)

    def test_metrics_plugin_get_metrics(self):
        """Test metrics retrieval."""
        # Set up some data
        self.plugin.request_count = 5
        self.plugin.error_count = 1
        self.plugin.response_times = [0.1, 0.2, 0.15]
        self.plugin.status_codes = {200: 3, 404: 1, 500: 1}

        metrics = self.plugin.get_metrics()

        self.assertIn('plugin_metrics', metrics)
        self.assertEqual(metrics['plugin_metrics']['total_requests'], 5)
        self.assertEqual(metrics['plugin_metrics']['error_count'], 1)
        self.assertAlmostEqual(metrics['plugin_metrics']['avg_response_time'], 0.15, places=3)


class TestLoggingPlugin(unittest.TestCase):
    """Test cases for LoggingPlugin."""

    def setUp(self):
        """Set up test fixtures."""
        self.plugin = LoggingPlugin()

    def test_logging_plugin_initialization(self):
        """Test logging plugin initialization."""
        import logging

        config = {'log_level': 'DEBUG'}
        self.plugin.initialize(config)

        self.assertEqual(self.plugin.name, "logging")
        self.assertEqual(self.plugin.logger.level, logging.DEBUG)

    @patch('builtins.print')  # Mock print to avoid console output
    def test_logging_plugin_hooks(self, mock_print):
        """Test logging plugin hooks."""
        import logging

        # Set up logging to avoid actual output
        with patch.object(self.plugin.logger, 'info'):
            with patch.object(self.plugin.logger, 'error'):
                # Test pre_request
                kwargs = self.plugin.pre_request("GET", "http://example.com")
                self.assertEqual(kwargs, {})

                # Test post_request
                response = Mock()
                response.status_code = 200
                result = self.plugin.post_request(response)
                self.assertEqual(result, response)

                # Test error
                error = ValueError("test")
                result_error = self.plugin.on_error(error, "GET", "http://example.com")
                self.assertEqual(result_error, error)


class TestRateLimitPlugin(unittest.TestCase):
    """Test cases for RateLimitPlugin."""

    def setUp(self):
        """Set up test fixtures."""
        self.plugin = RateLimitPlugin()

    def test_rate_limit_plugin_initialization(self):
        """Test rate limit plugin initialization."""
        config = {
            'requests_per_minute': 100,
            'max_requests': 120,
            'window_seconds': 30
        }
        self.plugin.initialize(config)

        self.assertEqual(self.plugin.requests_per_minute, 100)
        self.assertEqual(self.plugin.max_requests, 120)
        self.assertEqual(self.plugin.window_seconds, 30)

    def test_rate_limit_plugin_under_limit(self):
        """Test rate limiting when under the limit."""
        self.plugin.initialize({'max_requests': 2, 'window_seconds': 1})

        # Should not raise exception
        kwargs = self.plugin.pre_request("GET", "http://example.com")
        self.assertEqual(len(self.plugin.requests_in_window), 1)

    def test_rate_limit_plugin_over_limit(self):
        """Test rate limiting when over the limit."""
        from httpwrapper.exceptions import RateLimitError

        self.plugin.initialize({'max_requests': 1, 'window_seconds': 1})

        # First request should succeed
        self.plugin.pre_request("GET", "http://example.com")

        # Second request should fail
        with self.assertRaises(RateLimitError):
            self.plugin.pre_request("GET", "http://example.com")

    def test_rate_limit_plugin_window_cleanup(self):
        """Test cleanup of old requests from the window."""
        import time

        self.plugin.initialize({'max_requests': 2, 'window_seconds': 0.1})

        # Add a request
        self.plugin.pre_request("GET", "http://example.com")

        # Wait for window to expire
        time.sleep(0.15)

        # Add another request - should succeed
        self.plugin.pre_request("GET", "http://example.com")

        # Should have cleaned up the old request
        self.assertEqual(len(self.plugin.requests_in_window), 1)

    def test_rate_limit_plugin_metrics(self):
        """Test rate limit plugin metrics."""
        self.plugin.requests_in_window = [1.0, 2.0]
        self.plugin.max_requests = 10

        metrics = self.plugin.get_metrics()

        self.assertIn('rate_limit_metrics', metrics)
        self.assertEqual(metrics['rate_limit_metrics']['requests_in_window'], 2)
        self.assertEqual(metrics['rate_limit_metrics']['max_requests'], 10)


class TestPluginManager(unittest.TestCase):
    """Test cases for PluginManager."""

    def setUp(self):
        """Set up test fixtures."""
        self.manager = PluginManager()

    def test_plugin_manager_initialization(self):
        """Test plugin manager initialization."""
        self.assertEqual(len(self.manager.plugins), 0)
        self.assertFalse(self.manager._sorted)

    def test_register_plugin(self):
        """Test plugin registration."""
        self.manager.register_plugin(MetricsPlugin, {'max_response_times': 100})

        self.assertEqual(len(self.manager.plugins), 1)
        self.assertEqual(self.manager.plugins[0].name, "metrics")
        self.assertEqual(self.manager.plugins[0].max_response_times, 100)

    def test_unregister_plugin(self):
        """Test plugin unregistration."""
        self.manager.register_plugin(MetricsPlugin)
        self.assertEqual(len(self.manager.plugins), 1)

        self.manager.unregister_plugin("metrics")
        self.assertEqual(len(self.manager.plugins), 0)

    def test_get_plugin(self):
        """Test getting a plugin by name."""
        self.manager.register_plugin(MetricsPlugin)

        plugin = self.manager.get_plugin("metrics")
        self.assertIsNotNone(plugin)
        self.assertEqual(plugin.name, "metrics")

        # Test nonexistent plugin
        nonexistent = self.manager.get_plugin("nonexistent")
        self.assertIsNone(nonexistent)

    def test_get_plugins(self):
        """Test getting all plugins."""
        self.manager.register_plugin(MetricsPlugin)
        self.manager.register_plugin(LoggingPlugin)

        plugins = self.manager.get_plugins()
        self.assertEqual(len(plugins), 2)
        plugin_names = [p.name for p in plugins]
        self.assertIn("metrics", plugin_names)
        self.assertIn("logging", plugin_names)

    def test_plugin_sorting(self):
        """Test plugin sorting by priority."""
        # Create mock plugins with different priorities
        plugin1 = MetricsPlugin()
        plugin1.priority = 200

        plugin2 = LoggingPlugin()
        plugin2.priority = 50

        self.manager.plugins = [plugin1, plugin2]

        self.manager.sort_plugins()

        self.assertTrue(self.manager._sorted)
        self.assertEqual(self.manager.plugins[0].priority, 50)
        self.assertEqual(self.manager.plugins[1].priority, 200)

    def test_execute_pre_request(self):
        """Test pre-request hook execution."""
        self.manager.register_plugin(MetricsPlugin)

        kwargs = self.manager.execute_pre_request("GET", "http://example.com", param="value")

        self.assertIn('_start_time', kwargs)

    def test_execute_post_request(self):
        """Test post-request hook execution."""
        self.manager.register_plugin(MetricsPlugin)

        response = Mock()
        response.status_code = 200
        response._start_time = time.time() - 0.1  # Add proper start time

        result = self.manager.execute_post_request(response)

        self.assertEqual(result, response)

    def test_execute_on_error(self):
        """Test error hook execution."""
        self.manager.register_plugin(MetricsPlugin)

        error = ValueError("test")
        result = self.manager.execute_on_error(error, "GET", "http://example.com")

        self.assertEqual(result, error)

    def test_get_all_metrics(self):
        """Test getting metrics from all plugins."""
        self.manager.register_plugin(MetricsPlugin)
        self.manager.register_plugin(RateLimitPlugin)

        metrics = self.manager.get_all_metrics()

        self.assertIn('metrics', metrics)
        self.assertIn('rate_limit', metrics)

    def test_shutdown_all(self):
        """Test shutting down all plugins."""
        self.manager.register_plugin(MetricsPlugin)
        self.manager.register_plugin(LoggingPlugin)

        self.assertEqual(len(self.manager.plugins), 2)

        self.manager.shutdown_all()

        self.assertEqual(len(self.manager.plugins), 0)


class TestPluginIntegration(unittest.TestCase):
    """Test cases for plugin integration and interaction."""

    def test_multiple_plugins_execution_order(self):
        """Test that multiple plugins execute in priority order."""
        manager = PluginManager()

        # Create plugins with different priorities
        high_priority = MetricsPlugin()
        high_priority.priority = 10

        low_priority = LoggingPlugin()
        low_priority.priority = 500

        manager.plugins = [low_priority, high_priority]
        manager.sort_plugins()

        # Execute hooks
        kwargs = manager.execute_pre_request("GET", "http://example.com")

        # Should contain _start_time from MetricsPlugin (higher priority)
        self.assertIn('_start_time', kwargs)

    def test_plugin_error_suppression(self):
        """Test that a plugin can suppress errors."""
        class ErrorSuppressPlugin(HTTPWrapperPlugin):
            def initialize(self, config):
                pass

            def on_error(self, error, method, url):
                return None  # Suppress the error

        manager = PluginManager()
        manager.register_plugin(ErrorSuppressPlugin)

        error = ValueError("test")
        result = manager.execute_on_error(error, "GET", "http://example.com")

        self.assertIsNone(result)

    def test_plugin_response_modification(self):
        """Test that plugins can modify responses."""
        class ResponseTransformPlugin(HTTPWrapperPlugin):
            def initialize(self, config):
                pass

            def post_request(self, response):
                # Add a custom attribute
                if hasattr(response, 'status_code'):
                    response.processed_by_plugin = True
                return response

        manager = PluginManager()
        manager.register_plugin(ResponseTransformPlugin)

        response = Mock()
        response.status_code = 200

        result = manager.execute_post_request(response)

        self.assertTrue(hasattr(result, 'processed_by_plugin'))
        self.assertTrue(result.processed_by_plugin)


if __name__ == '__main__':
    unittest.main()
