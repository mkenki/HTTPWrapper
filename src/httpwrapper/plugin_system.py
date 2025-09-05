"""
Plugin system for HTTPWrapper extensions.
"""

import abc
import time
from typing import Any, Dict, List, Optional, Type, TypeVar
from dataclasses import dataclass


class HTTPWrapperPlugin(abc.ABC):
    """
    Base class for HTTPWrapper plugins.

    Plugins can intercept and modify request/response processing
    at various points in the HTTP lifecycle.
    """

    def __init__(self):
        self.name: str = self.__class__.__name__
        self.priority: int = 100  # Lower priority runs first

    @abc.abstractmethod
    def initialize(self, config: Dict[str, Any]) -> None:
        """
        Initialize the plugin with configuration.

        Args:
            config: Plugin-specific configuration
        """
        pass

    def pre_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """
        Called before making an HTTP request.

        Args:
            method: HTTP method
            url: Request URL
            **kwargs: Request parameters

        Returns:
            Modified request parameters
        """
        return kwargs

    def post_request(self, response: Any) -> Any:
        """
        Called after receiving an HTTP response.

        Args:
            response: HTTP response object

        Returns:
            Modified response
        """
        return response

    def on_error(self, error: Exception, method: str, url: str) -> Optional[Exception]:
        """
        Called when an error occurs.

        Args:
            error: The exception that occurred
            method: HTTP method
            url: Request URL

        Returns:
            Modified exception or None to suppress
        """
        return error

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get plugin-specific metrics.

        Returns:
            Dictionary of metrics
        """
        return {}

    def shutdown(self) -> None:
        """
        Cleanup resources when the plugin is being removed.
        """
        pass


class MetricsPlugin(HTTPWrapperPlugin):
    """
    Plugin that collects detailed metrics about HTTP requests.
    """

    def __init__(self):
        super().__init__()
        self.name = "metrics"
        self.request_count = 0
        self.error_count = 0
        self.response_times: List[float] = []
        self.status_codes: Dict[int, int] = {}

    def initialize(self, config: Dict[str, Any]) -> None:
        self.max_response_times = config.get('max_response_times', 1000)

    def pre_request(self, method: str, url: str, **kwargs):
        kwargs['_start_time'] = time.time()
        return kwargs

    def post_request(self, response: Any) -> Any:
        self.request_count += 1

        # Extract status code
        status_code = getattr(response, 'status_code', 0)
        self.status_codes[status_code] = self.status_codes.get(status_code, 0) + 1

        # Extract response time
        if hasattr(response, '_start_time'):
            response_time = time.time() - response._start_time
            self.response_times.append(response_time)
            if len(self.response_times) > self.max_response_times:
                self.response_times.pop(0)

        return response

    def on_error(self, error: Exception, method: str, url: str):
        self.error_count += 1
        return error

    def get_metrics(self) -> Dict[str, Any]:
        avg_response_time = (sum(self.response_times) / len(self.response_times)
                           if self.response_times else 0)

        return {
            'plugin_metrics': {
                'total_requests': self.request_count,
                'error_count': self.error_count,
                'avg_response_time': avg_response_time,
                'status_codes': self.status_codes.copy()
            }
        }


class LoggingPlugin(HTTPWrapperPlugin):
    """
    Plugin that provides enhanced structured logging.
    """

    def __init__(self):
        import logging
        super().__init__()
        self.name = "logging"
        self.logger = logging.getLogger('httpwrapper.plugin')
        self.logging = logging

    def initialize(self, config: Dict[str, Any]) -> None:
        level = config.get('log_level', 'INFO')
        self.logger.setLevel(getattr(self.logging, level))

    def pre_request(self, method: str, url: str, **kwargs):
        self.logger.info(f"Making {method} request to {url}")
        return kwargs

    def post_request(self, response: Any) -> Any:
        status_code = getattr(response, 'status_code', 0)
        self.logger.info(f"Received {status_code} response")
        return response

    def on_error(self, error: Exception, method: str, url: str):
        self.logger.error(f"Request to {url} failed: {error}")
        return error


class RateLimitPlugin(HTTPWrapperPlugin):
    """
    Plugin that provides rate limiting capabilities.
    """

    def __init__(self):
        super().__init__()
        self.name = "rate_limit"
        self.requests_per_minute = 60
        self.requests_in_window: List[float] = []

    def initialize(self, config: Dict[str, Any]) -> None:
        self.requests_per_minute = config.get('requests_per_minute', 60)
        self.max_requests = config.get('max_requests', self.requests_per_minute)
        self.window_seconds = config.get('window_seconds', 60)

    def pre_request(self, method: str, url: str, **kwargs):
        import time
        try:
            from ..exceptions import RateLimitError
        except ImportError:
            from httpwrapper.exceptions import RateLimitError

        now = time.time()

        # Clean old requests outside the window
        cutoff = now - self.window_seconds
        self.requests_in_window = [t for t in self.requests_in_window if t > cutoff]

        # Check if we're over the limit
        if len(self.requests_in_window) >= self.max_requests:
            retry_after = self.requests_in_window[0] + self.window_seconds - now
            raise RateLimitError("Rate limit exceeded", retry_after=retry_after)

        # Add current request timestamp
        self.requests_in_window.append(now)
        return kwargs

    def get_metrics(self) -> Dict[str, Any]:
        return {
            'rate_limit_metrics': {
                'requests_in_window': len(self.requests_in_window),
                'max_requests': self.max_requests
            }
        }


class PluginManager:
    """
    Manages HTTPWrapper plugins.
    """

    def __init__(self):
        self.plugins: List[HTTPWrapperPlugin] = []
        self._sorted = False

    def register_plugin(self, plugin_class: Type[HTTPWrapperPlugin], config: Dict[str, Any] = None) -> None:
        """
        Register a plugin class.

        Args:
            plugin_class: Plugin class to instantiate
            config: Configuration for the plugin
        """
        plugin = plugin_class()
        plugin.initialize(config or {})
        self.plugins.append(plugin)
        self._sorted = False
        print(f"Plugin '{plugin.name}' registered successfully")

    def unregister_plugin(self, plugin_name: str) -> None:
        """
        Remove a plugin by name.

        Args:
            plugin_name: Name of the plugin to remove
        """
        for plugin in self.plugins:
            if plugin.name == plugin_name:
                plugin.shutdown()
                self.plugins.remove(plugin)
                self._sorted = True
                print(f"Plugin '{plugin_name}' unregistered")
                break

    def get_plugins(self) -> List[HTTPWrapperPlugin]:
        """Get all registered plugins."""
        return self.plugins.copy()

    def get_plugin(self, name: str) -> Optional[HTTPWrapperPlugin]:
        """Get a plugin by name."""
        for plugin in self.plugins:
            if plugin.name == name:
                return plugin
        return None

    def sort_plugins(self) -> None:
        """Sort plugins by priority."""
        self.plugins.sort(key=lambda p: p.priority)
        self._sorted = True

    def execute_pre_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """Execute pre-request hooks."""
        if not self._sorted:
            self.sort_plugins()

        for plugin in self.plugins:
            kwargs = plugin.pre_request(method, url, **kwargs)

        return kwargs

    def execute_post_request(self, response: Any) -> Any:
        """Execute post-request hooks."""
        if not self._sorted:
            self.sort_plugins()

        for plugin in self.plugins:
            response = plugin.post_request(response)

        return response

    def execute_on_error(self, error: Exception, method: str, url: str) -> Optional[Exception]:
        """Execute error hooks."""
        if not self._sorted:
            self.sort_plugins()

        for plugin in self.plugins:
            error = plugin.on_error(error, method, url)
            if error is None:
                break

        return error

    def get_all_metrics(self) -> Dict[str, Any]:
        """Get metrics from all plugins."""
        metrics = {}
        for plugin in self.plugins:
            plugin_metrics = plugin.get_metrics()
            if plugin_metrics:
                metrics[plugin.name] = plugin_metrics
        return metrics

    def shutdown_all(self) -> None:
        """Shutdown all plugins."""
        for plugin in self.plugins:
            plugin.shutdown()
        self.plugins.clear()


# Global plugin manager instance
plugin_manager = PluginManager()
