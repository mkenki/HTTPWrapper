#!/usr/bin/env python3
"""
Example usage of HTTPWrapper with Plugin System.

This example demonstrates how to use the plugin system to extend HTTPWrapper
with custom functionality like rate limiting, metrics collection, and logging.
"""

import time
from httpwrapper.config import HTTPWrapperConfig
from httpwrapper.client import HTTPClient
from httpwrapper.plugin_system import (
    PluginManager,
    MetricsPlugin,
    LoggingPlugin,
    RateLimitPlugin,
    HTTPWrapperPlugin
)


# Example of a custom plugin
class AuthPlugin(HTTPWrapperPlugin):
    """
    Custom plugin that adds API key authentication to requests.
    """

    def __init__(self):
        super().__init__()
        self.name = "auth"
        self.priority = 5  # Run early to add auth headers

    def initialize(self, config):
        """Initialize with API key and auth method."""
        self.api_key = config.get('api_key', '')
        self.auth_method = config.get('auth_method', 'Bearer')

    def pre_request(self, method, url, **kwargs):
        """Add authentication headers to requests."""
        if not self.api_key:
            print("⚠️  Warning: No API key configured")
            return kwargs

        headers = kwargs.get('headers', {})

        if self.auth_method == 'Bearer':
            headers['Authorization'] = f'Bearer {self.api_key}'
        elif self.auth_method == 'API-Key':
            headers['X-API-Key'] = self.api_key

        kwargs['headers'] = headers
        return kwargs


class ResponseSerializerPlugin(HTTPWrapperPlugin):
    """
    Plugin that adds response body length tracking and formatting.
    """

    def __init__(self):
        super().__init__()
        self.name = "response_serializer"
        self.total_response_size = 0

    def initialize(self, config):
        """Initialize plugin."""
        pass

    def post_request(self, response):
        """Track response size and add metadata."""
        response.body_size = len(getattr(response, 'content', b''))
        self.total_response_size += response.body_size

        # Add custom metadata
        response.metadata = {
            'body_size': response.body_size,
            'total_downloaded': self.total_response_size,
            'serialized_at': time.time()
        }

        return response


def demo_basic_plugins():
    """
    Demonstrate basic plugin usage with built-in plugins.
    """
    print("🚀 HTTPWrapper Plugin System Demo")
    print("=" * 50)

    # Create plugin manager
    pm = PluginManager()

    # Register built-in plugins
    pm.register_plugin(MetricsPlugin, {
        'max_response_times': 50
    })

    pm.register_plugin(LoggingPlugin, {
        'log_level': 'INFO'
    })

    pm.register_plugin(RateLimitPlugin, {
        'max_requests': 5,
        'window_seconds': 10
    })

    # Create HTTP client with default config
    config = HTTPWrapperConfig()
    client = HTTPClient(
        retry_config=config.retry_config,
        circuit_breaker_config=config.circuit_breaker_config,
        http_config=config.http_config,
        cache_config=config.cache_config
    )

    # Simulate requests (we'll mock the actual HTTP calls)
    print("\n📊 Testing request pipeline with plugins...")

    # Override the client's request method to use plugins
    original_request = client.session.request

    def enhanced_request(*args, **kwargs):
        # Execute pre-request plugins
        kwargs = pm.execute_pre_request(args[0], args[1], **kwargs)

        try:
            # Make the actual request (mocked for demo)
            mock_response = type('MockResponse', (), {
                'status_code': 200,
                'json': lambda: {'message': 'success'},
                'content': b'{"message": "success"}' * 10,  # Mock content
                'headers': {'content-type': 'application/json'}
            })()

            # Execute post-request plugins
            mock_response = pm.execute_post_request(mock_response)

            return mock_response

        except Exception as e:
            # Execute error plugins
            error = pm.execute_on_error(e, args[0], args[1])
            if error:
                raise error
            return None

    # Monkey patch for demo
    client.session.request = enhanced_request

    # Test requests
    for i in range(3):
        print(f"\n🔄 Request {i+1}:")
        try:
            response = client.get("http://api.example.com/data")
            if response:
                print(f"   ✅ Status: {response.status_code}")
                if hasattr(response, 'body_size'):
                    print(f"   📏 Body size: {response.body_size} bytes")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # Show rate limiting
        rate_limit_metrics = pm.get_plugin('rate_limit').get_metrics()
        requests_in_window = rate_limit_metrics['rate_limit_metrics']['requests_in_window']
        print(f"   🚦 Rate limit: {requests_in_window}/5 requests in window")

        time.sleep(0.5)  # Small delay between requests

    # Show final metrics
    print("\n📈 Final Plugin Metrics:")
    all_metrics = pm.get_all_metrics()

    for plugin_name, metrics in all_metrics.items():
        print(f"\n🔹 {plugin_name.upper()} PLUGIN:")
        for key, value in metrics.items():
            if isinstance(value, dict):
                print(f"   • {key}:")
                for sub_key, sub_value in value.items():
                    print(".2f" if isinstance(sub_value, float) else f"      {sub_key}: {sub_value}")
            else:
                print(f"   • {key}: {value}")

    pm.shutdown_all()


def demo_custom_plugins():
    """
    Demonstrate custom plugin creation and integration.
    """
    print("\n\n🎨 Custom Plugin Demo")
    print("=" * 30)

    pm = PluginManager()

    # Register custom plugins
    pm.register_plugin(AuthPlugin, {
        'api_key': 'your-api-key-here',
        'auth_method': 'Bearer'
    })

    pm.register_plugin(ResponseSerializerPlugin)

    # Create client
    config = HTTPWrapperConfig()
    client = HTTPClient(
        retry_config=config.retry_config,
        circuit_breaker_config=config.circuit_breaker_config,
        http_config=config.http_config,
        cache_config=config.cache_config
    )

    # Mock request method with custom plugin integration
    def custom_request(*args, **kwargs):
        print(f"\n🔐 Pre-request authorization check...")

        # Execute pre-request plugins (auth plugin will add headers)
        kwargs = pm.execute_pre_request(args[0], args[1], **kwargs)

        # Check if auth header was added
        headers = kwargs.get('headers', {})
        if 'Authorization' in headers:
            print(f"   ✅ Auth header added: {headers['Authorization'][:20]}...")

        # Mock response
        mock_response = type('MockResponse', (), {
            'status_code': 200,
            'json': lambda: {'data': 'authenticated successfully'},
            'content': b'{"data": "authenticated successfully"}' * 25,
            'headers': {'content-type': 'application/json', 'x-api-version': '1.0'}
        })()

        # Execute post-request plugins
        mock_response = pm.execute_post_request(mock_response)

        return mock_response

    client.session.request = custom_request

    # Test request
    print("\n📤 Making authenticated request...")
    response = client.get("https://api.example.com/secure")

    if response:
        print("   ✅ Response received")
        if hasattr(response, 'metadata'):
            metadata = response.metadata
            print("   📊 Metadata added by plugin:")
            print(f"      Body size: {metadata['body_size']} bytes")
            print(f"      Serialized at: {time.ctime(metadata['serialized_at'])}")

    pm.shutdown_all()


def demo_plugin_configuration():
    """
    Demonstrate different plugin configurations and priority ordering.
    """
    print("\n\n⚙️  Plugin Configuration Demo")
    print("=" * 35)

    # Create multiple plugin managers with different configurations
    configs = [
        {
            'name': 'Development',
            'plugins': [
                (LoggingPlugin, {'log_level': 'DEBUG'}),
                (MetricsPlugin, {'max_response_times': 10}),
            ]
        },
        {
            'name': 'Production',
            'plugins': [
                (RateLimitPlugin, {'max_requests': 100, 'window_seconds': 60}),
                (MetricsPlugin, {'max_response_times': 1000}),
                (AuthPlugin, {'api_key': 'prod-key', 'auth_method': 'API-Key'}),
            ]
        },
        {
            'name': 'Testing',
            'plugins': [
                (ResponseSerializerPlugin, {}),
                (LoggingPlugin, {'log_level': 'WARNING'}),
            ]
        }
    ]

    for config in configs:
        print(f"\n🏗️  {config['name']} Configuration:")

        pm = PluginManager()
        for plugin_class, plugin_config in config['plugins']:
            pm.register_plugin(plugin_class, plugin_config)

        # Show registered plugins
        plugins = pm.get_plugins()
        for plugin in plugins:
            priority = getattr(plugin, 'priority', 'default')
            print(f"   • {plugin.name} (priority: {priority})")

        pm.shutdown_all()


def main():
    """Run all plugin system demonstrations."""
    try:
        demo_basic_plugins()
        demo_custom_plugins()
        demo_plugin_configuration()

        print("\n" + "="*60)
        print("🎉 HTTPWrapper Plugin System Demo Complete!")
        print("The plugin system provides:")
        print("   • Extensible request/response pipeline")
        print("   • Priority-based plugin execution")
        print("   • Built-in plugins for common functionality")
        print("   • Easy-to-create custom plugins")
        print("   • Comprehensive metrics and monitoring")
        print("="*60)

    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
